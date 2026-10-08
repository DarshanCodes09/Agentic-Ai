"""
Faculty and class-level performance analytics service.
Provides subject overview, assignment metrics, class concept mastery, and learning gap reports.
"""

import statistics
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import InsufficientPermissionsError, ResourceNotFoundError
from app.models.assessment import AssessmentResult, AssessmentStatus
from app.models.assignment import Assignment
from app.models.enrollment import Enrollment
from app.models.subject import Subject
from app.models.submission import Submission
from app.models.user import User, UserRole
from app.schemas.analytics import (
    AssignmentAnalyticsResponse,
    ClassConceptAnalyticsResponse,
    ClassLearningGapResponse,
    FacultySubjectAnalyticsResponse,
)
from app.services.analytics.constants import score_to_mastery_level
from app.services.analytics.learning_gap_service import detect_class_learning_gaps
from app.services.analytics.mastery_service import (
    aggregate_concept_mastery,
    get_top_strong_and_weak_concepts,
    parse_mastery_value,
)

EVALUATED_STATUSES = {
    AssessmentStatus.COMPLETED,
    AssessmentStatus.APPROVED,
    AssessmentStatus.MODIFIED,
}


def _verify_subject_faculty_ownership(
    db: Session, subject_id: int, current_faculty: User
) -> Subject:
    """Verify subject exists and is owned by the authenticated faculty user."""
    if current_faculty.role != UserRole.FACULTY:
        raise InsufficientPermissionsError()

    subject = db.scalar(select(Subject).where(Subject.id == subject_id))
    if not subject:
        raise ResourceNotFoundError(f"Subject with ID {subject_id} not found.")

    if subject.faculty_id != current_faculty.id:
        raise InsufficientPermissionsError("You do not own this subject.")

    return subject


def _verify_assignment_faculty_ownership(
    db: Session, assignment_id: int, current_faculty: User
) -> Assignment:
    """Verify assignment exists and its parent subject is owned by authenticated faculty."""
    if current_faculty.role != UserRole.FACULTY:
        raise InsufficientPermissionsError()

    stmt = (
        select(Assignment)
        .options(selectinload(Assignment.subject))
        .where(Assignment.id == assignment_id)
    )
    assignment = db.scalar(stmt)
    if not assignment:
        raise ResourceNotFoundError(f"Assignment with ID {assignment_id} not found.")

    if assignment.subject.faculty_id != current_faculty.id:
        raise InsufficientPermissionsError("You do not own the subject for this assignment.")

    return assignment


