"""
Assignment service: handles CRUD operations and subject ownership/enrollment authorization.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import (
    InsufficientPermissionsError,
    NotEnrolledError,
    ResourceNotFoundError,
)
from app.models.assignment import Assignment
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
        title=data.title,
        description=data.description,
        instructions=data.instructions,
        due_date=data.due_date,
        max_marks=data.max_marks,
        created_by=current_faculty.id,
    )
    db.add(assignment)
    db.flush()
    db.refresh(assignment)
    return assignment


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
        .options(selectinload(Assignment.subject))
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
        .options(selectinload(Assignment.subject))
        .where(Assignment.id == assignment_id)
    )
    assignment = db.scalar(stmt)
    if not assignment:
        raise ResourceNotFoundError(f"Assignment with ID {assignment_id} not found.")

    if assignment.subject.faculty_id != current_faculty.id:
        raise InsufficientPermissionsError()

    if data.title is not None:
        assignment.title = data.title
    if data.description is not None:
        assignment.description = data.description
    if data.instructions is not None:
        assignment.instructions = data.instructions
    if data.due_date is not None:
        assignment.due_date = data.due_date
    if data.max_marks is not None:
        assignment.max_marks = data.max_marks

    db.flush()
    db.refresh(assignment)
    return assignment


def delete_assignment(
    db: Session, assignment_id: int, current_faculty: User
) -> None:
    """Delete an assignment, strictly verifying faculty ownership."""
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

    db.delete(assignment)
    db.flush()
