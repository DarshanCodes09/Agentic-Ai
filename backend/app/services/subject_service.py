"""
Subject service: handles CRUD operations and faculty ownership checks for subjects.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import (
    DuplicateResourceError,
    InsufficientPermissionsError,
    ResourceNotFoundError,
)
from app.models.subject import Subject
from app.models.user import User, UserRole
from app.schemas.subject import SubjectCreate, SubjectUpdate


def normalize_subject_code(code: str) -> str:
    """Normalize subject/course codes for consistent lookup and uniqueness."""
    return code.strip().upper()


def create_subject(db: Session, data: SubjectCreate, faculty_user: User) -> Subject:
    """Create a new subject owned by the authenticated faculty user."""
    if faculty_user.role != UserRole.FACULTY:
        raise InsufficientPermissionsError()

    normalized_code = normalize_subject_code(data.code)

    # Verify code uniqueness
    existing = db.scalar(
        select(Subject).where(func.upper(Subject.code) == normalized_code)
    )
    if existing:
        raise DuplicateResourceError(f"Subject with code '{normalized_code}' already exists.")

    subject = Subject(
        name=data.name,
        code=normalized_code,
        description=data.description,
        faculty_id=faculty_user.id,
    )
    db.add(subject)
    db.flush()
    db.refresh(subject)
    return subject


def get_subject_by_id(db: Session, subject_id: int) -> Subject:
    """Get subject by ID or raise 404."""
    stmt = (
        select(Subject)
        .options(selectinload(Subject.faculty))
        .where(Subject.id == subject_id)
    )
    subject = db.scalar(stmt)
    if not subject:
        raise ResourceNotFoundError(f"Subject with ID {subject_id} not found.")
    return subject


def list_all_subjects(db: Session) -> list[Subject]:
    """List all subjects available in the system."""
    stmt = select(Subject).options(selectinload(Subject.faculty)).order_by(Subject.id)
    return list(db.scalars(stmt).all())


def list_student_subjects(db: Session, student_id: int) -> list[Subject]:
    """List only subjects in which the student has an enrollment record."""
    from app.models.enrollment import Enrollment

    stmt = (
        select(Subject)
        .join(Enrollment, Enrollment.subject_id == Subject.id)
        .options(selectinload(Subject.faculty))
        .where(Enrollment.student_id == student_id)
        .order_by(Subject.id)
    )
    return list(db.scalars(stmt).all())


def list_available_subjects_for_student(db: Session, student_id: int) -> list[Subject]:
    """List subjects the student has not joined yet."""
    from app.models.enrollment import Enrollment

    enrolled_subject_ids = select(Enrollment.subject_id).where(
        Enrollment.student_id == student_id
    )
    stmt = (
        select(Subject)
        .options(selectinload(Subject.faculty))
        .where(Subject.id.not_in(enrolled_subject_ids))
        .order_by(Subject.id)
    )
    return list(db.scalars(stmt).all())


def list_faculty_subjects(db: Session, faculty_id: int) -> list[Subject]:
    """List subjects owned by a specific faculty member."""
    stmt = (
        select(Subject)
        .options(selectinload(Subject.faculty))
        .where(Subject.faculty_id == faculty_id)
        .order_by(Subject.id)
    )
    return list(db.scalars(stmt).all())


def update_subject(
    db: Session, subject_id: int, data: SubjectUpdate, current_user: User
) -> Subject:
    """Update subject details, strictly verifying faculty ownership."""
    subject = get_subject_by_id(db, subject_id)
    if subject.faculty_id != current_user.id:
        raise InsufficientPermissionsError()

    if data.name is not None:
        subject.name = data.name
    if data.description is not None:
        subject.description = data.description

    db.flush()
    db.refresh(subject)
    return subject


def delete_subject(db: Session, subject_id: int, current_user: User) -> None:
    """Delete a subject, strictly verifying faculty ownership."""
    subject = get_subject_by_id(db, subject_id)
    if subject.faculty_id != current_user.id:
        raise InsufficientPermissionsError()

    db.delete(subject)
    db.flush()
