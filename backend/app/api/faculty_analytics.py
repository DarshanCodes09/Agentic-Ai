"""
Faculty Analytics API endpoints:
- GET /api/faculty/subjects/{subject_id}/analytics
- GET /api/faculty/subjects/{subject_id}/analytics/concepts
- GET /api/faculty/subjects/{subject_id}/analytics/gaps
- GET /api/faculty/assignments/{assignment_id}/analytics
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import require_faculty
from app.database.session import get_db
from app.models.user import User
from app.schemas.analytics import (
    AssignmentAnalyticsResponse,
    ClassConceptAnalyticsResponse,
    ClassLearningGapResponse,
    FacultySubjectAnalyticsResponse,
)
from app.services.analytics import faculty_analytics_service

router = APIRouter(prefix="/api/faculty", tags=["Faculty Analytics"])


@router.get(
    "/subjects/{subject_id}/analytics",
    response_model=FacultySubjectAnalyticsResponse,
    summary="Get class performance analytics for a subject (Faculty owner only)",
)
def get_subject_analytics(
    subject_id: int,
    current_faculty: User = Depends(require_faculty),
    db: Session = Depends(get_db),
) -> FacultySubjectAnalyticsResponse:
    """Return class summary, score distributions, completion rate, and top concepts for a subject."""
    return faculty_analytics_service.get_faculty_subject_analytics(
        db=db, subject_id=subject_id, current_faculty=current_faculty
    )


@router.get(
    "/subjects/{subject_id}/analytics/concepts",
    response_model=list[ClassConceptAnalyticsResponse],
    summary="Get aggregated class concept mastery for a subject (Faculty owner only)",
)
def get_class_concept_analytics(
    subject_id: int,
    current_faculty: User = Depends(require_faculty),
    db: Session = Depends(get_db),
) -> list[ClassConceptAnalyticsResponse]:
    """Return aggregated student mastery across all academic concepts taught in this subject."""
    return faculty_analytics_service.get_faculty_class_concept_analytics(
        db=db, subject_id=subject_id, current_faculty=current_faculty
    )


@router.get(
    "/subjects/{subject_id}/analytics/gaps",
    response_model=list[ClassLearningGapResponse],
    summary="Get class-wide learning gaps and vulnerable concepts (Faculty owner only)",
)
def get_class_learning_gaps(
    subject_id: int,
    current_faculty: User = Depends(require_faculty),
    db: Session = Depends(get_db),
) -> list[ClassLearningGapResponse]:
    """Return concepts with widespread student struggle to guide instructional interventions."""
    return faculty_analytics_service.get_faculty_class_learning_gaps(
        db=db, subject_id=subject_id, current_faculty=current_faculty
    )


@router.get(
    "/assignments/{assignment_id}/analytics",
    response_model=AssignmentAnalyticsResponse,
    summary="Get performance analytics for an assignment (Faculty owner only)",
)
def get_assignment_analytics(
    assignment_id: int,
    current_faculty: User = Depends(require_faculty),
    db: Session = Depends(get_db),
) -> AssignmentAnalyticsResponse:
    """Return assignment completion rates, score averages, and submission distribution."""
    return faculty_analytics_service.get_faculty_assignment_analytics(
        db=db, assignment_id=assignment_id, current_faculty=current_faculty
    )
