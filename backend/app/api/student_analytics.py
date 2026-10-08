"""
Student Analytics API endpoints:
- GET /api/students/me/analytics
- GET /api/students/me/analytics/subjects
- GET /api/students/me/analytics/concepts
- GET /api/students/me/analytics/gaps
- GET /api/students/me/analytics/trends
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import require_student
from app.database.session import get_db
from app.models.user import User
from app.schemas.analytics import (
    ConceptMasterySummary,
    LearningGapItem,
    PerformanceTrendItem,
    StudentOverallAnalyticsResponse,
    SubjectPerformanceResponse,
)
from app.services.analytics import student_analytics_service

router = APIRouter(prefix="/api/students/me/analytics", tags=["Student Analytics"])


@router.get(
    "",
    response_model=StudentOverallAnalyticsResponse,
    summary="Get overall student performance analytics (Authenticated student only)",
)
def get_overall_analytics(
    current_student: User = Depends(require_student),
    db: Session = Depends(get_db),
) -> StudentOverallAnalyticsResponse:
    """Return comprehensive academic metrics, score summaries, and top concepts for student."""
    return student_analytics_service.get_student_overall_analytics(
        db=db, student_id=current_student.id
    )


@router.get(
    "/subjects",
    response_model=list[SubjectPerformanceResponse],
    summary="Get subject-wise performance breakdown (Authenticated student only)",
)
def get_subject_performance(
    current_student: User = Depends(require_student),
    db: Session = Depends(get_db),
) -> list[SubjectPerformanceResponse]:
    """Return academic performance broken down by enrolled subjects."""
    return student_analytics_service.get_student_subject_performance(
        db=db, student_id=current_student.id
    )


@router.get(
    "/concepts",
    response_model=list[ConceptMasterySummary],
    summary="Get concept mastery breakdown (Authenticated student only)",
)
def get_concept_mastery(
    current_student: User = Depends(require_student),
    db: Session = Depends(get_db),
) -> list[ConceptMasterySummary]:
    """Return aggregated concept mastery scores and levels across all evaluated assignments."""
    return student_analytics_service.get_student_concept_mastery(
        db=db, student_id=current_student.id
    )


@router.get(
    "/gaps",
    response_model=list[LearningGapItem],
    summary="Get identified learning gaps and misconceptions (Authenticated student only)",
)
def get_learning_gaps(
    current_student: User = Depends(require_student),
    db: Session = Depends(get_db),
) -> list[LearningGapItem]:
    """Return identified conceptual weaknesses, missing topics, and evidence citations."""
    return student_analytics_service.get_student_learning_gaps(
        db=db, student_id=current_student.id
    )


@router.get(
    "/trends",
    response_model=list[PerformanceTrendItem],
    summary="Get chronological performance trends (Authenticated student only)",
)
def get_performance_trends(
    current_student: User = Depends(require_student),
    db: Session = Depends(get_db),
) -> list[PerformanceTrendItem]:
    """Return chronological sequence of evaluated scores for progression charting."""
    return student_analytics_service.get_student_performance_trends(
        db=db, student_id=current_student.id
    )
