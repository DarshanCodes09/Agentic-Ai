"""
Authentication API routes.

Endpoints:
  POST /api/auth/register    — Create a new user account
  POST /api/auth/login       — Login with email + password, receive JWT
  POST /api/auth/login/form  — OAuth2-compatible form login (for Swagger UI)
  GET  /api/auth/me          — Return the current authenticated user
"""

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.exceptions import InvalidCredentialsError
from app.core.security import create_access_token, verify_password
from app.database.session import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, RegisterResponse, TokenResponse
from app.schemas.user import UserBrief
from app.services.auth_service import authenticate_user
from app.services.user_service import create_user, get_user_by_email

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
def register(
    payload: RegisterRequest,
    db: Session = Depends(get_db),
) -> RegisterResponse:
    """
    Register a new STUDENT or FACULTY account.

    - Validates email format and password complexity.
    - Hashes the password with bcrypt before storage.
    - Returns safe user data (never the password hash).
    - Returns 409 Conflict if the email is already registered.
    """
    user = create_user(db, payload)
    return RegisterResponse(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login with email and password",
)
def login(
    payload: LoginRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """
    Authenticate with email + password and receive a JWT access token.
    """
    return authenticate_user(db, payload)


@router.post(
    "/login/form",
    response_model=TokenResponse,
    summary="OAuth2-compatible form login (Swagger UI)",
    include_in_schema=False,  # Hidden from public docs — only for Swagger UI auth
)
def login_form(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> TokenResponse:
    """
    OAuth2 password-flow endpoint consumed by Swagger UI's Authorize button.
    The username field is treated as the email address.
    """
    user = get_user_by_email(db, form_data.username)
    if user is None or not verify_password(form_data.password, user.password_hash):
        raise InvalidCredentialsError()

    token = create_access_token(subject=user.id)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
    )


@router.get(
    "/me",
    response_model=UserBrief,
    summary="Get the currently authenticated user",
)
def get_me(current_user: User = Depends(get_current_user)) -> UserBrief:
    """
    Return the profile of the currently authenticated user.
    Requires a valid Bearer JWT in the Authorization header.
    """
    return UserBrief.model_validate(current_user)
