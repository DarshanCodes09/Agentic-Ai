"""
Enrollment ORM model.

Maps students to subjects. Only STUDENT users may enroll.
Enforces unique (student_id, subject_id).
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class Enrollment(Base):
    """
    Enrollments table.

    Links a student User to a Subject.
    """

    __tablename__ = "enrollments"

    __table_args__ = (
        UniqueConstraint("student_id", "subject_id", name="uq_student_subject"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    student_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subject_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("subjects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    enrolled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # --- Relationships ---
    student: Mapped["User"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "User",
        foreign_keys=[student_id],
    )
    subject: Mapped["Subject"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Subject",
        back_populates="enrollments",
        foreign_keys=[subject_id],
    )

    def __repr__(self) -> str:
        return f"<Enrollment student_id={self.student_id} subject_id={self.subject_id}>"
