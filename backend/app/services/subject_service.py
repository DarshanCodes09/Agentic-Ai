"""
Subject service: handles CRUD operations and faculty ownership checks for subjects.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import (
    DuplicateResourceError,
    InsufficientPermissionsError,
    ResourceNotFoundError,
)
from app.models.subject import Subject
from app.models.user import User, UserRole
from app.schemas.subject import SubjectCreate, SubjectUpdate


def create_subject(db: Session, data: SubjectCreate, faculty_user: User) -> Subject:
    """Create a new subject owned by the authenticated faculty user."""
    if faculty_user.role != UserRole.FACULTY:
        raise InsufficientPermissionsError()

    # Verify code uniqueness
    existing = db.scalar(select(Subject).where(Subject.code == data.code))
    if existing:
        raise DuplicateResourceError(f"Subject with code '{data.code}' already exists.")

    subject = Subject(
        name=data.name,
        code=data.code,
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
