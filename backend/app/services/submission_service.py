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
    subpath: str | None = None,
):
    """
    Retrieve FileResponse for student submitted file or extracted subfile.
    Authorized for the student submitter or the faculty owning the assignment.
    """
    submission = get_submission_by_id(db, submission_id, current_user)

    if not submission.file_path:
        raise ResourceNotFoundError("No file was uploaded with this submission.")

    from pathlib import Path
    from app.services.file_storage.security import (
        build_secure_file_response,
        validate_file_path_safe,
    )
    from app.services.document_processing.zip_processor import get_zip_processor

    storage = get_file_storage_service()
    safe_main_path = validate_file_path_safe(submission.file_path, storage.upload_dir)

    if subpath:
        ext = safe_main_path.suffix.lower()
        if ext != ".zip":
            raise AppException(
                detail="Subpath previews are only supported for archive (.zip) submissions.",
                status_code=400,
            )
        from app.services.file_storage.storage import get_archive_unpacked_dir
        unpack_dir = get_archive_unpacked_dir(safe_main_path)
        if not unpack_dir.exists():
            zip_proc = get_zip_processor()
            zip_proc.inspect_and_extract(safe_main_path, target_extract_dir=unpack_dir)

        safe_subfile = validate_file_path_safe(str(unpack_dir / subpath), unpack_dir)
        return build_secure_file_response(
            file_path=safe_subfile,
            original_filename=Path(subpath).name,
            inline=inline,
        )

    return build_secure_file_response(
        file_path=safe_main_path,
        original_filename=submission.original_filename,
        inline=inline,
    )


def get_submission_manifest(
    db: Session,
    submission_id: int,
    current_user: User,
) -> dict:
    """
    Get detailed manifest and file breakdown of a submission.
    Authorized for the student submitter or the faculty owning the assignment.
    """
    submission = get_submission_by_id(db, submission_id, current_user)
    if not submission.file_path:
        return {
            "submission_id": submission.id,
            "has_file": False,
            "file_format": None,
            "file_manifest": None,
            "execution_audit": None,
        }

    from pathlib import Path
    from app.services.file_storage.security import validate_file_path_safe
    from app.services.document_processing.notebook_processor import get_notebook_processor
    from app.services.document_processing.zip_processor import get_zip_processor

    storage = get_file_storage_service()
    safe_path = validate_file_path_safe(submission.file_path, storage.upload_dir)
    ext = safe_path.suffix.lower()
    orig_name = submission.original_filename or safe_path.name

    file_manifest = None
    execution_audit = None

    if ext == ".ipynb":
        nb = get_notebook_processor().parse_file(safe_path, filename=orig_name)
        execution_audit = {
            "total_cells": nb.audit.total_cells,
            "markdown_cells": nb.audit.markdown_cells,
            "code_cells": nb.audit.code_cells,
            "executed_code_cells": nb.audit.executed_code_cells,
            "unexecuted_code_cells": nb.audit.unexecuted_code_cells,
            "cells_with_errors": nb.audit.cells_with_errors,
            "execution_status": nb.audit.execution_status,
            "execution_order_anomaly": nb.audit.execution_order_anomaly,
            "kernel_language": nb.audit.kernel_language,
        }
    elif ext == ".zip":
        from app.services.file_storage.storage import get_archive_unpacked_dir
        unpack_dir = get_archive_unpacked_dir(safe_path)
        zip_proc = get_zip_processor()
        manifest = zip_proc.inspect_and_extract(safe_path, target_extract_dir=unpack_dir)
        file_manifest = {
            "total_files": manifest.total_files,
            "total_size_bytes": manifest.total_size_bytes,
            "category_counts": manifest.category_counts,
            "has_readme": manifest.has_readme,
            "has_tests": manifest.has_tests,
            "has_manifest": manifest.has_manifest,
            "notebook_count": len(manifest.notebooks),
            "files": [
                {
                    "rel_path": e.rel_path,
                    "size": e.size,
                    "category": e.category,
                    "extension": e.extension,
                    "is_test": e.is_test,
                }
                for e in manifest.file_entries
            ],
        }
        if manifest.notebooks:
            nb = manifest.notebooks[0]
            execution_audit = {
                "total_cells": nb.audit.total_cells,
                "markdown_cells": nb.audit.markdown_cells,
                "code_cells": nb.audit.code_cells,
                "executed_code_cells": nb.audit.executed_code_cells,
                "unexecuted_code_cells": nb.audit.unexecuted_code_cells,
                "cells_with_errors": nb.audit.cells_with_errors,
                "execution_status": nb.audit.execution_status,
                "execution_order_anomaly": nb.audit.execution_order_anomaly,
                "kernel_language": nb.audit.kernel_language,
            }

    return {
        "submission_id": submission.id,
        "has_file": True,
        "original_filename": orig_name,
        "file_format": ext.lstrip("."),
        "file_size": safe_path.stat().st_size,
        "file_manifest": file_manifest,
        "execution_audit": execution_audit,
    }


