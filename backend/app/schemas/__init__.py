"""
Pydantic schemas package marker.
"""

from app.schemas.assignment import (
    AssignmentCreate,
    AssignmentResponse,
    AssignmentUpdate,
)
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
)
from app.schemas.enrollment import EnrollmentCreate, EnrollmentResponse
from app.schemas.question import (
    QuestionCreate,
    QuestionResponse,
    QuestionUpdate,
)
from app.schemas.rubric import (
    RubricCreate,
    RubricItemCreate,
    RubricItemResponse,
    RubricItemUpdate,
    RubricResponse,
    RubricUpdate,
)
from app.schemas.submission import SubmissionCreate, SubmissionResponse
from app.schemas.subject import (
    SubjectCreate,
    SubjectResponse,
    SubjectUpdate,
)
from app.schemas.user import UserBrief, UserPublic

__all__ = [
    "RegisterRequest",
    "RegisterResponse",
    "LoginRequest",
    "TokenResponse",
    "UserPublic",
    "UserBrief",
    "SubjectCreate",
    "SubjectUpdate",
    "SubjectResponse",
    "EnrollmentCreate",
    "EnrollmentResponse",
    "AssignmentCreate",
    "AssignmentUpdate",
    "AssignmentResponse",
    "QuestionCreate",
    "QuestionUpdate",
    "QuestionResponse",
    "RubricCreate",
    "RubricUpdate",
    "RubricResponse",
    "RubricItemCreate",
    "RubricItemUpdate",
    "RubricItemResponse",
    "SubmissionCreate",
    "SubmissionResponse",
]
