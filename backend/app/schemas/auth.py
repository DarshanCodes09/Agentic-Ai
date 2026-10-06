"""
Pydantic schemas for authentication endpoints.
"""

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.user import UserRole


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    """Payload for POST /api/auth/register."""

    full_name: str = Field(
        ...,
        min_length=2,
        max_length=255,
        examples=["Alice Johnson"],
    )
    email: EmailStr = Field(..., examples=["alice@university.edu"])
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        examples=["Secure@1234"],
    )
    role: UserRole = Field(..., examples=["STUDENT"])

    @field_validator("password")
    @classmethod
    def password_complexity(cls, value: str) -> str:
        """Enforce a minimum complexity requirement."""
        if not any(c.isupper() for c in value):
            raise ValueError("Password must contain at least one uppercase letter.")
        if not any(c.islower() for c in value):
            raise ValueError("Password must contain at least one lowercase letter.")
        if not any(c.isdigit() for c in value):
            raise ValueError("Password must contain at least one digit.")
        return value

    @field_validator("full_name")
    @classmethod
    def full_name_no_blanks(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Full name must not be blank.")
        return stripped


class RegisterResponse(BaseModel):
    """Safe user data returned after successful registration."""

    id: int
    full_name: str
    email: EmailStr
    role: UserRole
    is_active: bool
    message: str = "Registration successful."

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    """Payload for POST /api/auth/login."""

    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """JWT token payload returned on successful login."""

    access_token: str
    token_type: str = "bearer"
    user_id: int
    email: EmailStr
    full_name: str
    role: UserRole
