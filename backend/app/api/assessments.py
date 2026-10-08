"""
Assessments API endpoints:
- POST /api/submissions/{submission_id}/assess
- GET /api/submissions/{submission_id}/assessment
- POST /api/assessments/{assessment_id}/approve
- PUT /api/assessments/{assessment_id}
"""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.database.session import get_db
from app.models.user import User
from app.schemas.assessment import (
    AssessmentApprovalRequest,
    AssessmentModificationRequest,
    AssessmentResponse,
)
from app.services.assessment import assessment_service

router = APIRouter(prefix="/api", tags=["Assessments"])


@router.post(
    "/submissions/{submission_id}/assess",
    response_model=AssessmentResponse,
    status_code=status.HTTP_200_OK,
    summary="Trigger AI assessment for a submission (Faculty owning subject only)",
)
async def assess_submission(
    submission_id: int,
    force_reassess: bool = Query(default=False, description="Re-run assessment even if one already exists"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AssessmentResponse:
    """
    Evaluates student submission against assignment questions, rubric criteria,
    and retrieved course knowledge base chunks.
    """
    return await assessment_service.assess_submission(
        db=db,
        submission_id=submission_id,
        current_faculty=current_user,
        force_reassess=force_reassess,
    )


@router.get(
    "/submissions/{submission_id}/assessment",
    response_model=AssessmentResponse,
    summary="Get assessment for a submission (Faculty owner or Student submitter)",
)
def get_submission_assessment(
    submission_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AssessmentResponse:
    """
    Retrieve assessment details, criteria scores, concept mastery, and feedback.
    """
    return assessment_service.get_assessment_by_submission(
        db=db,
        submission_id=submission_id,
        current_user=current_user,
    )


@router.post(
    "/assessments/{assessment_id}/approve",
    response_model=AssessmentResponse,
    summary="Approve AI assessment and finalize grade (Faculty owning subject only)",
)
def approve_assessment(
    assessment_id: int,
    request: AssessmentApprovalRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AssessmentResponse:
    """
    Faculty approves the assessment, locking status to APPROVED and updating submission to EVALUATED.
    """
    notes = request.faculty_notes if request else None
    return assessment_service.approve_assessment(
        db=db,
        assessment_id=assessment_id,
        current_faculty=current_user,
        faculty_notes=notes,
    )


@router.put(
    "/assessments/{assessment_id}",
    response_model=AssessmentResponse,
    summary="Override or modify assessment score (Faculty owning subject only)",
)
def modify_assessment(
    assessment_id: int,
    request: AssessmentModificationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AssessmentResponse:
    """
    Faculty overrides final score and provides justification notes.
    Updates assessment status to MODIFIED and submission to EVALUATED.
    """
    return assessment_service.modify_assessment(
        db=db,
        assessment_id=assessment_id,
        current_faculty=current_user,
        final_score=request.final_score,
        faculty_notes=request.faculty_notes,
    )
