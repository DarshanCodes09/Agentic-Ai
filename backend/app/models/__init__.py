"""
Package marker — exposes the models sub-package.

Import all models here so Alembic's autogenerate can discover every table
by importing this single module.
"""

from app.models.user import User, UserRole  # noqa: F401
