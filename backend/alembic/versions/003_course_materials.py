"""Create course_materials table for Phase 3 RAG

Revision ID: 003_course_materials
Revises: 002_academic_core_phase2
Create Date: 2026-10-08

Creates course_materials table with materialprocessingstatus enum.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "003_course_materials"
down_revision: Union[str, None] = "002_academic_core_phase2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    processing_status_enum = sa.Enum(
        "UPLOADED", "PROCESSING", "PROCESSED", "FAILED", name="materialprocessingstatus"
    )
    if bind.dialect.name == "postgresql":
        processing_status_enum.create(bind, checkfirst=True)

    op.create_table(
        "course_materials",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("uploaded_by", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("stored_filename", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("file_type", sa.String(length=50), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column(
            "processing_status",
            sa.Enum(
                "UPLOADED",
                "PROCESSING",
                "PROCESSED",
                "FAILED",
                name="materialprocessingstatus",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_course_materials_id"), "course_materials", ["id"], unique=False)
    op.create_index(op.f("ix_course_materials_subject_id"), "course_materials", ["subject_id"], unique=False)
    op.create_index(op.f("ix_course_materials_uploaded_by"), "course_materials", ["uploaded_by"], unique=False)


def downgrade() -> None:
    op.drop_table("course_materials")
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        sa.Enum(name="materialprocessingstatus").drop(bind, checkfirst=True)
