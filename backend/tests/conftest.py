"""
Pytest configuration and shared fixtures.

Uses a separate test database (SQLite in-memory/file) so tests
never touch the real PostgreSQL database.
"""

import warnings

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import SAWarning
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401 — register all models with Base.metadata
from app.database.base import Base
from app.database.session import get_db
from app.main import app

# ---------------------------------------------------------------------------
# Test database — SQLite for test isolation
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


# ---------------------------------------------------------------------------
# Auth Helper Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def faculty_user(client: TestClient) -> dict:
    data = {
        "full_name": "Prof. Charles Xavier",
        "email": "faculty1@university.edu",
        "password": "FacultyPass@123",
        "role": "FACULTY",
    }
    client.post("/api/auth/register", json=data)
    res = client.post("/api/auth/login", json={"email": data["email"], "password": data["password"]})
    token = res.json()["access_token"]
    return {"token": token, "headers": {"Authorization": f"Bearer {token}"}, "email": data["email"]}


@pytest.fixture
def other_faculty_user(client: TestClient) -> dict:
    data = {
        "full_name": "Prof. Magneto Lensherr",
        "email": "faculty2@university.edu",
        "password": "FacultyPass@456",
        "role": "FACULTY",
    }
    client.post("/api/auth/register", json=data)
    res = client.post("/api/auth/login", json={"email": data["email"], "password": data["password"]})
    token = res.json()["access_token"]
    return {"token": token, "headers": {"Authorization": f"Bearer {token}"}, "email": data["email"]}


@pytest.fixture
def student_user(client: TestClient) -> dict:
    data = {
        "full_name": "Peter Parker",
        "email": "student1@university.edu",
        "password": "StudentPass@123",
        "role": "STUDENT",
    }
    client.post("/api/auth/register", json=data)
    res = client.post("/api/auth/login", json={"email": data["email"], "password": data["password"]})
    token = res.json()["access_token"]
    return {"token": token, "headers": {"Authorization": f"Bearer {token}"}, "email": data["email"]}


@pytest.fixture
def other_student_user(client: TestClient) -> dict:
    data = {
        "full_name": "Miles Morales",
        "email": "student2@university.edu",
        "password": "StudentPass@456",
        "role": "STUDENT",
    }
    client.post("/api/auth/register", json=data)
    res = client.post("/api/auth/login", json={"email": data["email"], "password": data["password"]})
    token = res.json()["access_token"]
    return {"token": token, "headers": {"Authorization": f"Bearer {token}"}, "email": data["email"]}
