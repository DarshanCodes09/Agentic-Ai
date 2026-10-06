"""
Reusable FastAPI dependencies for authentication and role-based access control.

These dependencies are the foundation for securing all future endpoints.
Usage:
    current_user: User = Depends(get_current_user)
    _: User = Depends(require_faculty)
"""

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.exceptions import (
    InactiveUserError,
    InsufficientPermissionsError,
    InvalidTokenError,
)
from app.core.security import decode_access_token
from app.database.session import get_db
from app.models.user import User, UserRole
from app.services.user_service import get_user_by_id

# The tokenUrl tells Swagger UI where to POST credentials to get a token.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login/form")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Decode the JWT from the Authorization header and return the User.

    Raises:
        InvalidTokenError: If the token is malformed, expired, or has no subject.
        InactiveUserError: If the user account is deactivated.
    """
    try:
        payload = decode_access_token(token)
        user_id_str: str | None = payload.get("sub")
        if user_id_str is None:
            raise InvalidTokenError()
        user_id = int(user_id_str)
    except (JWTError, ValueError):
        raise InvalidTokenError()

    user = get_user_by_id(db, user_id)

    if not user.is_active:
        raise InactiveUserError()

    return user


def require_student(current_user: User = Depends(get_current_user)) -> User:
    """
    Dependency that ensures the authenticated user has the STUDENT role.

    Raises:
        InsufficientPermissionsError: If the user is not a student.
    """
    if current_user.role != UserRole.STUDENT:
        raise InsufficientPermissionsError()
    return current_user


def require_faculty(current_user: User = Depends(get_current_user)) -> User:
    """
    Dependency that ensures the authenticated user has the FACULTY role.

    Raises:
        InsufficientPermissionsError: If the user is not faculty.
    """
    if current_user.role != UserRole.FACULTY:
        raise InsufficientPermissionsError()
    return current_user
