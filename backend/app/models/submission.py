"""
Submission ORM model.

Stores student submissions for assignments (text and/or uploaded file).
"""

import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class SubmissionStatus(str, enum.Enum):
    """Submission lifecycle states."""
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    EVALUATED = "EVALUATED"


class Submission(Base):
    """
    Submissions table.

    Records student submission for an assignment.
    Supports text submissions, file uploads, or both.
    """

    __tablename__ = "submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    assignment_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("assignments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    submission_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)

    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    status: Mapped[SubmissionStatus] = mapped_column(
        Enum(SubmissionStatus, name="submissionstatus", create_type=True),
        default=SubmissionStatus.SUBMITTED,
        nullable=False,
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
    assignment: Mapped["Assignment"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Assignment",
        back_populates="submissions",
        foreign_keys=[assignment_id],
    )
    student: Mapped["User"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "User",
        foreign_keys=[student_id],
    )
    assessment: Mapped["AssessmentResult | None"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "AssessmentResult",
        back_populates="submission",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Submission id={self.id} assignment_id={self.assignment_id} student_id={self.student_id} status={self.status}>"

