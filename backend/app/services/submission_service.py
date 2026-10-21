"""
Submission service: handles assignment submissions, file/text storage, and authorization.
"""

from datetime import datetime, timezone

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import (
    AppException,
    InsufficientPermissionsError,
    NotEnrolledError,
    ResourceNotFoundError,
)
from app.models.assessment import AssessmentStatus
from app.models.assignment import Assignment
from app.models.submission import Submission, SubmissionStatus
from app.models.user import User, UserRole
from app.services.enrollment_service import is_student_enrolled
from app.services.file_storage.storage import get_file_storage_service


async def submit_assignment(
    db: Session,
    assignment_id: int,
    student_user: User,
    submission_text: str | None = None,
    file: UploadFile | None = None,
) -> Submission:
    """Submit student work for an assignment (text, file, or both)."""
    if student_user.role != UserRole.STUDENT:
        raise InsufficientPermissionsError()

    assignment = db.scalar(
        select(Assignment)
        .options(selectinload(Assignment.subject))
        .where(Assignment.id == assignment_id)
    )
    if not assignment:
        raise ResourceNotFoundError(f"Assignment with ID {assignment_id} not found.")

    # Student can submit ONLY to assignments belonging to subjects in which they are enrolled
    if not is_student_enrolled(db, student_user.id, assignment.subject_id):
        raise NotEnrolledError()

    if not submission_text and not file:
        raise AppException(
            detail="Submission must include text or an uploaded file.",
            status_code=422,
        )

    file_path: str | None = None
    original_filename: str | None = None

    if file is not None and file.filename:
        storage = get_file_storage_service()
        file_path, original_filename = await storage.save_file(file)

    submission = Submission(
        assignment_id=assignment_id,
        student_id=student_user.id,
        submission_text=submission_text,
        file_path=file_path,
        original_filename=original_filename,
        status=SubmissionStatus.SUBMITTED,
    )
    db.add(submission)
    db.flush()
    db.refresh(submission)
    return submission


def list_assignment_submissions(
    db: Session, assignment_id: int, current_faculty: User
) -> list[Submission]:
    """List all submissions for an assignment. Accessible only by the owning faculty."""
    if current_faculty.role != UserRole.FACULTY:
        raise InsufficientPermissionsError()

    assignment = db.scalar(
        select(Assignment)
        .options(selectinload(Assignment.subject))
        .where(Assignment.id == assignment_id)
    )
    if not assignment:
        raise ResourceNotFoundError(f"Assignment with ID {assignment_id} not found.")

    if assignment.subject.faculty_id != current_faculty.id:
        raise InsufficientPermissionsError()

    stmt = (
        select(Submission)
        .options(selectinload(Submission.student))
        .where(Submission.assignment_id == assignment_id)
        .order_by(Submission.submitted_at.desc())
    )
    return list(db.scalars(stmt).all())


def list_student_submissions(db: Session, current_student: User) -> list[Submission]:
    """List submissions owned by the currently authenticated student."""
    if current_student.role != UserRole.STUDENT:
        raise InsufficientPermissionsError()

    stmt = (
        select(Submission)
        .options(selectinload(Submission.student))
        .where(Submission.student_id == current_student.id)
        .order_by(Submission.submitted_at.desc())
    )
    return list(db.scalars(stmt).all())


def get_submission_by_id(
    db: Session, submission_id: int, current_user: User
) -> Submission:
    """
    Get a single submission by ID.
    Students can only view their own submissions.
    Faculty can only view submissions for assignments they own.
    """
    stmt = (
        select(Submission)
        .options(
            selectinload(Submission.student),
            selectinload(Submission.assignment).selectinload(Assignment.subject),
        )
        .where(Submission.id == submission_id)
    )
    submission = db.scalar(stmt)
    if not submission:
        raise ResourceNotFoundError(f"Submission with ID {submission_id} not found.")

    if current_user.role == UserRole.STUDENT:
        if submission.student_id != current_user.id:
            raise InsufficientPermissionsError()
    elif current_user.role == UserRole.FACULTY:
        if submission.assignment.subject.faculty_id != current_user.id:
            raise InsufficientPermissionsError()
    else:
        raise InsufficientPermissionsError()

    return submission


def get_submission_file_response(
    db: Session,
    submission_id: int,
    current_user: User,
    inline: bool = False,
):
    """
    Retrieve FileResponse for student submitted file.
    Authorized for the student submitter or the faculty owning the assignment.
    """
    submission = get_submission_by_id(db, submission_id, current_user)

    if not submission.file_path:
        raise ResourceNotFoundError("No file was uploaded with this submission.")

    from app.services.file_storage.security import (
        build_secure_file_response,
        validate_file_path_safe,
    )
    storage = get_file_storage_service()
    safe_path = validate_file_path_safe(submission.file_path, storage.upload_dir)

    return build_secure_file_response(
        file_path=safe_path,
        original_filename=submission.original_filename,
        inline=inline,
    )


