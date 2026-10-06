"""
Declarative base for all SQLAlchemy ORM models.

All models must inherit from Base so Alembic can discover them
and manage migrations automatically.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Project-wide SQLAlchemy declarative base."""
    pass
