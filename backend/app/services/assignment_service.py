"""
Assignment service: handles CRUD operations and subject ownership/enrollment authorization.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import (
    AppException,
    DuplicateResourceError,
    InsufficientPermissionsError,
    NotEnrolledError,
    ResourceNotFoundError,
)
from app.models.assignment import Assignment
from app.models.rubric import Rubric
from app.models.rubric_item import RubricItem
from app.models.submission import Submission
from app.models.subject import Subject
from app.models.user import User, UserRole
from app.schemas.assignment import AssignmentCreate, AssignmentUpdate
from app.services.enrollment_service import is_student_enrolled


def create_assignment(
    db: Session, subject_id: int, data: AssignmentCreate, current_faculty: User
) -> Assignment:
    """Create a new assignment for a subject owned by the authenticated faculty member."""
    subject = db.scalar(select(Subject).where(Subject.id == subject_id))
    if not subject:
        raise ResourceNotFoundError(f"Subject with ID {subject_id} not found.")

    if subject.faculty_id != current_faculty.id:
        raise InsufficientPermissionsError()

    assignment = Assignment(
        subject_id=subject_id,
        title=data.title.strip(),
        description=data.description,
        instructions=data.instructions,
        due_date=data.due_date,
        max_marks=data.max_marks,
        created_by=current_faculty.id,
    )
    db.add(assignment)
    db.flush()

    if data.rubric:
        # Validate criteria sum
        if data.rubric.items:
            seen = set()
            criteria_sum = 0.0
            for item in data.rubric.items:
                norm = item.criterion.strip().lower()
                if norm in seen:
                    raise DuplicateResourceError(f"Duplicate criterion '{item.criterion.strip()}' in rubric.")
                seen.add(norm)
                criteria_sum += float(item.max_marks)

            if criteria_sum > float(data.max_marks):
                raise AppException(
                    detail=(
                        f"Total rubric criteria marks ({criteria_sum}) exceed assignment "
                        f"maximum marks ({data.max_marks})."
                    ),
                    status_code=422,
                )

        rubric = Rubric(
            assignment_id=assignment.id,
            name=data.rubric.name.strip() if data.rubric.name else f"{data.title.strip()} Rubric",
            description=data.rubric.description,
        )
        db.add(rubric)
        db.flush()

        if data.rubric.items:
            for item_data in data.rubric.items:
                rub_item = RubricItem(
                    rubric_id=rubric.id,
                    criterion=item_data.criterion.strip(),
                    description=item_data.description,
                    max_marks=item_data.max_marks,
                )
                db.add(rub_item)
            db.flush()

    db.refresh(assignment)
    stmt = (
        select(Assignment)
        .options(
            selectinload(Assignment.subject),
            selectinload(Assignment.rubric).selectinload(Rubric.items),
        )
        .where(Assignment.id == assignment.id)
    )
    return db.scalar(stmt)


def list_subject_assignments(
    db: Session, subject_id: int, current_user: User
) -> list[Assignment]:
    """
    List assignments for a subject.
    Faculty can view if they own the subject.
    Students can view if they are enrolled in the subject.
    """
    subject = db.scalar(select(Subject).where(Subject.id == subject_id))
    if not subject:
        raise ResourceNotFoundError(f"Subject with ID {subject_id} not found.")

    if current_user.role == UserRole.FACULTY:
        if subject.faculty_id != current_user.id:
            raise InsufficientPermissionsError()
    else:
        if not is_student_enrolled(db, current_user.id, subject_id):
            raise NotEnrolledError()

    stmt = (
        select(Assignment)
        .options(
            selectinload(Assignment.rubric).selectinload(Rubric.items),
        )
        .where(Assignment.subject_id == subject_id)
        .order_by(Assignment.due_date.asc())
    )
    return list(db.scalars(stmt).all())


def get_assignment_by_id(
    db: Session, assignment_id: int, current_user: User
) -> Assignment:
    """
    Get assignment by ID, verifying faculty ownership or student enrollment.
    """
    stmt = (
        select(Assignment)
        .options(
            selectinload(Assignment.subject),
            selectinload(Assignment.rubric).selectinload(Rubric.items),
        )
        .where(Assignment.id == assignment_id)
    )
    assignment = db.scalar(stmt)
    if not assignment:
        raise ResourceNotFoundError(f"Assignment with ID {assignment_id} not found.")

    if current_user.role == UserRole.FACULTY:
        if assignment.subject.faculty_id != current_user.id:
            raise InsufficientPermissionsError()
    else:
        if not is_student_enrolled(db, current_user.id, assignment.subject_id):
            raise NotEnrolledError()

    return assignment


def update_assignment(
    db: Session, assignment_id: int, data: AssignmentUpdate, current_faculty: User
) -> Assignment:
    """Update assignment details, strictly verifying faculty ownership."""
    stmt = (
        select(Assignment)
        .options(
            selectinload(Assignment.subject),
            selectinload(Assignment.rubric).selectinload(Rubric.items),
        )
        .where(Assignment.id == assignment_id)
    )
    assignment = db.scalar(stmt)
    if not assignment:
        raise ResourceNotFoundError(f"Assignment with ID {assignment_id} not found.")

    if assignment.subject.faculty_id != current_faculty.id:
        raise InsufficientPermissionsError()

    if data.title is not None:
        title_val = data.title.strip()
        if not title_val:
            raise AppException("Assignment title cannot be blank.", status_code=422)
        assignment.title = title_val
    if data.description is not None:
        assignment.description = data.description
    if data.instructions is not None:
        assignment.instructions = data.instructions
    if data.due_date is not None:
        assignment.due_date = data.due_date
    if data.is_archived is not None:
        assignment.is_archived = data.is_archived
    if data.max_marks is not None:
        if assignment.rubric and assignment.rubric.items:
            current_criteria_sum = sum(float(i.max_marks) for i in assignment.rubric.items)
            if current_criteria_sum > float(data.max_marks):
                raise AppException(
                    detail=(
                        f"New maximum marks ({data.max_marks}) is less than existing rubric criteria "
                        f"sum ({current_criteria_sum}). Please adjust rubric criteria first."
                    ),
                    status_code=422,
                )
        assignment.max_marks = data.max_marks

    db.flush()
    db.refresh(assignment)
    return assignment


def archive_assignment(
    db: Session, assignment_id: int, current_faculty: User, is_archived: bool = True
) -> Assignment:
    """Archive or unarchive an assignment, strictly verifying faculty ownership."""
    stmt = (
        select(Assignment)
        .options(
            selectinload(Assignment.subject),
            selectinload(Assignment.rubric).selectinload(Rubric.items),
        )
        .where(Assignment.id == assignment_id)
    )
    assignment = db.scalar(stmt)
    if not assignment:
        raise ResourceNotFoundError(f"Assignment with ID {assignment_id} not found.")

    if assignment.subject.faculty_id != current_faculty.id:
        raise InsufficientPermissionsError()

    assignment.is_archived = is_archived
    db.flush()
    db.refresh(assignment)
    return assignment


def delete_assignment(
    db: Session, assignment_id: int, current_faculty: User
) -> None:
    """
    Delete an assignment, strictly verifying faculty ownership.
    Safeguard: If student submissions exist, reject permanent deletion
    to prevent silently deleting student submissions, grades, and feedback.
    """
    stmt = (
        select(Assignment)
        .options(selectinload(Assignment.subject))
        .where(Assignment.id == assignment_id)
    )
    assignment = db.scalar(stmt)
    if not assignment:
        raise ResourceNotFoundError(f"Assignment with ID {assignment_id} not found.")

    if assignment.subject.faculty_id != current_faculty.id:
        raise InsufficientPermissionsError()

    submission_count = (
        db.scalar(
            select(func.count(Submission.id)).where(Submission.assignment_id == assignment_id)
        )
        or 0
    )
    if submission_count > 0:
        raise AppException(
            detail=(
                f"Cannot delete assignment '{assignment.title}': it has {submission_count} student submission(s) "
                "or assessment records. Please archive the assignment instead to preserve academic history."
            ),
            status_code=409,
        )

    db.delete(assignment)
    db.flush()
