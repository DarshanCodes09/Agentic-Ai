"""
Pydantic schemas for student and faculty academic performance analytics.
"""

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class ConceptMasterySummary(BaseModel):
    """Aggregated mastery details for an academic concept."""
    concept: str = Field(..., description="Concept title or identifier")
    assessment_count: int = Field(..., ge=0, description="Total assessments/questions featuring this concept")
    mastery_score: float = Field(..., ge=0.0, le=1.0, description="Normalized mastery score [0.0 - 1.0]")
    mastery_level: str = Field(..., description="Categorical mastery level (MASTERED, DEVELOPING, NEEDS_IMPROVEMENT)")
    supporting_evidence: list[str] = Field(default_factory=list, description="Extracted citation evidence from assessments")


class LearningGapItem(BaseModel):
    """Identified student conceptual deficiency or learning gap."""
    concept: str = Field(..., description="Concept exhibiting a learning gap")
    subject_id: int | None = Field(default=None, description="Subject ID where gap was observed")
    subject_name: str | None = Field(default=None, description="Subject title")
    severity: str = Field(..., description="Deterministic gap severity: HIGH, MEDIUM, LOW")
    mastery_score: float = Field(..., ge=0.0, le=1.0, description="Normalized mastery score")
    evidence: list[str] = Field(default_factory=list, description="Reasoning and excerpts indicating misconceptions")
    occurrence_count: int = Field(..., ge=1, description="Number of evaluations confirming this deficiency")


class PerformanceTrendItem(BaseModel):
    """Single point in a chronological performance sequence."""
    assessment_id: int
    assignment_id: int
    assignment_title: str
    subject_id: int
    subject_name: str
    score: float = Field(..., ge=0.0)
    max_score: float = Field(..., ge=0.0)
    percentage: float = Field(..., ge=0.0, le=100.0)
    evaluated_at: datetime


class SubjectPerformanceResponse(BaseModel):
    """Student performance metrics scoped to a single subject."""
    subject_id: int
    subject_name: str
    subject_code: str
    assessments_count: int = Field(..., ge=0)
    total_score: float = Field(..., ge=0.0)
    total_max_score: float = Field(..., ge=0.0)
    percentage: float = Field(..., ge=0.0, le=100.0)
    average_score: float = Field(..., ge=0.0)


class StudentOverallAnalyticsResponse(BaseModel):
    """Comprehensive academic performance overview for a student."""
    student_id: int
    total_assessments_evaluated: int = Field(..., ge=0)
    total_marks_obtained: float = Field(..., ge=0.0)
    total_max_marks: float = Field(..., ge=0.0)
    overall_percentage: float = Field(..., ge=0.0, le=100.0)
    average_score: float = Field(..., ge=0.0)
    average_confidence: float | None = None
    enrolled_subjects_count: int = Field(..., ge=0)
    strongest_concepts: list[ConceptMasterySummary] = Field(default_factory=list)
    weakest_concepts: list[ConceptMasterySummary] = Field(default_factory=list)


class FacultySubjectAnalyticsResponse(BaseModel):
    """Class performance overview for an entire subject owned by faculty."""
    subject_id: int
    subject_name: str
    subject_code: str
    enrolled_student_count: int = Field(..., ge=0)
    students_with_submissions: int = Field(..., ge=0)
    evaluated_submissions_count: int = Field(..., ge=0)
    total_submissions_count: int = Field(..., ge=0)
    assignment_count: int = Field(..., ge=0)
    average_score: float = Field(..., ge=0.0)
    average_percentage: float = Field(..., ge=0.0, le=100.0)
    highest_percentage: float = Field(..., ge=0.0, le=100.0)
    lowest_percentage: float = Field(..., ge=0.0, le=100.0)
    median_percentage: float = Field(..., ge=0.0, le=100.0)
    completion_rate: float = Field(..., ge=0.0, le=100.0)
    performance_distribution: dict[str, int] = Field(default_factory=dict)
    strong_concepts: list[str] = Field(default_factory=list)
    weak_concepts: list[str] = Field(default_factory=list)


class AssignmentAnalyticsResponse(BaseModel):
    """Performance analytics for a single assignment owned by faculty."""
    assignment_id: int
    assignment_title: str
    subject_id: int
    subject_name: str
    max_marks: float = Field(..., ge=0.0)
    enrolled_count: int = Field(..., ge=0)
    submission_count: int = Field(..., ge=0)
    evaluated_count: int = Field(..., ge=0)
    average_score: float = Field(..., ge=0.0)
    average_percentage: float = Field(..., ge=0.0, le=100.0)
    highest_score: float = Field(..., ge=0.0)
    lowest_score: float = Field(..., ge=0.0)
    completion_rate: float = Field(..., ge=0.0, le=100.0)


class ClassConceptAnalyticsResponse(BaseModel):
    """Aggregated class mastery for a concept across all student evaluations."""
    concept: str
    average_mastery: float = Field(..., ge=0.0, le=1.0)
    mastery_level: str
    assessed_student_count: int = Field(..., ge=0)
    total_occurrences: int = Field(..., ge=0)


class ClassLearningGapResponse(BaseModel):
    """Class-wide conceptual vulnerability indicating curriculum reinforcement needs."""
    concept: str
    average_mastery: float = Field(..., ge=0.0, le=1.0)
    affected_student_count: int = Field(..., ge=0)
    total_occurrences: int = Field(..., ge=0)
    severity: str
    sample_evidence: list[str] = Field(default_factory=list)