def get_submission_evidence_report(
    db: Session,
    submission_id: int,
    current_user: User,
) -> dict:
    """
    Get detailed assessment evidence diagnostic report for faculty review or student inspection.
    Includes discovered archive entries, processing status counts, rubric evidence mapping,
    omitted or truncated files, vision inspection verification, and human review flags.
    """
    submission = get_submission_by_id(db, submission_id, current_user)
    if not submission.file_path:
        return {
            "submission_id": submission.id,
            "original_filename": None,
            "file_format": None,
            "total_archive_entries": 0,
            "supported_files_count": 0,
            "successfully_processed_count": 0,
            "failed_files_count": 0,
            "unsupported_files_count": 0,
            "truncated_files_count": 0,
            "omitted_files_count": 0,
            "vision_inspected": False,
            "vision_inspected_count": 0,
            "file_inventory": [],
            "criterion_evidence_mapping": {},
            "truncated_or_excluded_files": [],
            "criteria_requiring_human_review": [],
        }

    from pathlib import Path
    import mimetypes
    from app.services.file_storage.security import validate_file_path_safe
    from app.services.file_storage.storage import get_archive_unpacked_dir
    from app.services.document_processing.zip_processor import get_zip_processor

    storage = get_file_storage_service()
    safe_path = validate_file_path_safe(submission.file_path, storage.upload_dir)
    ext = safe_path.suffix.lower()
    orig_name = submission.original_filename or safe_path.name
    zip_proc = get_zip_processor()

    # Load assignment rubric items
    rubric_items_data = []
    assignment = submission.assignment
    if assignment and assignment.rubric and assignment.rubric.items:
        rubric_items_data = [
            {"id": item.id, "criterion": item.criterion, "description": item.description, "max_marks": float(item.max_marks)}
            for item in assignment.rubric.items
        ]

    instructions = assignment.instructions if assignment else None
    title = assignment.title if assignment else None

    if ext == ".zip":
        unpack_dir = get_archive_unpacked_dir(safe_path)
        manifest = zip_proc.inspect_and_extract(safe_path, target_extract_dir=unpack_dir)
        zip_proc._rank_inventory_relevance(
            inventory=manifest,
            rubric_items=rubric_items_data,
            assignment_instructions=instructions,
            assignment_title=title,
        )
        return zip_proc.generate_evidence_report(
            submission_id=submission.id,
            inventory=manifest,
            original_filename=orig_name,
        )

    # For direct non-archive files
    detected_mime = mimetypes.guess_type(orig_name)[0] or "application/octet-stream"
    file_size = safe_path.stat().st_size
    return {
        "submission_id": submission.id,
        "original_filename": orig_name,
        "file_format": ext.lstrip("."),
        "total_archive_entries": 1,
        "supported_files_count": 1,
        "successfully_processed_count": 1,
        "failed_files_count": 0,
        "unsupported_files_count": 0,
        "truncated_files_count": 0,
        "omitted_files_count": 0,
        "vision_inspected": False,
        "vision_inspected_count": 0,
        "category_counts": {ext.lstrip("."): 1},
        "file_inventory": [
            {
                "rel_path": orig_name,
                "filename": safe_path.name,
                "extension": ext,
                "detected_content_type": detected_mime,
                "category": ext.lstrip("."),
                "size_bytes": file_size,
                "processing_status": "PROCESSED",
                "useful_content_extracted": True,
                "summary": f"Direct single-file submission: {orig_name} ({file_size} bytes).",
                "error_or_omission_reason": None,
                "vision_inspected": False,
                "is_test": False,
                "relevance_score": 100.0,
            }
        ],
        "criterion_evidence_mapping": {
            r["criterion"]: [orig_name] for r in rubric_items_data
        },
        "truncated_or_excluded_files": [],
        "criteria_requiring_human_review": [],
    }


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
