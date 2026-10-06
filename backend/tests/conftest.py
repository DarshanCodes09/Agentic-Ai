"""
Pytest configuration and shared fixtures.

Uses a separate test database (SQLite in-memory by default) so tests
never touch the real PostgreSQL database.
"""

import warnings

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import SAWarning
from sqlalchemy.orm import Session, sessionmaker

from app.database.base import Base
from app.database.session import get_db
from app.main import app

# ---------------------------------------------------------------------------
# Test database — SQLite in-memory for speed and isolation
# ---------------------------------------------------------------------------
TEST_DATABASE_URL = "sqlite:///./test.db"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},  # Required for SQLite + threading
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="session", autouse=True)
def create_test_tables():
    """Create all tables once for the entire test session, then drop them."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db() -> Session:
    """
    Provide a clean database session for each test.
    Each test runs inside a transaction that is rolled back after the test,
    ensuring complete isolation between tests.
    """
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    # Suppress SQLite-specific SAWarning when a transaction is deassociated
    # after an IntegrityError forces a connection-level rollback.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SAWarning)
        try:
            transaction.rollback()
        except Exception:
            pass
    connection.close()


@pytest.fixture
def client(db: Session) -> TestClient:
    """
    Return a FastAPI TestClient with the DB dependency overridden
    to use the test database session.
    """
    def override_get_db():
        try:
            yield db
        finally:
            pass  # Cleanup handled by the db fixture

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
