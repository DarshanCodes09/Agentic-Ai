"""
Student performance analytics service.
Calculates overall metrics, subject breakdown, concept mastery, learning gaps, and chronological trends.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.assessment import AssessmentResult, AssessmentStatus
from app.models.assignment import Assignment
from app.models.enrollment import Enrollment
from app.models.subject import Subject
from app.models.submission import Submission
from app.schemas.analytics import (
    ConceptMasterySummary,
    LearningGapItem,
    PerformanceTrendItem,
    StudentOverallAnalyticsResponse,
    SubjectPerformanceResponse,
)
from app.services.analytics.learning_gap_service import detect_student_learning_gaps
from app.services.analytics.mastery_service import (
    aggregate_concept_mastery,
    get_top_strong_and_weak_concepts,
)

EVALUATED_STATUSES = {
    AssessmentStatus.COMPLETED,
    AssessmentStatus.APPROVED,
    AssessmentStatus.MODIFIED,
}


def get_student_evaluated_assessments(
    db: Session, student_id: int
) -> list[AssessmentResult]:
    """
    Fetch all successfully evaluated assessments for a student.
    Eagerly loads submissions, assignments, and subjects to prevent N+1 queries.
    """
    stmt = (
        select(AssessmentResult)
        .join(AssessmentResult.submission)
        .options(
            selectinload(AssessmentResult.submission)
            .selectinload(Submission.assignment)
            .selectinload(Assignment.subject)
        )
        .where(
            Submission.student_id == student_id,
            AssessmentResult.status.in_(EVALUATED_STATUSES),
        )
        .order_by(AssessmentResult.created_at.asc())
    )
    return list(db.scalars(stmt).all())


def get_student_overall_analytics(
    db: Session, student_id: int
) -> StudentOverallAnalyticsResponse:
    """Calculate overall academic performance for a student."""
    assessments = get_student_evaluated_assessments(db, student_id)

    # Count enrolled subjects
    enrolled_count = (
        db.scalar(
            select(Enrollment)
            .where(Enrollment.student_id == student_id)
        )
        is not None
    )
    enrolled_subjects_stmt = select(Enrollment.subject_id).where(Enrollment.student_id == student_id)
    enrolled_subject_ids = list(db.scalars(enrolled_subjects_stmt).all())
    enrolled_count = len(enrolled_subject_ids)

    if not assessments:
        return StudentOverallAnalyticsResponse(
            student_id=student_id,
            total_assessments_evaluated=0,
            total_marks_obtained=0.0,
            total_max_marks=0.0,
            overall_percentage=0.0,
            average_score=0.0,
            average_confidence=None,
            enrolled_subjects_count=enrolled_count,
            strongest_concepts=[],
            weakest_concepts=[],
        )

    total_obtained = sum(a.final_score for a in assessments)
    total_max = sum(a.max_score for a in assessments)
    overall_pct = round((total_obtained / total_max) * 100, 2) if total_max > 0 else 0.0
    avg_score = round(total_obtained / len(assessments), 2)

    mastery_summaries = aggregate_concept_mastery(assessments)
    strongest, weakest = get_top_strong_and_weak_concepts(mastery_summaries, top_k=5)

    return StudentOverallAnalyticsResponse(
        student_id=student_id,
        total_assessments_evaluated=len(assessments),
        total_marks_obtained=round(total_obtained, 2),
        total_max_marks=round(total_max, 2),
        overall_percentage=overall_pct,
        average_score=avg_score,
        average_confidence=1.0,
        enrolled_subjects_count=enrolled_count,
        strongest_concepts=strongest,
        weakest_concepts=weakest,
    )


def get_student_subject_performance(
    db: Session, student_id: int
) -> list[SubjectPerformanceResponse]:
    """Calculate subject-wise performance breakdown for all enrolled subjects."""
    # 1. Fetch all subjects student is enrolled in
    enrolled_subjects_stmt = (
        select(Subject)
        .join(Enrollment, Enrollment.subject_id == Subject.id)
        .where(Enrollment.student_id == student_id)
        .order_by(Subject.name.asc())
    )
    enrolled_subjects = list(db.scalars(enrolled_subjects_stmt).all())

    # 2. Fetch all student evaluated assessments
    assessments = get_student_evaluated_assessments(db, student_id)

    # Group assessments by subject_id
    subject_assessments_map: dict[int, list[AssessmentResult]] = {}
    for a in assessments:
        if a.submission and a.submission.assignment:
            sub_id = a.submission.assignment.subject_id
            subject_assessments_map.setdefault(sub_id, []).append(a)

    responses: list[SubjectPerformanceResponse] = []
    for subject in enrolled_subjects:
        sub_evals = subject_assessments_map.get(subject.id, [])
        count = len(sub_evals)
        total_score = round(sum(a.final_score for a in sub_evals), 2)
        total_max = round(sum(a.max_score for a in sub_evals), 2)
        pct = round((total_score / total_max) * 100, 2) if total_max > 0 else 0.0
        avg_score = round(total_score / count, 2) if count > 0 else 0.0

        responses.append(
            SubjectPerformanceResponse(
                subject_id=subject.id,
                subject_name=subject.name,
                subject_code=subject.code,
                assessments_count=count,
                total_score=total_score,
                total_max_score=total_max,
                percentage=pct,
                average_score=avg_score,
            )
        )

    return responses


def get_student_concept_mastery(
    db: Session, student_id: int
) -> list[ConceptMasterySummary]:
    """Return aggregated concept mastery for a student."""
    assessments = get_student_evaluated_assessments(db, student_id)
    return aggregate_concept_mastery(assessments)


def get_student_learning_gaps(
    db: Session, student_id: int
) -> list[LearningGapItem]:
    """Return identified learning gaps and misconceptions for a student."""
    assessments = get_student_evaluated_assessments(db, student_id)
    return detect_student_learning_gaps(assessments)


def get_student_performance_trends(
    db: Session, student_id: int
) -> list[PerformanceTrendItem]:
    """Return chronological sequence of evaluated assessments for progress tracking."""
    assessments = get_student_evaluated_assessments(db, student_id)
    trends: list[PerformanceTrendItem] = []

    for a in assessments:
        if not a.submission or not a.submission.assignment:
            continue

        asg = a.submission.assignment
        subject = asg.subject
        pct = round((a.final_score / a.max_score) * 100, 2) if a.max_score > 0 else 0.0

        trends.append(
            PerformanceTrendItem(
                assessment_id=a.id,
                assignment_id=asg.id,
                assignment_title=asg.title,
                subject_id=subject.id if subject else 0,
                subject_name=subject.name if subject else "Unknown",
                score=round(a.final_score, 2),
                max_score=round(a.max_score, 2),
                percentage=pct,
                evaluated_at=a.created_at,
            )
        )

    return trends
