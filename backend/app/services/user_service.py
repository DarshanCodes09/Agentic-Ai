"""
User service — business logic for user creation and lookup.

This layer sits between the API routes and the database models,
keeping routes thin and business logic testable.
"""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import DuplicateEmailError, UserNotFoundError
from app.core.security import hash_password
from app.models.user import User, UserRole
from app.schemas.auth import RegisterRequest


def create_user(db: Session, payload: RegisterRequest) -> User:
    """
    Create and persist a new user.

    Raises:
        DuplicateEmailError: If the email is already registered.
    """
    hashed = hash_password(payload.password)
    user = User(
        full_name=payload.full_name.strip(),
        email=payload.email.lower(),
        password_hash=hashed,
        role=payload.role,
        is_active=True,
    )
    db.add(user)
    try:
        db.flush()  # Flush to catch DB-level constraint violations before commit
    except IntegrityError:
        db.rollback()
        raise DuplicateEmailError()
    return user


def get_user_by_email(db: Session, email: str) -> User | None:
    """Return the User with the given email, or None if not found."""
    return db.query(User).filter(User.email == email.lower()).first()


def get_user_by_id(db: Session, user_id: int) -> User:
    """
    Return the User with the given id.

    Raises:
        UserNotFoundError: If no user exists with that id.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise UserNotFoundError()
    return user


def get_all_users(db: Session) -> list[User]:
    """Return all users (for admin/debug use — not exposed publicly in Phase 1)."""
    return db.query(User).all()
