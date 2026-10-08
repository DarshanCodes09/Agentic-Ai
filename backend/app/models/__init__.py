"""
Package marker — exposes all models for Alembic discovery and ORM relationship resolution.
"""

from app.models.assignment import Assignment  # noqa: F401
from app.models.course_material import CourseMaterial, MaterialProcessingStatus  # noqa: F401
from app.models.enrollment import Enrollment  # noqa: F401
from app.models.question import Question  # noqa: F401
from app.models.rubric import Rubric  # noqa: F401
from app.models.rubric_item import RubricItem  # noqa: F401
from app.models.submission import Submission, SubmissionStatus  # noqa: F401
from app.models.subject import Subject  # noqa: F401
from app.models.user import User, UserRole  # noqa: F401

__all__ = [
    "User",
    "UserRole",
    "Subject",
    "CourseMaterial",
    "MaterialProcessingStatus",
    "Enrollment",
    "Assignment",
    "Question",
    "Rubric",
    "RubricItem",
    "Submission",
    "SubmissionStatus",
]
