"""
FastAPI database session dependency.

Provides a request-scoped SQLAlchemy session that is automatically
closed (and rolled back on error) when the request finishes.
"""

from collections.abc import Generator

from sqlalchemy.orm import Session

from app.database.database import SessionLocal


def get_db() -> Generator[Session, None, None]:
    """
    Yield a database session for the duration of a single request.

    Usage in a route:
        def my_endpoint(db: Session = Depends(get_db)): ...
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
