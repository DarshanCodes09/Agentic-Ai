"""
Submissions API routes: retrieve submission by ID with strict role access.
"""

from fastapi import APIRouter, Depends, Request, status
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


@router.get(
    "/{submission_id}/file",
    summary="Download or preview submitted file (Student owner or Assignment faculty only)",
)
def get_submission_file(
    submission_id: int,
    inline: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return submission_service.get_submission_file_response(
        db=db,
        submission_id=submission_id,
        current_user=current_user,
        inline=inline,
    )


@router.put(
    "/{submission_id}",
    response_model=SubmissionResponse,
    summary="Replace submission with updated text or file before deadline (Student owner only)",
)
async def replace_submission(
    submission_id: int,
    request: Request,
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
) -> SubmissionResponse:
    content_type = request.headers.get("content-type", "")
    submission_text = None
    file = None

    if "application/json" in content_type:
        body = await request.json()
        submission_text = body.get("submission_text")
    elif "multipart/form-data" in content_type:
        form = await request.form()
        submission_text = form.get("submission_text")
        form_file = form.get("file")
        if form_file and hasattr(form_file, "filename") and form_file.filename:
            file = form_file
    else:
        try:
            body = await request.json()
            submission_text = body.get("submission_text")
        except Exception:
            pass

    return await submission_service.replace_submission(
        db=db,
        submission_id=submission_id,
        student_user=current_user,
        submission_text=submission_text,
        file=file,
    )


@router.delete(
    "/{submission_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Withdraw submission before deadline and evaluation (Student owner only)",
)
def withdraw_submission(
    submission_id: int,
    current_user: User = Depends(require_student),
    db: Session = Depends(get_db),
) -> None:
    submission_service.withdraw_submission(
        db=db,
        submission_id=submission_id,
        student_user=current_user,
    )
