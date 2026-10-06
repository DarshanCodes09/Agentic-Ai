"""
Question ORM model.

Belongs to an Assignment. Stores question details, marks, and expected concepts.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class Question(Base):
    """
    Questions table.

    Each question belongs to an assignment with unique question_number per assignment.
    expected_concepts stores a structured JSON array of concept tags/descriptions.
    """

    __tablename__ = "questions"

    __table_args__ = (
        UniqueConstraint(
            "assignment_id", "question_number", name="uq_assignment_question_number"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    assignment_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("assignments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question_number: Mapped[int] = mapped_column(Integer, nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    marks: Mapped[float] = mapped_column(Float, nullable=False)

    # Stores list of concept tags/definitions for future AI evaluation
    expected_concepts: Mapped[list[str] | Any | None] = mapped_column(
        JSON,
        nullable=True,
        default=list,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # --- Relationships ---
    assignment: Mapped["Assignment"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Assignment",
        back_populates="questions",
        foreign_keys=[assignment_id],
    )

    def __repr__(self) -> str:
        return f"<Question id={self.id} assignment_id={self.assignment_id} q_num={self.question_number}>"
