"""
Enrollment service: handles student enrollment and faculty viewing of enrolled students.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import (
    DuplicateResourceError,
    InactiveUserError,
    InsufficientPermissionsError,
    ResourceNotFoundError,
)
from app.models.enrollment import Enrollment
from app.models.subject import Subject
from app.models.user import User, UserRole
from app.services.subject_service import normalize_subject_code


def is_student_enrolled(db: Session, student_id: int, subject_id: int) -> bool:
    """Check whether a student is currently enrolled in a subject."""
    stmt = select(Enrollment).where(
        Enrollment.student_id == student_id,
        Enrollment.subject_id == subject_id,
    )
    return db.scalar(stmt) is not None


def enroll_student(db: Session, subject_id: int, student_user: User) -> Enrollment:
    """Enroll an active student in a subject."""
    if student_user.role != UserRole.STUDENT:
        raise InsufficientPermissionsError()

    if not student_user.is_active:
        raise InactiveUserError()

    # Check that subject exists
    subject = db.scalar(select(Subject).where(Subject.id == subject_id))
    if not subject:
        raise ResourceNotFoundError(f"Subject with ID {subject_id} not found.")

    # Check duplicate enrollment
    if is_student_enrolled(db, student_user.id, subject_id):
        raise DuplicateResourceError("Student is already enrolled in this subject.")

    enrollment = Enrollment(
        student_id=student_user.id,
        subject_id=subject_id,
    )
    db.add(enrollment)
    db.flush()
    db.refresh(enrollment)
    return enrollment


def enroll_student_by_course_code(
    db: Session, course_code: str, student_user: User
) -> Enrollment:
    """Enroll an active student by normalized course/subject code."""
    normalized_code = normalize_subject_code(course_code)
    if not normalized_code:
        raise ResourceNotFoundError("Course code is required.")

    subject = db.scalar(
        select(Subject).where(func.upper(Subject.code) == normalized_code)
    )
    if not subject:
        raise ResourceNotFoundError(f"Course with code '{normalized_code}' not found.")

    return enroll_student(db, subject.id, student_user)


def get_subject_students(
    db: Session, subject_id: int, current_faculty: User
) -> list[Enrollment]:
    """Retrieve all student enrollments for a subject, verifying faculty ownership."""
    subject = db.scalar(select(Subject).where(Subject.id == subject_id))
    if not subject:
        raise ResourceNotFoundError(f"Subject with ID {subject_id} not found.")

    if subject.faculty_id != current_faculty.id:
        raise InsufficientPermissionsError()

    stmt = (
        select(Enrollment)
        .options(selectinload(Enrollment.student))
        .where(Enrollment.subject_id == subject_id)
        .order_by(Enrollment.enrolled_at.desc())
    )
    return list(db.scalars(stmt).all())
