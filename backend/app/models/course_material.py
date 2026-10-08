"""
CourseMaterial ORM model.

Represents faculty-uploaded reference/lecture material (PDF or DOCX) for a subject.
Forms the knowledge base for RAG retrieval.
"""

import enum
from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class MaterialProcessingStatus(str, enum.Enum):
    """Document extraction and vector embedding status."""
    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"


class CourseMaterial(Base):
    """
    Course materials table.

    Stores metadata for academic reference documents uploaded by faculty.
    """

    __tablename__ = "course_materials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    subject_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("subjects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    uploaded_by: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)  # "pdf" or "docx"
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)  # size in bytes

    processing_status: Mapped[MaterialProcessingStatus] = mapped_column(
        Enum(MaterialProcessingStatus, name="materialprocessingstatus", create_type=True),
        default=MaterialProcessingStatus.UPLOADED,
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
    subject: Mapped["Subject"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Subject",
        back_populates="materials",
        foreign_keys=[subject_id],
    )
    uploader: Mapped["User"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "User",
        foreign_keys=[uploaded_by],
    )

    def __repr__(self) -> str:
        return f"<CourseMaterial id={self.id} subject_id={self.subject_id} title={self.title!r} status={self.processing_status}>"
