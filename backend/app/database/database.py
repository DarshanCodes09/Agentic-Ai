"""
SQLAlchemy engine and session factory.

The engine is created once from DATABASE_URL. The SessionLocal factory
is used to open database sessions.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.database_url,
    # Pool settings suitable for a single-server FastAPI application.
    pool_pre_ping=True,       # Detects stale connections before checkout
    pool_size=10,
    max_overflow=20,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)
