"""
Rubric ORM model.

Belongs to an Assignment. Contains criteria items for grading and future AI evaluation.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class Rubric(Base):
    """
    Rubrics table.

    Each rubric belongs to an assignment (1-to-1 relationship).
    """

    __tablename__ = "rubrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    assignment_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("assignments.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

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
        back_populates="rubric",
        foreign_keys=[assignment_id],
    )
    items: Mapped[list["RubricItem"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "RubricItem",
        back_populates="rubric",
        cascade="all, delete-orphan",
        order_by="RubricItem.id",
    )

    def __repr__(self) -> str:
        return f"<Rubric id={self.id} assignment_id={self.assignment_id} name={self.name!r}>"