def get_faculty_subject_analytics(
    db: Session, subject_id: int, current_faculty: User
) -> FacultySubjectAnalyticsResponse:
    """Compute comprehensive class performance analytics for a faculty subject."""
    subject = _verify_subject_faculty_ownership(db, subject_id, current_faculty)

    # 1. Enrolled student count
    enrolled_count = db.scalar(
        select(func.count(Enrollment.id)).where(Enrollment.subject_id == subject_id)
    ) or 0

    # 2. Assignment count
    assignment_count = db.scalar(
        select(func.count(Assignment.id)).where(Assignment.subject_id == subject_id)
    ) or 0

    # 3. Submissions for this subject
    submissions_stmt = (
        select(Submission)
        .join(Assignment, Submission.assignment_id == Assignment.id)
        .where(Assignment.subject_id == subject_id)
    )
    submissions = list(db.scalars(submissions_stmt).all())
    total_submissions = len(submissions)
    students_with_submissions = len({s.student_id for s in submissions})

    # 4. Evaluated assessments for this subject
    eval_stmt = (
        select(AssessmentResult)
        .join(Submission, AssessmentResult.submission_id == Submission.id)
        .join(Assignment, Submission.assignment_id == Assignment.id)
        .options(
            selectinload(AssessmentResult.submission)
            .selectinload(Submission.assignment)
            .selectinload(Assignment.subject)
        )
        .where(
            Assignment.subject_id == subject_id,
            AssessmentResult.status.in_(EVALUATED_STATUSES),
        )
    )
    assessments = list(db.scalars(eval_stmt).all())
    evaluated_count = len(assessments)

    # Default empty performance distribution
    dist: dict[str, int] = {
        "90-100%": 0,
        "80-89%": 0,
        "70-79%": 0,
        "60-69%": 0,
        "<60%": 0,
    }

    if not assessments:
        return FacultySubjectAnalyticsResponse(
            subject_id=subject.id,
            subject_name=subject.name,
            subject_code=subject.code,
            enrolled_student_count=enrolled_count,
            students_with_submissions=students_with_submissions,
            evaluated_submissions_count=0,
            total_submissions_count=total_submissions,
            assignment_count=assignment_count,
            average_score=0.0,
            average_percentage=0.0,
            highest_percentage=0.0,
            lowest_percentage=0.0,
            median_percentage=0.0,
            completion_rate=0.0,
            performance_distribution=dist,
            strong_concepts=[],
            weak_concepts=[],
        )

    # Percentage stats
    percentages: list[float] = []
    scores: list[float] = []
    for a in assessments:
        scores.append(a.final_score)
        pct = (a.final_score / a.max_score) * 100 if a.max_score > 0 else 0.0
        percentages.append(pct)

        # Binning
        if pct >= 90.0:
            dist["90-100%"] += 1
        elif pct >= 80.0:
            dist["80-89%"] += 1
        elif pct >= 70.0:
            dist["70-79%"] += 1
        elif pct >= 60.0:
            dist["60-69%"] += 1
        else:
            dist["<60%"] += 1

    avg_score = round(sum(scores) / len(scores), 2)
    avg_pct = round(sum(percentages) / len(percentages), 2)
    highest_pct = round(max(percentages), 2)
    lowest_pct = round(min(percentages), 2)
    median_pct = round(statistics.median(percentages), 2)

    # Completion rate: evaluated assessments vs total expected (enrolled_students * assignment_count)
    expected_assessments = enrolled_count * assignment_count
    if expected_assessments > 0:
        completion_rate = round(min(100.0, (evaluated_count / expected_assessments) * 100), 2)
    elif total_submissions > 0:
        completion_rate = round((evaluated_count / total_submissions) * 100, 2)
    else:
        completion_rate = 0.0

    # Concepts
    concept_summaries = aggregate_concept_mastery(assessments)
    strong, weak = get_top_strong_and_weak_concepts(concept_summaries, top_k=5)
    strong_concepts = [c.concept for c in strong]
    weak_concepts = [c.concept for c in weak]

    return FacultySubjectAnalyticsResponse(
        subject_id=subject.id,
        subject_name=subject.name,
        subject_code=subject.code,
        enrolled_student_count=enrolled_count,
        students_with_submissions=students_with_submissions,
        evaluated_submissions_count=evaluated_count,
        total_submissions_count=total_submissions,
        assignment_count=assignment_count,
        average_score=avg_score,
        average_percentage=avg_pct,
        highest_percentage=highest_pct,
        lowest_percentage=lowest_pct,
        median_percentage=median_pct,
        completion_rate=completion_rate,
        performance_distribution=dist,
        strong_concepts=strong_concepts,
        weak_concepts=weak_concepts,
    )


