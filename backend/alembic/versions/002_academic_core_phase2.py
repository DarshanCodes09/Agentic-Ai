"""Create academic core tables for Phase 2

Revision ID: 002_academic_core_phase2
Revises: 001_initial
Create Date: 2026-10-06

Creates subjects, enrollments, assignments, questions, rubrics, rubric_items, submissions.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002_academic_core_phase2"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create submissionstatus enum type if dialect supports enum (PostgreSQL)
    bind = op.get_bind()
    submissionstatus_enum = sa.Enum("SUBMITTED", "UNDER_REVIEW", "EVALUATED", name="submissionstatus")
    if bind.dialect.name == "postgresql":
        submissionstatus_enum.create(bind, checkfirst=True)

    # 1. Subjects table
    op.create_table(
        "subjects",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("faculty_id", sa.Integer(), nullable=False),
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
        sa.ForeignKeyConstraint(["faculty_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index(op.f("ix_subjects_id"), "subjects", ["id"], unique=False)
    op.create_index(op.f("ix_subjects_code"), "subjects", ["code"], unique=True)
    op.create_index(op.f("ix_subjects_faculty_id"), "subjects", ["faculty_id"], unique=False)

    # 2. Enrollments table
    op.create_table(
        "enrollments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column(
            "enrolled_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("student_id", "subject_id", name="uq_student_subject"),
    )
    op.create_index(op.f("ix_enrollments_id"), "enrollments", ["id"], unique=False)
    op.create_index(op.f("ix_enrollments_student_id"), "enrollments", ["student_id"], unique=False)
    op.create_index(op.f("ix_enrollments_subject_id"), "enrollments", ["subject_id"], unique=False)

    # 3. Assignments table
    op.create_table(
        "assignments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("instructions", sa.Text(), nullable=True),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("max_marks", sa.Float(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
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
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["subject_id"], ["subjects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_assignments_id"), "assignments", ["id"], unique=False)
    op.create_index(op.f("ix_assignments_subject_id"), "assignments", ["subject_id"], unique=False)
    op.create_index(op.f("ix_assignments_created_by"), "assignments", ["created_by"], unique=False)

    # 4. Questions table
    op.create_table(
        "questions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("assignment_id", sa.Integer(), nullable=False),
        sa.Column("question_number", sa.Integer(), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("marks", sa.Float(), nullable=False),
        sa.Column("expected_concepts", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["assignment_id"], ["assignments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("assignment_id", "question_number", name="uq_assignment_question_number"),
    )
    op.create_index(op.f("ix_questions_id"), "questions", ["id"], unique=False)
    op.create_index(op.f("ix_questions_assignment_id"), "questions", ["assignment_id"], unique=False)

    # 5. Rubrics table
    op.create_table(
        "rubrics",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("assignment_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["assignment_id"], ["assignments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("assignment_id"),
    )
    op.create_index(op.f("ix_rubrics_id"), "rubrics", ["id"], unique=False)
    op.create_index(op.f("ix_rubrics_assignment_id"), "rubrics", ["assignment_id"], unique=True)

    # 6. Rubric items table
    op.create_table(
        "rubric_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("rubric_id", sa.Integer(), nullable=False),
        sa.Column("criterion", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("max_marks", sa.Float(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["rubric_id"], ["rubrics.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_rubric_items_id"), "rubric_items", ["id"], unique=False)
    op.create_index(op.f("ix_rubric_items_rubric_id"), "rubric_items", ["rubric_id"], unique=False)

    # 7. Submissions table
    op.create_table(
        "submissions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("assignment_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("submission_text", sa.Text(), nullable=True),
        sa.Column("file_path", sa.String(length=500), nullable=True),
        sa.Column("original_filename", sa.String(length=255), nullable=True),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("SUBMITTED", "UNDER_REVIEW", "EVALUATED", name="submissionstatus", create_type=False),
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
        sa.ForeignKeyConstraint(["assignment_id"], ["assignments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_submissions_id"), "submissions", ["id"], unique=False)
    op.create_index(op.f("ix_submissions_assignment_id"), "submissions", ["assignment_id"], unique=False)
    op.create_index(op.f("ix_submissions_student_id"), "submissions", ["student_id"], unique=False)


def downgrade() -> None:
    op.drop_table("submissions")
    op.drop_table("rubric_items")
    op.drop_table("rubrics")
    op.drop_table("questions")
    op.drop_table("assignments")
    op.drop_table("enrollments")
    op.drop_table("subjects")

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        sa.Enum(name="submissionstatus").drop(bind, checkfirst=True)
