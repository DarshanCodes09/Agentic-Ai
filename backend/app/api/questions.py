"""
Questions API routes: update and delete individual questions.
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_faculty
from app.database.session import get_db
from app.models.user import User
from app.schemas.question import QuestionResponse, QuestionUpdate
from app.services import question_service

router = APIRouter(prefix="/api/questions", tags=["Questions"])


@router.put(
    "/{question_id}",
    response_model=QuestionResponse,
    summary="Update question (Faculty owner only)",
)
def update_question(
    question_id: int,
    payload: QuestionUpdate,
    current_user: User = Depends(require_faculty),
    db: Session = Depends(get_db),
) -> QuestionResponse:
    return question_service.update_question(db, question_id, payload, current_user)


@router.delete(
    "/{question_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete question (Faculty owner only)",
)
def delete_question(
    question_id: int,
    current_user: User = Depends(require_faculty),
    db: Session = Depends(get_db),
) -> None:
    question_service.delete_question(db, question_id, current_user)
