"""
Analytics service package.
"""

from app.services.analytics.constants import (
    DEFAULT_TOP_CONCEPTS_COUNT,
    GAP_SEVERITY_HIGH_THRESHOLD,
    GAP_SEVERITY_MEDIUM_THRESHOLD,
    MASTERY_LEVEL_WEIGHTS,
    MASTERY_THRESHOLD_DEVELOPING,
    MASTERY_THRESHOLD_MASTERED,
    score_to_gap_severity,
    score_to_mastery_level,
)
from app.services.analytics.faculty_analytics_service import (
    get_faculty_assignment_analytics,
    get_faculty_class_concept_analytics,
    get_faculty_class_learning_gaps,
    get_faculty_subject_analytics,
)
from app.services.analytics.learning_gap_service import (
    detect_class_learning_gaps,
    detect_student_learning_gaps,
)
from app.services.analytics.mastery_service import (
    aggregate_concept_mastery,
    get_top_strong_and_weak_concepts,
    parse_mastery_value,
)
from app.services.analytics.student_analytics_service import (
    get_student_concept_mastery,
    get_student_evaluated_assessments,
    get_student_learning_gaps,
    get_student_overall_analytics,
    get_student_performance_trends,
    get_student_subject_performance,
)

__all__ = [
    "MASTERY_LEVEL_WEIGHTS",
    "MASTERY_THRESHOLD_MASTERED",
    "MASTERY_THRESHOLD_DEVELOPING",
    "GAP_SEVERITY_HIGH_THRESHOLD",
    "GAP_SEVERITY_MEDIUM_THRESHOLD",
    "DEFAULT_TOP_CONCEPTS_COUNT",
    "score_to_mastery_level",
    "score_to_gap_severity",
    "parse_mastery_value",
    "aggregate_concept_mastery",
    "get_top_strong_and_weak_concepts",
    "detect_student_learning_gaps",
    "detect_class_learning_gaps",
    "get_student_evaluated_assessments",
    "get_student_overall_analytics",
    "get_student_subject_performance",
    "get_student_concept_mastery",
    "get_student_learning_gaps",
    "get_student_performance_trends",
    "get_faculty_subject_analytics",
    "get_faculty_assignment_analytics",
    "get_faculty_class_concept_analytics",
    "get_faculty_class_learning_gaps",
]