async def replace_submission(
    db: Session,
    submission_id: int,
    student_user: User,
    submission_text: str | None = None,
    file: UploadFile | None = None,
) -> Submission:
    """
    Replace an existing submission with updated text or file.
    Safeguards:
      1. Student must own the submission.
      2. Assignment due date must not have passed.
      3. Submission must not be evaluated/approved/modified or under active faculty review.
    """
    if student_user.role != UserRole.STUDENT:
        raise InsufficientPermissionsError()

    stmt = (
        select(Submission)
        .options(
            selectinload(Submission.assignment),
            selectinload(Submission.assessment),
        )
        .where(Submission.id == submission_id)
    )
    submission = db.scalar(stmt)
    if not submission:
        raise ResourceNotFoundError(f"Submission with ID {submission_id} not found.")

    if submission.student_id != student_user.id:
        raise InsufficientPermissionsError("You can only modify your own submissions.")

    # Deadline validation
    now = datetime.now(timezone.utc)
    due_date = submission.assignment.due_date
    if due_date.tzinfo is None:
        due_date = due_date.replace(tzinfo=timezone.utc)
    if now > due_date:
        raise AppException(
            detail="Cannot replace submission: assignment due date has passed.",
            status_code=400,
        )

    # Status / evaluation validation
    if (
        submission.status == SubmissionStatus.EVALUATED
        or (
            submission.assessment
            and submission.assessment.status in [AssessmentStatus.APPROVED, AssessmentStatus.MODIFIED]
        )
    ):
        raise AppException(
            detail="Cannot replace submission: work has already been evaluated and finalized.",
            status_code=400,
        )

    if submission.status == SubmissionStatus.UNDER_REVIEW:
        raise AppException(
            detail="Cannot replace submission: assessment is currently under faculty review.",
            status_code=400,
        )

    # Content check
    if not submission_text and not file:
        raise AppException(
            detail="Updated submission must include text or an uploaded file.",
            status_code=422,
        )

    storage = get_file_storage_service()

    if file is not None and file.filename:
        # Delete old file safely if it existed
        if submission.file_path:
            storage.delete_file(submission.file_path)

        new_path, original_filename = await storage.save_file(file)
        submission.file_path = new_path
        submission.original_filename = original_filename

    if submission_text is not None:
        submission.submission_text = submission_text

    # If an unapproved draft assessment exists, remove it so fresh evaluation is required
    if submission.assessment:
        db.delete(submission.assessment)

    submission.submitted_at = now
    submission.status = SubmissionStatus.SUBMITTED
    db.flush()
    db.refresh(submission)
    return submission


def withdraw_submission(
    db: Session,
    submission_id: int,
    student_user: User,
) -> None:
    """
    Withdraw (delete) a student submission before the deadline and before evaluation.
    Safeguards:
      1. Student must own the submission.
      2. Assignment due date must not have passed.
      3. Submission must not be evaluated or under active review.
    """
    if student_user.role != UserRole.STUDENT:
        raise InsufficientPermissionsError()

    stmt = (
        select(Submission)
        .options(
            selectinload(Submission.assignment),
            selectinload(Submission.assessment),
        )
        .where(Submission.id == submission_id)
    )
    submission = db.scalar(stmt)
    if not submission:
        raise ResourceNotFoundError(f"Submission with ID {submission_id} not found.")

    if submission.student_id != student_user.id:
        raise InsufficientPermissionsError("You can only withdraw your own submissions.")

    # Deadline validation
    now = datetime.now(timezone.utc)
    due_date = submission.assignment.due_date
    if due_date.tzinfo is None:
        due_date = due_date.replace(tzinfo=timezone.utc)
    if now > due_date:
        raise AppException(
            detail="Cannot withdraw submission: assignment due date has passed.",
            status_code=400,
        )

    # Status / evaluation validation
    if (
        submission.status == SubmissionStatus.EVALUATED
        or (
            submission.assessment
            and submission.assessment.status in [AssessmentStatus.APPROVED, AssessmentStatus.MODIFIED]
        )
    ):
        raise AppException(
            detail="Cannot withdraw submission: work has already been evaluated and finalized.",
            status_code=400,
        )

    if submission.status == SubmissionStatus.UNDER_REVIEW:
        raise AppException(
            detail="Cannot withdraw submission: assessment is currently under faculty review.",
            status_code=400,
        )

    storage = get_file_storage_service()
    if submission.file_path:
        storage.delete_file(submission.file_path)

    if submission.assessment:
        db.delete(submission.assessment)

    db.delete(submission)
    db.flush()
