"""
Pydantic schemas for AI assessment, criteria evaluation, concept mastery, and feedback.
"""

from datetime import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class AssessmentStatus(str, Enum):
    """Lifecycle status of an AI assessment."""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    APPROVED = "APPROVED"
    MODIFIED = "MODIFIED"


class CriterionEvaluation(BaseModel):
    """Evaluation breakdown for an individual rubric criterion."""
    rubric_item_id: int | None = Field(default=None, description="Associated RubricItem ID if available")
    criterion: str = Field(..., description="Rubric criterion title or name")
    score: float = Field(..., ge=0.0, description="Marks awarded for this criterion")
    max_marks: float = Field(..., ge=0.0, description="Maximum marks possible for this criterion")
    reasoning: str = Field(..., description="Academic justification for the criterion score")


class ConceptMasteryLevel(str, Enum):
    """Bloom-aligned or proficiency mastery level."""
    MASTERED = "MASTERED"
    PROFICIENT = "PROFICIENT"
    PARTIAL = "PARTIAL"
    NEEDS_IMPROVEMENT = "NEEDS_IMPROVEMENT"
    NOT_DEMONSTRATED = "NOT_DEMONSTRATED"


class ConceptMasteryItem(BaseModel):
    """Concept-level assessment indicator."""
    concept: str = Field(..., description="Expected academic concept")
    mastery_level: ConceptMasteryLevel = Field(..., description="Assessed mastery level")
    evidence: str = Field(..., description="Direct citation or evidence from student submission")


class AssessmentStructuredOutput(BaseModel):
    """Structured output schema returned by the Assessment Agent."""
    ai_score: float = Field(..., ge=0.0, description="Total score awarded across all criteria/questions")
    criteria_scores: list[CriterionEvaluation] = Field(default_factory=list, description="Scores per rubric criterion")
    concept_mastery: list[ConceptMasteryItem] = Field(default_factory=list, description="Mastery evaluations per concept")
    strengths: list[str] = Field(default_factory=list, description="Observed strengths in student work")
    weaknesses: list[str] = Field(default_factory=list, description="Gaps or misconceptions identified")
    general_remarks: str = Field(..., description="Overall evaluative assessment summary")


class FeedbackStructuredOutput(BaseModel):
    """Structured output schema returned by the Feedback Agent."""
    summary: str = Field(..., description="Constructive executive summary for the student")
    detailed_feedback: str = Field(..., description="In-depth section-by-section guidance")
    actionable_steps: list[str] = Field(default_factory=list, description="Concrete next steps for learning improvement")
    suggested_topics: list[str] = Field(default_factory=list, description="Course topics recommended for revision")


class AssessmentApprovalRequest(BaseModel):
    """Faculty request to approve an AI-generated assessment."""
    faculty_notes: str | None = Field(default=None, max_length=1000, description="Optional notes or commendations from faculty")


class AssessmentModificationRequest(BaseModel):
    """Faculty request to override or modify an assessment score."""
    final_score: float = Field(..., ge=0.0, description="Faculty overridden final score")
    faculty_notes: str | None = Field(default=None, max_length=1000, description="Rationale for score override")


class AssessmentFeedbackResponse(BaseModel):
    """Response schema for assessment feedback."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    summary: str
    detailed_feedback: str | None = None
    actionable_steps: list[str] = Field(default_factory=list)
    suggested_topics: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class AssessmentResponse(BaseModel):
    """Full assessment response including criteria, concept mastery, scores, and feedback."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    submission_id: int
    ai_score: float
    final_score: float
    max_score: float
    status: AssessmentStatus
    criteria_scores: list[dict[str, Any]] | list[CriterionEvaluation] = Field(default_factory=list)
    concept_mastery: list[dict[str, Any]] | list[ConceptMasteryItem] = Field(default_factory=list)
    retrieved_context: list[dict[str, Any]] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    faculty_notes: str | None = None
    model_name: str | None = None
    feedback: AssessmentFeedbackResponse | None = None
    created_at: datetime
    updated_at: datetime
