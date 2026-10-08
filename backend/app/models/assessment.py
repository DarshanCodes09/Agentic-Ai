"""
AssessmentResult and AssessmentFeedback ORM models.
"""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.schemas.assessment import AssessmentStatus


class AssessmentResult(Base):
    """
    Stores AI assessment evaluations, criteria scores, concept mastery,
    and faculty approval/override status.
    """

    __tablename__ = "assessment_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    submission_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("submissions.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    ai_score: Mapped[float] = mapped_column(Float, nullable=False)
    final_score: Mapped[float] = mapped_column(Float, nullable=False)
    max_score: Mapped[float] = mapped_column(Float, nullable=False)

    status: Mapped[AssessmentStatus] = mapped_column(
        Enum(AssessmentStatus, name="assessmentstatus", create_type=True),
        default=AssessmentStatus.COMPLETED,
        nullable=False,
    )

    criteria_scores: Mapped[list[dict[str, Any]] | Any | None] = mapped_column(
        JSON,
        nullable=True,
        default=list,
    )
    concept_mastery: Mapped[list[dict[str, Any]] | Any | None] = mapped_column(
        JSON,
        nullable=True,
        default=list,
    )
    retrieved_context: Mapped[list[dict[str, Any]] | Any | None] = mapped_column(
        JSON,
        nullable=True,
        default=list,
    )
    strengths: Mapped[list[str] | Any | None] = mapped_column(
        JSON,
        nullable=True,
        default=list,
    )
    weaknesses: Mapped[list[str] | Any | None] = mapped_column(
        JSON,
        nullable=True,
        default=list,
    )

    faculty_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(100), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # --- Relationships ---
    submission: Mapped["Submission"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Submission",
        back_populates="assessment",
        foreign_keys=[submission_id],
    )
    feedback: Mapped["AssessmentFeedback | None"] = relationship(
        "AssessmentFeedback",
        back_populates="assessment",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<AssessmentResult id={self.id} submission_id={self.submission_id} score={self.final_score}/{self.max_score} status={self.status}>"


class AssessmentFeedback(Base):
    """
    Stores personalized academic feedback generated for a student submission.
    """

    __tablename__ = "assessment_feedbacks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    assessment_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("assessment_results.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    summary: Mapped[str] = mapped_column(Text, nullable=False)
    detailed_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)

    actionable_steps: Mapped[list[str] | Any | None] = mapped_column(
        JSON,
        nullable=True,
        default=list,
    )
    suggested_topics: Mapped[list[str] | Any | None] = mapped_column(
        JSON,
        nullable=True,
        default=list,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # --- Relationships ---
    assessment: Mapped["AssessmentResult"] = relationship(
        "AssessmentResult",
        back_populates="feedback",
        foreign_keys=[assessment_id],
    )

    def __repr__(self) -> str:
        return f"<AssessmentFeedback id={self.id} assessment_id={self.assessment_id}>"
