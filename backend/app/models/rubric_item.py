"""
RubricItem ORM model.

A grading criterion within a Rubric.
"""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class RubricItem(Base):
    """
    Rubric items table.

    Represents an individual grading criterion with description and max_marks.
    """

    __tablename__ = "rubric_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    rubric_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("rubrics.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    criterion: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    max_marks: Mapped[float] = mapped_column(Float, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # --- Relationships ---
    rubric: Mapped["Rubric"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Rubric",
        back_populates="items",
        foreign_keys=[rubric_id],
    )

    def __repr__(self) -> str:
        return f"<RubricItem id={self.id} criterion={self.criterion!r} max_marks={self.max_marks}>"
