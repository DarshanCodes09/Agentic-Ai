"""
Assignment ORM model.

Represents an assignment belonging to a Subject and created by the faculty owner.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class Assignment(Base):
    """
    Assignments table.

    Belongs to a Subject and is created by a faculty member.
    """

    __tablename__ = "assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    subject_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("subjects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    max_marks: Mapped[float] = mapped_column(Float, nullable=False)

    created_by: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
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
    subject: Mapped["Subject"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Subject",
        back_populates="assignments",
        foreign_keys=[subject_id],
    )
    creator: Mapped["User"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "User",
        foreign_keys=[created_by],
    )
    questions: Mapped[list["Question"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Question",
        back_populates="assignment",
        cascade="all, delete-orphan",
        order_by="Question.question_number",
    )
    rubric: Mapped["Rubric | None"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Rubric",
        back_populates="assignment",
        uselist=False,
        cascade="all, delete-orphan",
    )
    submissions: Mapped[list["Submission"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Submission",
        back_populates="assignment",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Assignment id={self.id} title={self.title!r}>"
