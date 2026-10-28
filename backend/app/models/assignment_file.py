"""
AssignmentFile ORM model.

Stores files attached to assignments by faculty (e.g., instructions, problem descriptions,
rubric documents, specifications in PDF, DOCX, TXT, or MD format).
"""

from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class AssignmentFile(Base):
    """
    Assignment files table.

    Stores metadata and extracted text for reference and specification documents
    attached to an assignment by faculty.
    """

    __tablename__ = "assignment_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    assignment_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("assignments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    uploaded_by: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)  # "pdf", "docx", "txt", "md"
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)  # size in bytes
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)

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
        back_populates="files",
        foreign_keys=[assignment_id],
    )
    uploader: Mapped["User"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "User",
        foreign_keys=[uploaded_by],
    )

    def __repr__(self) -> str:
        return f"<AssignmentFile id={self.id} assignment_id={self.assignment_id} filename={self.original_filename!r}>"
