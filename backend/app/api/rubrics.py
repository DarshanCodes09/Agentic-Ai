"""
Rubrics & Rubric Items API routes.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_faculty
from app.database.session import get_db
from app.models.user import User
from app.schemas.rubric import (
    RubricItemCreate,
    RubricItemResponse,
    RubricItemUpdate,
    RubricResponse,
    RubricUpdate,
)
from app.services import rubric_service

router = APIRouter(tags=["Rubrics"])


@router.put(
    "/api/rubrics/{rubric_id}",
    response_model=RubricResponse,
    summary="Update rubric (Faculty owner only)",
)
def update_rubric(
    rubric_id: int,
    payload: RubricUpdate,
    current_user: User = Depends(require_faculty),
    db: Session = Depends(get_db),
) -> RubricResponse:
    return rubric_service.update_rubric(db, rubric_id, payload, current_user)


@router.post(
    "/api/rubrics/{rubric_id}/items",
    response_model=RubricItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add criterion item to rubric (Faculty owner only)",
)
def add_rubric_item(
    rubric_id: int,
    payload: RubricItemCreate,
    current_user: User = Depends(require_faculty),
    db: Session = Depends(get_db),
) -> RubricItemResponse:
    return rubric_service.add_rubric_item(db, rubric_id, payload, current_user)


@router.put(
    "/api/rubric-items/{item_id}",
    response_model=RubricItemResponse,
    summary="Update rubric criterion item (Faculty owner only)",
)
def update_rubric_item(
    item_id: int,
    payload: RubricItemUpdate,
    current_user: User = Depends(require_faculty),
    db: Session = Depends(get_db),
) -> RubricItemResponse:
    return rubric_service.update_rubric_item(db, item_id, payload, current_user)


@router.delete(
    "/api/rubric-items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete rubric criterion item (Faculty owner only)",
)
def delete_rubric_item(
    item_id: int,
    current_user: User = Depends(require_faculty),
    db: Session = Depends(get_db),
) -> None:
    rubric_service.delete_rubric_item(db, item_id, current_user)