def get_faculty_assignment_analytics(
    db: Session, assignment_id: int, current_faculty: User
) -> AssignmentAnalyticsResponse:
    """Compute performance metrics for a specific assignment."""
    assignment = _verify_assignment_faculty_ownership(db, assignment_id, current_faculty)
    subject = assignment.subject

    enrolled_count = db.scalar(
        select(func.count(Enrollment.id)).where(Enrollment.subject_id == subject.id)
    ) or 0

    submission_count = db.scalar(
        select(func.count(Submission.id)).where(Submission.assignment_id == assignment_id)
    ) or 0

    eval_stmt = (
        select(AssessmentResult)
        .join(Submission, AssessmentResult.submission_id == Submission.id)
        .where(
            Submission.assignment_id == assignment_id,
            AssessmentResult.status.in_(EVALUATED_STATUSES),
        )
    )
    assessments = list(db.scalars(eval_stmt).all())
    evaluated_count = len(assessments)

    if not assessments:
        return AssignmentAnalyticsResponse(
            assignment_id=assignment.id,
            assignment_title=assignment.title,
            subject_id=subject.id,
            subject_name=subject.name,
            max_marks=assignment.max_marks,
            enrolled_count=enrolled_count,
            submission_count=submission_count,
            evaluated_count=0,
            average_score=0.0,
            average_percentage=0.0,
            highest_score=0.0,
            lowest_score=0.0,
            completion_rate=0.0,
        )

    scores = [a.final_score for a in assessments]
    percentages = [(a.final_score / a.max_score) * 100 for a in assessments if a.max_score > 0]

    avg_score = round(sum(scores) / len(scores), 2)
    avg_pct = round(sum(percentages) / len(percentages), 2) if percentages else 0.0
    highest = round(max(scores), 2)
    lowest = round(min(scores), 2)
    completion_rate = round((evaluated_count / enrolled_count) * 100, 2) if enrolled_count > 0 else 0.0

    return AssignmentAnalyticsResponse(
        assignment_id=assignment.id,
        assignment_title=assignment.title,
        subject_id=subject.id,
        subject_name=subject.name,
        max_marks=assignment.max_marks,
        enrolled_count=enrolled_count,
        submission_count=submission_count,
        evaluated_count=evaluated_count,
        average_score=avg_score,
        average_percentage=avg_pct,
        highest_score=highest,
        lowest_score=lowest,
        completion_rate=min(100.0, completion_rate),
    )


def get_faculty_class_concept_analytics(
    db: Session, subject_id: int, current_faculty: User
) -> list[ClassConceptAnalyticsResponse]:
    """Aggregate concept mastery across all students in a faculty subject."""
    _verify_subject_faculty_ownership(db, subject_id, current_faculty)

    eval_stmt = (
        select(AssessmentResult)
        .join(Submission, AssessmentResult.submission_id == Submission.id)
        .join(Assignment, Submission.assignment_id == Assignment.id)
        .options(selectinload(AssessmentResult.submission))
        .where(
            Assignment.subject_id == subject_id,
            AssessmentResult.status.in_(EVALUATED_STATUSES),
        )
    )
    assessments = list(db.scalars(eval_stmt).all())

    concept_stats: dict[str, dict[str, Any]] = {}
    for a in assessments:
        if not a.concept_mastery or not isinstance(a.concept_mastery, list):
            continue

        student_id = a.submission.student_id if a.submission else None
        for item in a.concept_mastery:
            if not isinstance(item, dict):
                continue
            concept = item.get("concept")
            if not concept or not isinstance(concept, str):
                continue
            concept = concept.strip()
            if not concept:
                continue

            score = parse_mastery_value(item.get("mastery_level"))
            if concept not in concept_stats:
                concept_stats[concept] = {"scores": [], "students": set()}

            concept_stats[concept]["scores"].append(score)
            if student_id is not None:
                concept_stats[concept]["students"].add(student_id)

    results: list[ClassConceptAnalyticsResponse] = []
    for concept, data in concept_stats.items():
        scores = data["scores"]
        if not scores:
            continue
        avg = round(sum(scores) / len(scores), 2)
        results.append(
            ClassConceptAnalyticsResponse(
                concept=concept,
                average_mastery=avg,
                mastery_level=score_to_mastery_level(avg),
                assessed_student_count=len(data["students"]),
                total_occurrences=len(scores),
            )
        )

    results.sort(key=lambda x: (x.average_mastery, x.assessed_student_count), reverse=True)
    return results


def get_faculty_class_learning_gaps(
    db: Session, subject_id: int, current_faculty: User
) -> list[ClassLearningGapResponse]:
    """Identify widespread class conceptual gaps in a faculty subject."""
    _verify_subject_faculty_ownership(db, subject_id, current_faculty)

    eval_stmt = (
        select(AssessmentResult)
        .join(Submission, AssessmentResult.submission_id == Submission.id)
        .join(Assignment, Submission.assignment_id == Assignment.id)
        .options(selectinload(AssessmentResult.submission))
        .where(
            Assignment.subject_id == subject_id,
            AssessmentResult.status.in_(EVALUATED_STATUSES),
        )
    )
    assessments = list(db.scalars(eval_stmt).all())
    return detect_class_learning_gaps(assessments)
