"""
Assignment API routes: assignments, questions, rubrics, and submissions under assignments.
"""

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_faculty, require_student
from app.database.session import get_db
from app.models.user import User
from app.schemas.assignment import AssignmentResponse, AssignmentUpdate
from app.schemas.question import QuestionCreate, QuestionResponse
from app.schemas.rubric import RubricCreate, RubricResponse
from app.schemas.submission import SubmissionResponse
from app.services import (
    assignment_service,
    question_service,
    rubric_service,
    submission_service,
)

router = APIRouter(prefix="/api/assignments", tags=["Assignments"])


@router.get(
    "/{assignment_id}",
    response_model=AssignmentResponse,
    summary="Get assignment by ID (Faculty owner or enrolled student)",
)
def get_assignment(
    assignment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AssignmentResponse:
    return assignment_service.get_assignment_by_id(db, assignment_id, current_user)


@router.put(
    "/{assignment_id}",
    response_model=AssignmentResponse,
    summary="Update assignment (Faculty owner only)",
)
def update_assignment(
    assignment_id: int,
    payload: AssignmentUpdate,
    current_user: User = Depends(require_faculty),
    db: Session = Depends(get_db),
) -> AssignmentResponse:
    return assignment_service.update_assignment(db, assignment_id, payload, current_user)


@router.delete(
    "/{assignment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete assignment (Faculty owner only)",
)
def delete_assignment(
    assignment_id: int,
    current_user: User = Depends(require_faculty),
    db: Session = Depends(get_db),
) -> None:
    assignment_service.delete_assignment(db, assignment_id, current_user)


# ---------------------------------------------------------------------------
# Questions for Assignment
# ---------------------------------------------------------------------------

@router.post(
    "/{assignment_id}/questions",
    response_model=QuestionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add question to assignment (Faculty owner only)",
)
def add_question(
    assignment_id: int,
    payload: QuestionCreate,
    current_user: User = Depends(require_faculty),
    db: Session = Depends(get_db),
) -> QuestionResponse:
    return question_service.create_question(db, assignment_id, payload, current_user)


@router.get(
    "/{assignment_id}/questions",
    response_model=list[QuestionResponse],
    summary="List assignment questions (Faculty owner or enrolled student)",
)
def list_questions(
    assignment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[QuestionResponse]:
    return question_service.list_assignment_questions(db, assignment_id, current_user)


# ---------------------------------------------------------------------------
# Rubric for Assignment
# ---------------------------------------------------------------------------

@router.post(
    "/{assignment_id}/rubric",
    response_model=RubricResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create rubric for assignment (Faculty owner only)",
)
def create_rubric(
    assignment_id: int,
    payload: RubricCreate,
    current_user: User = Depends(require_faculty),
    db: Session = Depends(get_db),
) -> RubricResponse:
    return rubric_service.create_rubric(db, assignment_id, payload, current_user)


@router.get(
    "/{assignment_id}/rubric",
    response_model=RubricResponse,
    summary="Get assignment rubric (Faculty owner or enrolled student)",
)
def get_rubric(
    assignment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RubricResponse:
    return rubric_service.get_assignment_rubric(db, assignment_id, current_user)


# ---------------------------------------------------------------------------
# Submissions for Assignment
# ---------------------------------------------------------------------------

@router.post(
    "/{assignment_id}/submit",
    response_model=SubmissionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit student work (text or file, Students only)",
)
async def submit_assignment(
    assignment_id: int,
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
        # Fallback to form/json parsing
        try:
            body = await request.json()
            submission_text = body.get("submission_text")
        except Exception:
            pass

    return await submission_service.submit_assignment(
        db, assignment_id, current_user, submission_text=submission_text, file=file
    )


@router.get(
    "/{assignment_id}/submissions",
    response_model=list[SubmissionResponse],
    summary="List all submissions for assignment (Faculty owner only)",
)
def list_submissions(
    assignment_id: int,
    current_user: User = Depends(require_faculty),
    db: Session = Depends(get_db),
) -> list[SubmissionResponse]:
    return submission_service.list_assignment_submissions(db, assignment_id, current_user)
