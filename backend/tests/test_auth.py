"""
Tests for authentication endpoints — Phase 1.

Covers:
  1. Successful student registration
  2. Successful faculty registration
  3. Duplicate email registration
  4. Invalid password (complexity)
  5. Short password
  6. Successful login
  7. Login with wrong password
  8. Login with non-existent email
  9. GET /api/auth/me with valid JWT
 10. GET /api/auth/me with invalid JWT
 11. Student accessing student-only endpoint
 12. Faculty accessing faculty-only endpoint
 13. Student accessing faculty-only endpoint (expect 403)
 14. Faculty accessing student-only endpoint (expect 403)
 15. Unauthenticated access to protected endpoint (expect 401)
"""

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

STUDENT_DATA = {
    "full_name": "Alice Student",
    "email": "alice@university.edu",
    "password": "Secure@1234",
    "role": "STUDENT",
}

FACULTY_DATA = {
    "full_name": "Dr. Bob Faculty",
    "email": "bob@university.edu",
    "password": "Faculty@5678",
    "role": "FACULTY",
}


def register_and_login(client: TestClient, user_data: dict) -> str:
    """Register a user and return their JWT access token."""
    client.post("/api/auth/register", json=user_data)
    response = client.post(
        "/api/auth/login",
        json={"email": user_data["email"], "password": user_data["password"]},
    )
    return response.json()["access_token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Registration tests
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_register_student_success(self, client: TestClient):
        response = client.post("/api/auth/register", json=STUDENT_DATA)
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == STUDENT_DATA["email"]
        assert data["role"] == "STUDENT"
        assert data["is_active"] is True
        assert "password" not in data
        assert "password_hash" not in data

    def test_register_faculty_success(self, client: TestClient):
        response = client.post("/api/auth/register", json=FACULTY_DATA)
        assert response.status_code == 201
        data = response.json()
        assert data["role"] == "FACULTY"

    def test_register_duplicate_email(self, client: TestClient):
        client.post("/api/auth/register", json=STUDENT_DATA)
        response = client.post("/api/auth/register", json=STUDENT_DATA)
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]

    def test_register_invalid_password_no_uppercase(self, client: TestClient):
        data = {**STUDENT_DATA, "email": "new@uni.edu", "password": "lowercase123"}
        response = client.post("/api/auth/register", json=data)
        assert response.status_code == 422

    def test_register_password_too_short(self, client: TestClient):
        data = {**STUDENT_DATA, "email": "short@uni.edu", "password": "Ab1"}
        response = client.post("/api/auth/register", json=data)
        assert response.status_code == 422

    def test_register_invalid_email(self, client: TestClient):
        data = {**STUDENT_DATA, "email": "not-an-email"}
        response = client.post("/api/auth/register", json=data)
        assert response.status_code == 422

    def test_register_blank_full_name(self, client: TestClient):
        data = {**STUDENT_DATA, "email": "blank@uni.edu", "full_name": "   "}
        response = client.post("/api/auth/register", json=data)
        assert response.status_code == 422

    def test_register_invalid_role(self, client: TestClient):
        data = {**STUDENT_DATA, "email": "role@uni.edu", "role": "ADMIN"}
        response = client.post("/api/auth/register", json=data)
        assert response.status_code == 422

    def test_password_not_returned_in_response(self, client: TestClient):
        response = client.post("/api/auth/register", json=STUDENT_DATA)
        body = response.text
        assert "password_hash" not in body
        assert STUDENT_DATA["password"] not in body


# ---------------------------------------------------------------------------
# Login tests
# ---------------------------------------------------------------------------

class TestLogin:
    def test_login_success(self, client: TestClient):
        client.post("/api/auth/register", json=STUDENT_DATA)
        response = client.post(
            "/api/auth/login",
            json={"email": STUDENT_DATA["email"], "password": STUDENT_DATA["password"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["role"] == "STUDENT"
        assert "password" not in data
        assert "password_hash" not in data

    def test_login_wrong_password(self, client: TestClient):
        client.post("/api/auth/register", json=STUDENT_DATA)
        response = client.post(
            "/api/auth/login",
            json={"email": STUDENT_DATA["email"], "password": "WrongPass9!"},
        )
        assert response.status_code == 401

    def test_login_nonexistent_email(self, client: TestClient):
        response = client.post(
            "/api/auth/login",
            json={"email": "nobody@nowhere.com", "password": "Whatever1!"},
        )
        assert response.status_code == 401

    def test_login_case_insensitive_email(self, client: TestClient):
        """Email lookup should be case-insensitive."""
        client.post("/api/auth/register", json=STUDENT_DATA)
        response = client.post(
            "/api/auth/login",
            json={
                "email": STUDENT_DATA["email"].upper(),
                "password": STUDENT_DATA["password"],
            },
        )
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# /me endpoint tests
# ---------------------------------------------------------------------------

class TestGetMe:
    def test_get_me_authenticated(self, client: TestClient):
        token = register_and_login(client, STUDENT_DATA)
        response = client.get("/api/auth/me", headers=auth_headers(token))
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == STUDENT_DATA["email"]
        assert data["role"] == "STUDENT"
        assert "password_hash" not in data

    def test_get_me_no_token(self, client: TestClient):
        response = client.get("/api/auth/me")
        assert response.status_code == 401

    def test_get_me_invalid_token(self, client: TestClient):
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer this.is.not.a.valid.jwt"},
        )
        assert response.status_code == 401

    def test_get_me_malformed_header(self, client: TestClient):
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": "NotBearer sometoken"},
        )
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Role-based access control tests
# ---------------------------------------------------------------------------

class TestRBAC:
    def test_student_can_access_student_endpoint(self, client: TestClient):
        token = register_and_login(client, STUDENT_DATA)
        response = client.get("/api/student/dashboard", headers=auth_headers(token))
        assert response.status_code == 200
        assert "student" in response.json()["message"].lower()

    def test_faculty_can_access_faculty_endpoint(self, client: TestClient):
        token = register_and_login(client, FACULTY_DATA)
        response = client.get("/api/faculty/dashboard", headers=auth_headers(token))
        assert response.status_code == 200
        assert "faculty" in response.json()["message"].lower()

    def test_student_cannot_access_faculty_endpoint(self, client: TestClient):
        token = register_and_login(client, STUDENT_DATA)
        response = client.get("/api/faculty/dashboard", headers=auth_headers(token))
        assert response.status_code == 403

    def test_faculty_cannot_access_student_endpoint(self, client: TestClient):
        token = register_and_login(client, FACULTY_DATA)
        response = client.get("/api/student/dashboard", headers=auth_headers(token))
        assert response.status_code == 403

    def test_unauthenticated_cannot_access_student_endpoint(self, client: TestClient):
        response = client.get("/api/student/dashboard")
        assert response.status_code == 401

    def test_unauthenticated_cannot_access_faculty_endpoint(self, client: TestClient):
        response = client.get("/api/faculty/dashboard")
        assert response.status_code == 401
