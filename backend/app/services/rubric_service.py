"""
Rubric service: handles rubrics and rubric items for assignments.
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
from app.models.rubric import Rubric
from app.models.rubric_item import RubricItem
from app.models.user import User, UserRole
from app.schemas.rubric import (
    RubricCreate,
    RubricItemCreate,
    RubricItemUpdate,
    RubricUpdate,
)
from app.services.enrollment_service import is_student_enrolled


def create_rubric(
    db: Session, assignment_id: int, data: RubricCreate, current_faculty: User
) -> Rubric:
    """Create a rubric for an assignment, verifying faculty ownership."""
    assignment = db.scalar(
        select(Assignment)
        .options(selectinload(Assignment.subject))
        .where(Assignment.id == assignment_id)
    )
    if not assignment:
        raise ResourceNotFoundError(f"Assignment with ID {assignment_id} not found.")

    if assignment.subject.faculty_id != current_faculty.id:
        raise InsufficientPermissionsError()

    # Check if a rubric already exists for this assignment
    existing = db.scalar(select(Rubric).where(Rubric.assignment_id == assignment_id))
    if existing:
        raise DuplicateResourceError("A rubric already exists for this assignment.")

    rubric = Rubric(
        assignment_id=assignment_id,
        name=data.name,
        description=data.description,
    )
    db.add(rubric)
    db.flush()

    if data.items:
        for item_data in data.items:
            item = RubricItem(
                rubric_id=rubric.id,
                criterion=item_data.criterion,
                description=item_data.description,
                max_marks=item_data.max_marks,
            )
            db.add(item)
        db.flush()

    db.refresh(rubric)
    return rubric


def get_assignment_rubric(
    db: Session, assignment_id: int, current_user: User
) -> Rubric:
    """Get the rubric for an assignment."""
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
        select(Rubric)
        .options(selectinload(Rubric.items))
        .where(Rubric.assignment_id == assignment_id)
    )
    rubric = db.scalar(stmt)
    if not rubric:
        raise ResourceNotFoundError("No rubric found for this assignment.")
    return rubric


def update_rubric(
    db: Session, rubric_id: int, data: RubricUpdate, current_faculty: User
) -> Rubric:
    """Update rubric, verifying faculty ownership."""
    stmt = (
        select(Rubric)
        .options(
            selectinload(Rubric.assignment).selectinload(Assignment.subject),
            selectinload(Rubric.items),
        )
        .where(Rubric.id == rubric_id)
    )
    rubric = db.scalar(stmt)
    if not rubric:
        raise ResourceNotFoundError(f"Rubric with ID {rubric_id} not found.")

    if rubric.assignment.subject.faculty_id != current_faculty.id:
        raise InsufficientPermissionsError()

    if data.name is not None:
        rubric.name = data.name
    if data.description is not None:
        rubric.description = data.description

    db.flush()
    db.refresh(rubric)
    return rubric


def add_rubric_item(
    db: Session, rubric_id: int, data: RubricItemCreate, current_faculty: User
) -> RubricItem:
    """Add a grading criterion item to a rubric."""
    stmt = (
        select(Rubric)
        .options(
            selectinload(Rubric.assignment).selectinload(Assignment.subject)
        )
        .where(Rubric.id == rubric_id)
    )
    rubric = db.scalar(stmt)
    if not rubric:
        raise ResourceNotFoundError(f"Rubric with ID {rubric_id} not found.")

    if rubric.assignment.subject.faculty_id != current_faculty.id:
        raise InsufficientPermissionsError()

    item = RubricItem(
        rubric_id=rubric_id,
        criterion=data.criterion,
        description=data.description,
        max_marks=data.max_marks,
    )
    db.add(item)
    db.flush()
    db.refresh(item)
    return item


def update_rubric_item(
    db: Session, item_id: int, data: RubricItemUpdate, current_faculty: User
) -> RubricItem:
    """Update a rubric item."""
    stmt = (
        select(RubricItem)
        .options(
            selectinload(RubricItem.rubric)
            .selectinload(Rubric.assignment)
            .selectinload(Assignment.subject)
        )
        .where(RubricItem.id == item_id)
    )
    item = db.scalar(stmt)
    if not item:
        raise ResourceNotFoundError(f"Rubric item with ID {item_id} not found.")

    if item.rubric.assignment.subject.faculty_id != current_faculty.id:
        raise InsufficientPermissionsError()

    if data.criterion is not None:
        item.criterion = data.criterion
    if data.description is not None:
        item.description = data.description
    if data.max_marks is not None:
        item.max_marks = data.max_marks

    db.flush()
    db.refresh(item)
    return item


def delete_rubric_item(db: Session, item_id: int, current_faculty: User) -> None:
    """Delete a rubric item."""
    stmt = (
        select(RubricItem)
        .options(
            selectinload(RubricItem.rubric)
            .selectinload(Rubric.assignment)
            .selectinload(Assignment.subject)
        )
        .where(RubricItem.id == item_id)
    )
    item = db.scalar(stmt)
    if not item:
        raise ResourceNotFoundError(f"Rubric item with ID {item_id} not found.")

    if item.rubric.assignment.subject.faculty_id != current_faculty.id:
        raise InsufficientPermissionsError()

    db.delete(item)
    db.flush()
