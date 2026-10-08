"""
Deterministic learning gap detection service.
Identifies weak concepts, missing knowledge, and recurring student misconceptions.
"""

from typing import Any
from sqlalchemy.orm import Session

from app.models.assessment import AssessmentResult, AssessmentStatus
from app.models.submission import Submission
from app.schemas.analytics import ClassLearningGapResponse, LearningGapItem
from app.services.analytics.constants import (
    GAP_SEVERITY_MEDIUM_THRESHOLD,
    score_to_gap_severity,
)
from app.services.analytics.mastery_service import parse_mastery_value


def detect_student_learning_gaps(
    assessments: list[AssessmentResult],
) -> list[LearningGapItem]:
    """
    Detect learning gaps across a student's evaluated assessments.

    A concept is flagged as a learning gap if its average mastery score is below
    GAP_SEVERITY_MEDIUM_THRESHOLD (< 0.60) or has repeated deficiencies.
    """
    valid_statuses = {
        AssessmentStatus.COMPLETED,
        AssessmentStatus.APPROVED,
        AssessmentStatus.MODIFIED,
    }

    # (concept, subject_id, subject_name) -> {scores: list[float], evidences: list[str]}
    gap_tracker: dict[tuple[str, int | None, str | None], dict[str, list[Any]]] = {}

    for assessment in assessments:
        if assessment.status not in valid_statuses or not assessment.concept_mastery:
            continue

        sub: Submission | None = assessment.submission
        subject_id = sub.assignment.subject_id if sub and sub.assignment else None
        subject_name = sub.assignment.subject.name if sub and sub.assignment and sub.assignment.subject else None

        raw_items = assessment.concept_mastery
        if not isinstance(raw_items, list):
            continue

        for item in raw_items:
            if not isinstance(item, dict):
                continue

            concept = item.get("concept")
            if not concept or not isinstance(concept, str):
                continue
            concept = concept.strip()
            if not concept:
                continue

            raw_level = item.get("mastery_level")
            score = parse_mastery_value(raw_level)

            evidence = item.get("evidence")
            evidence_str = str(evidence).strip() if evidence else ""

            key = (concept, subject_id, subject_name)
            if key not in gap_tracker:
                gap_tracker[key] = {"scores": [], "evidences": []}

            gap_tracker[key]["scores"].append(score)
            if evidence_str and evidence_str not in gap_tracker[key]["evidences"]:
                gap_tracker[key]["evidences"].append(evidence_str)

    learning_gaps: list[LearningGapItem] = []
    for (concept, subject_id, subject_name), data in gap_tracker.items():
        scores = data["scores"]
        if not scores:
            continue

        avg_score = round(sum(scores) / len(scores), 2)
        # Flag as gap if mastery is below DEVELOPING threshold (< 0.60)
        if avg_score < GAP_SEVERITY_MEDIUM_THRESHOLD:
            severity = score_to_gap_severity(avg_score)
            learning_gaps.append(
                LearningGapItem(
                    concept=concept,
                    subject_id=subject_id,
                    subject_name=subject_name,
                    severity=severity,
                    mastery_score=avg_score,
                    evidence=data["evidences"][:5],
                    occurrence_count=len(scores),
                )
            )

    # Sort gaps by lowest mastery score first (highest severity first), then by occurrence count desc
    learning_gaps.sort(key=lambda g: (g.mastery_score, -g.occurrence_count))
    return learning_gaps


def detect_class_learning_gaps(
    assessments: list[AssessmentResult],
) -> list[ClassLearningGapResponse]:
    """
    Detect subject-level learning gaps across all students in a class.
    """
    valid_statuses = {
        AssessmentStatus.COMPLETED,
        AssessmentStatus.APPROVED,
        AssessmentStatus.MODIFIED,
    }

    # concept -> {scores: list[float], students: set[int], evidences: list[str]}
    concept_stats: dict[str, dict[str, Any]] = {}

    for assessment in assessments:
        if assessment.status not in valid_statuses or not assessment.concept_mastery:
            continue

        student_id = assessment.submission.student_id if assessment.submission else None
        raw_items = assessment.concept_mastery
        if not isinstance(raw_items, list):
            continue

        for item in raw_items:
            if not isinstance(item, dict):
                continue

            concept = item.get("concept")
            if not concept or not isinstance(concept, str):
                continue
            concept = concept.strip()
            if not concept:
                continue

            score = parse_mastery_value(item.get("mastery_level"))
            evidence = item.get("evidence")
            evidence_str = str(evidence).strip() if evidence else ""

            if concept not in concept_stats:
                concept_stats[concept] = {
                    "scores": [],
                    "students_with_gaps": set(),
                    "evidences": [],
                }

            concept_stats[concept]["scores"].append(score)
            if score < GAP_SEVERITY_MEDIUM_THRESHOLD and student_id is not None:
                concept_stats[concept]["students_with_gaps"].add(student_id)

            if evidence_str and evidence_str not in concept_stats[concept]["evidences"]:
                concept_stats[concept]["evidences"].append(evidence_str)

    class_gaps: list[ClassLearningGapResponse] = []
    for concept, data in concept_stats.items():
        scores = data["scores"]
        if not scores:
            continue

        avg_score = round(sum(scores) / len(scores), 2)
        # Include concept if class average is below threshold OR at least one student has gap
        affected_count = len(data["students_with_gaps"])
        if avg_score < GAP_SEVERITY_MEDIUM_THRESHOLD or affected_count > 0:
            severity = score_to_gap_severity(avg_score)
            class_gaps.append(
                ClassLearningGapResponse(
                    concept=concept,
                    average_mastery=avg_score,
                    affected_student_count=affected_count,
                    total_occurrences=len(scores),
                    severity=severity,
                    sample_evidence=data["evidences"][:5],
                )
            )

    # Sort class gaps by lowest average mastery first
    class_gaps.sort(key=lambda g: (g.average_mastery, -g.affected_student_count))
    return class_gaps
