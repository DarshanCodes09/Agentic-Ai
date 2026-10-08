"""Create assessment_results and assessment_feedbacks tables for Phase 4

Revision ID: 004_assessment_and_feedback
Revises: 003_course_materials
Create Date: 2026-10-08

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "004_assessment_and_feedback"
down_revision: Union[str, None] = "003_course_materials"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    assessment_status_enum = sa.Enum(
        "PENDING",
        "PROCESSING",
        "COMPLETED",
        "FAILED",
        "APPROVED",
        "MODIFIED",
        name="assessmentstatus",
    )
    if bind.dialect.name == "postgresql":
        assessment_status_enum.create(bind, checkfirst=True)

    op.create_table(
        "assessment_results",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("submission_id", sa.Integer(), nullable=False),
        sa.Column("ai_score", sa.Float(), nullable=False),
        sa.Column("final_score", sa.Float(), nullable=False),
        sa.Column("max_score", sa.Float(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING",
                "PROCESSING",
                "COMPLETED",
                "FAILED",
                "APPROVED",
                "MODIFIED",
                name="assessmentstatus",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("criteria_scores", sa.JSON(), nullable=True),
        sa.Column("concept_mastery", sa.JSON(), nullable=True),
        sa.Column("retrieved_context", sa.JSON(), nullable=True),
        sa.Column("strengths", sa.JSON(), nullable=True),
        sa.Column("weaknesses", sa.JSON(), nullable=True),
        sa.Column("faculty_notes", sa.Text(), nullable=True),
        sa.Column("model_name", sa.String(length=100), nullable=True),
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
        sa.ForeignKeyConstraint(["submission_id"], ["submissions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("submission_id"),
    )
    op.create_index(op.f("ix_assessment_results_id"), "assessment_results", ["id"], unique=False)
    op.create_index(op.f("ix_assessment_results_submission_id"), "assessment_results", ["submission_id"], unique=True)

    op.create_table(
        "assessment_feedbacks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("assessment_id", sa.Integer(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("detailed_feedback", sa.Text(), nullable=True),
        sa.Column("actionable_steps", sa.JSON(), nullable=True),
        sa.Column("suggested_topics", sa.JSON(), nullable=True),
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
        sa.ForeignKeyConstraint(["assessment_id"], ["assessment_results.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("assessment_id"),
    )
    op.create_index(op.f("ix_assessment_feedbacks_id"), "assessment_feedbacks", ["id"], unique=False)
    op.create_index(op.f("ix_assessment_feedbacks_assessment_id"), "assessment_feedbacks", ["assessment_id"], unique=True)


def downgrade() -> None:
    op.drop_table("assessment_feedbacks")
    op.drop_table("assessment_results")
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        sa.Enum(name="assessmentstatus").drop(bind, checkfirst=True)
