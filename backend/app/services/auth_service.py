"""
Authentication service — login logic.
"""

from sqlalchemy.orm import Session

from app.core.exceptions import InactiveUserError, InvalidCredentialsError
from app.core.security import create_access_token, verify_password
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse
from app.services.user_service import get_user_by_email


def authenticate_user(db: Session, payload: LoginRequest) -> TokenResponse:
    """
    Validate credentials and return a JWT token response.

    Raises:
        InvalidCredentialsError: If email not found or password is wrong.
        InactiveUserError: If the account is deactivated.
    """
    user: User | None = get_user_by_email(db, payload.email)

    # Use the same error for "not found" and "wrong password" to prevent
    # user enumeration via timing differences.
    if user is None or not verify_password(payload.password, user.password_hash):
        raise InvalidCredentialsError()

    if not user.is_active:
        raise InactiveUserError()

    token = create_access_token(subject=user.id)

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
    )
