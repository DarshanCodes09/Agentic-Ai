"""
Subject ORM model.

A subject is owned by a single FACULTY member. Students can enroll in subjects.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class Subject(Base):
    """
    Subjects table.

    Each subject is created and managed by one faculty member (faculty_id).
    The subject code must be unique across the platform.
    """

    __tablename__ = "subjects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Foreign key → users.id (must be a FACULTY user — enforced at service layer)
    faculty_id: Mapped[int] = mapped_column(
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
    faculty: Mapped["User"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "User",
        foreign_keys=[faculty_id],
    )
    enrollments: Mapped[list["Enrollment"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Enrollment",
        back_populates="subject",
        cascade="all, delete-orphan",
    )
    assignments: Mapped[list["Assignment"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Assignment",
        back_populates="subject",
        cascade="all, delete-orphan",
    )
    materials: Mapped[list["CourseMaterial"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "CourseMaterial",
        back_populates="subject",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Subject id={self.id} code={self.code!r}>"
