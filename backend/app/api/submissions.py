"""
Submissions API routes: retrieve submission by ID with strict role access.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.database.session import get_db
from app.models.user import User
from app.schemas.submission import SubmissionResponse
from app.services import submission_service

router = APIRouter(prefix="/api/submissions", tags=["Submissions"])


@router.get(
    "/{submission_id}",
    response_model=SubmissionResponse,
    summary="Get submission by ID (Student owner or Assignment faculty only)",
)
def get_submission(
    submission_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SubmissionResponse:
    return submission_service.get_submission_by_id(db, submission_id, current_user)
