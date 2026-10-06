"""
Question service: handles questions for assignments and verifies permissions.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import (
    DuplicateResourceError,
    InsufficientPermissionsError,
    NotEnrolledError,
    ResourceNotFoundError,
)
from app.models.assignment import Assignment
from app.models.question import Question
from app.models.user import User, UserRole
from app.schemas.question import QuestionCreate, QuestionUpdate
from app.services.enrollment_service import is_student_enrolled


def create_question(
    db: Session, assignment_id: int, data: QuestionCreate, current_faculty: User
) -> Question:
    """Create a new question for an assignment owned by current faculty."""
    assignment = db.scalar(
        select(Assignment)
        .options(selectinload(Assignment.subject))
        .where(Assignment.id == assignment_id)
    )
    if not assignment:
        raise ResourceNotFoundError(f"Assignment with ID {assignment_id} not found.")

    if assignment.subject.faculty_id != current_faculty.id:
        raise InsufficientPermissionsError()

    # Check question_number uniqueness within assignment
    existing = db.scalar(
        select(Question).where(
            Question.assignment_id == assignment_id,
            Question.question_number == data.question_number,
        )
    )
    if existing:
        raise DuplicateResourceError(
            f"Question number {data.question_number} already exists for this assignment."
        )

    question = Question(
        assignment_id=assignment_id,
        question_number=data.question_number,
        question_text=data.question_text,
        marks=data.marks,
        expected_concepts=data.expected_concepts or [],
    )
    db.add(question)
    db.flush()
    db.refresh(question)
    return question


def list_assignment_questions(
    db: Session, assignment_id: int, current_user: User
) -> list[Question]:
    """List all questions for an assignment."""
    assignment = db.scalar(
        select(Assignment)
        .options(selectinload(Assignment.subject))
        .where(Assignment.id == assignment_id)
    )
    if not assignment:
        raise ResourceNotFoundError(f"Assignment with ID {assignment_id} not found.")

    if current_user.role == UserRole.FACULTY:
        if assignment.subject.faculty_id != current_user.id:
            raise InsufficientPermissionsError()
    else:
        if not is_student_enrolled(db, current_user.id, assignment.subject_id):
            raise NotEnrolledError()

    stmt = (
        select(Question)
        .where(Question.assignment_id == assignment_id)
        .order_by(Question.question_number.asc())
    )
    return list(db.scalars(stmt).all())


def update_question(
    db: Session, question_id: int, data: QuestionUpdate, current_faculty: User
) -> Question:
    """Update question, verifying faculty ownership."""
    stmt = (
        select(Question)
        .options(
            selectinload(Question.assignment).selectinload(Assignment.subject)
        )
        .where(Question.id == question_id)
    )
    question = db.scalar(stmt)
    if not question:
        raise ResourceNotFoundError(f"Question with ID {question_id} not found.")

    if question.assignment.subject.faculty_id != current_faculty.id:
        raise InsufficientPermissionsError()

    if data.question_number is not None and data.question_number != question.question_number:
        existing = db.scalar(
            select(Question).where(
                Question.assignment_id == question.assignment_id,
                Question.question_number == data.question_number,
            )
        )
        if existing:
            raise DuplicateResourceError(
                f"Question number {data.question_number} already exists for this assignment."
            )
        question.question_number = data.question_number

    if data.question_text is not None:
        question.question_text = data.question_text
    if data.marks is not None:
        question.marks = data.marks
    if data.expected_concepts is not None:
        question.expected_concepts = data.expected_concepts

    db.flush()
    db.refresh(question)
    return question


def delete_question(db: Session, question_id: int, current_faculty: User) -> None:
    """Delete question, verifying faculty ownership."""
    stmt = (
        select(Question)
        .options(
            selectinload(Question.assignment).selectinload(Assignment.subject)
        )
        .where(Question.id == question_id)
    )
    question = db.scalar(stmt)
    if not question:
        raise ResourceNotFoundError(f"Question with ID {question_id} not found.")

    if question.assignment.subject.faculty_id != current_faculty.id:
        raise InsufficientPermissionsError()

    db.delete(question)
    db.flush()
