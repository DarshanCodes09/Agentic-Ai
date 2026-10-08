"""
Mastery calculation and concept aggregation service.
Processes Phase 4 concept_mastery assessment records deterministically.
"""

from typing import Any

from app.models.assessment import AssessmentResult, AssessmentStatus
from app.schemas.analytics import ConceptMasterySummary
from app.services.analytics.constants import (
    DEFAULT_TOP_CONCEPTS_COUNT,
    MASTERY_LEVEL_WEIGHTS,
    score_to_mastery_level,
)


def parse_mastery_value(raw_val: Any) -> float:
    """Safely convert raw mastery level string or numeric value into [0.0, 1.0] float."""
    if isinstance(raw_val, (int, float)):
        return max(0.0, min(float(raw_val), 1.0))

    if isinstance(raw_val, str):
        clean_key = raw_val.strip().upper()
        if clean_key in MASTERY_LEVEL_WEIGHTS:
            return MASTERY_LEVEL_WEIGHTS[clean_key]
        try:
            val = float(clean_key)
            return max(0.0, min(val, 1.0))
        except ValueError:
            pass

    return MASTERY_LEVEL_WEIGHTS["NOT_DEMONSTRATED"]


def aggregate_concept_mastery(
    assessments: list[AssessmentResult],
) -> list[ConceptMasterySummary]:
    """
    Aggregate concept_mastery records across evaluated assessments.

    Args:
        assessments: Evaluated AssessmentResult instances.

    Returns:
        List of ConceptMasterySummary objects sorted by mastery_score descending.
    """
    valid_statuses = {
        AssessmentStatus.COMPLETED,
        AssessmentStatus.APPROVED,
        AssessmentStatus.MODIFIED,
    }

    # concept_name -> {scores: list[float], evidences: list[str]}
    concept_buckets: dict[str, dict[str, list[Any]]] = {}

    for assessment in assessments:
        if assessment.status not in valid_statuses or not assessment.concept_mastery:
            continue

        raw_items = assessment.concept_mastery
        if not isinstance(raw_items, list):
            continue

        for item in raw_items:
            if not isinstance(item, dict):
                continue

            concept_name = item.get("concept")
            if not concept_name or not isinstance(concept_name, str):
                continue
            concept_name = concept_name.strip()
            if not concept_name:
                continue

            raw_level = item.get("mastery_level")
            numeric_score = parse_mastery_value(raw_level)

            evidence = item.get("evidence")
            evidence_str = str(evidence).strip() if evidence else ""

            if concept_name not in concept_buckets:
                concept_buckets[concept_name] = {"scores": [], "evidences": []}

            concept_buckets[concept_name]["scores"].append(numeric_score)
            if evidence_str and evidence_str not in concept_buckets[concept_name]["evidences"]:
                concept_buckets[concept_name]["evidences"].append(evidence_str)

    summaries: list[ConceptMasterySummary] = []
    for concept, data in concept_buckets.items():
        scores = data["scores"]
        if not scores:
            continue
        avg_score = round(sum(scores) / len(scores), 2)
        level = score_to_mastery_level(avg_score)
        summaries.append(
            ConceptMasterySummary(
                concept=concept,
                assessment_count=len(scores),
                mastery_score=avg_score,
                mastery_level=level,
                supporting_evidence=data["evidences"][:5],  # top evidence citations
            )
        )

    # Sort descending by mastery score, then by assessment count
    summaries.sort(key=lambda x: (x.mastery_score, x.assessment_count), reverse=True)
    return summaries


def get_top_strong_and_weak_concepts(
    mastery_summaries: list[ConceptMasterySummary],
    top_k: int = DEFAULT_TOP_CONCEPTS_COUNT,
) -> tuple[list[ConceptMasterySummary], list[ConceptMasterySummary]]:
    """
    Split aggregated concepts into strongest and weakest lists.

    Returns:
        (strongest_concepts, weakest_concepts)
    """
    if not mastery_summaries:
        return [], []

    # Sort descending for strongest
    sorted_desc = sorted(mastery_summaries, key=lambda x: x.mastery_score, reverse=True)
    strongest = sorted_desc[:top_k]

    # Sort ascending for weakest
    sorted_asc = sorted(mastery_summaries, key=lambda x: x.mastery_score)
    weakest = sorted_asc[:top_k]

    return strongest, weakest
