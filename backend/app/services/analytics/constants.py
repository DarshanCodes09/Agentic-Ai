"""
Constants and scoring thresholds for performance analytics and mastery calculations.
"""

# Weights for converting Phase 4 ConceptMasteryLevel into normalized numeric values [0.0, 1.0]
MASTERY_LEVEL_WEIGHTS: dict[str, float] = {
    "MASTERED": 1.0,
    "PROFICIENT": 0.80,
    "DEVELOPING": 0.60,
    "PARTIAL": 0.50,
    "NEEDS_IMPROVEMENT": 0.25,
    "NOT_DEMONSTRATED": 0.0,
}

# Categorical Mastery Thresholds
MASTERY_THRESHOLD_MASTERED: float = 0.80
MASTERY_THRESHOLD_DEVELOPING: float = 0.60

# Learning Gap Severity Thresholds
GAP_SEVERITY_HIGH_THRESHOLD: float = 0.40
GAP_SEVERITY_MEDIUM_THRESHOLD: float = 0.60

# Default counts for top strong/weak rankings
DEFAULT_TOP_CONCEPTS_COUNT: int = 5


def score_to_mastery_level(score: float) -> str:
    """Map numeric score in [0.0, 1.0] to a standardized mastery label."""
    if score >= MASTERY_THRESHOLD_MASTERED:
        return "MASTERED"
    if score >= MASTERY_THRESHOLD_DEVELOPING:
        return "DEVELOPING"
    return "NEEDS_IMPROVEMENT"


def score_to_gap_severity(score: float) -> str:
    """Map numeric score to deterministic learning gap severity."""
    if score < GAP_SEVERITY_HIGH_THRESHOLD:
        return "HIGH"
    if score < GAP_SEVERITY_MEDIUM_THRESHOLD:
        return "MEDIUM"
    return "LOW"
