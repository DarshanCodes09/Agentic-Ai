"""
Submissions API routes: retrieve submission by ID with strict role access.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_student
from app.database.session import get_db
from app.models.user import User
from app.schemas.submission import SubmissionResponse
from app.services import submission_service

router = APIRouter(prefix="/api/submissions", tags=["Submissions"])


@router.get(
    "",
    response_model=list[SubmissionResponse],
    summary="List current student's submissions (Student owner only)",
)
def list_my_submissions(
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
) -> list[SubmissionResponse]:
    return submission_service.list_student_submissions(db, current_user)


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
