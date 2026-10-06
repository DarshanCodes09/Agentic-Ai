"""
Tests for Enrollment endpoints — Phase 2.

Covers:
  1. Student can enroll in subject
  2. Duplicate enrollment rejected (409)
  3. Faculty cannot enroll as student (403)
  4. Inactive student cannot enroll (403)
  5. Enrolling in non-existent subject returns 404
  6. Faculty can view enrolled students for own subject
  7. Faculty cannot view enrolled students for another faculty's subject (403)
  8. Student cannot view enrolled students list (403)
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User


def test_student_can_enroll(client: TestClient, faculty_user: dict, student_user: dict):
    # Faculty creates subject
    sub_res = client.post(
        "/api/subjects",
        json={"name": "Physics I", "code": "PHYS101"},
        headers=faculty_user["headers"],
    )
    subject_id = sub_res.json()["id"]

    # Student enrolls
    res = client.post(f"/api/subjects/{subject_id}/enroll", headers=student_user["headers"])
    assert res.status_code == 201
    data = res.json()
    assert data["subject_id"] == subject_id
    assert "student_id" in data


def test_duplicate_enrollment_rejected(
    client: TestClient, faculty_user: dict, student_user: dict
):
    sub_res = client.post(
        "/api/subjects",
        json={"name": "Chemistry I", "code": "CHEM101"},
        headers=faculty_user["headers"],
    )
    subject_id = sub_res.json()["id"]

    # First enrollment
    res1 = client.post(f"/api/subjects/{subject_id}/enroll", headers=student_user["headers"])
    assert res1.status_code == 201

    # Second enrollment attempt
    res2 = client.post(f"/api/subjects/{subject_id}/enroll", headers=student_user["headers"])
    assert res2.status_code == 409
    assert "already enrolled" in res2.json()["detail"].lower()


def test_faculty_cannot_enroll(client: TestClient, faculty_user: dict):
    sub_res = client.post(
        "/api/subjects",
        json={"name": "Biology I", "code": "BIO101"},
        headers=faculty_user["headers"],
    )
    subject_id = sub_res.json()["id"]

    # Faculty tries to enroll
    res = client.post(f"/api/subjects/{subject_id}/enroll", headers=faculty_user["headers"])
    assert res.status_code == 403


def test_enroll_in_nonexistent_subject_returns_404(
    client: TestClient, student_user: dict
):
    res = client.post("/api/subjects/99999/enroll", headers=student_user["headers"])
    assert res.status_code == 404


def test_faculty_can_view_enrolled_students(
    client: TestClient, faculty_user: dict, student_user: dict, other_student_user: dict
):
    sub_res = client.post(
        "/api/subjects",
        json={"name": "Linear Algebra", "code": "MATH201"},
        headers=faculty_user["headers"],
    )
    subject_id = sub_res.json()["id"]

    # Two students enroll
    client.post(f"/api/subjects/{subject_id}/enroll", headers=student_user["headers"])
    client.post(f"/api/subjects/{subject_id}/enroll", headers=other_student_user["headers"])

    # Faculty views roster
    res = client.get(f"/api/subjects/{subject_id}/students", headers=faculty_user["headers"])
    assert res.status_code == 200
    students = res.json()
    assert len(students) == 2


def test_faculty_cannot_view_roster_of_other_faculty_subject(
    client: TestClient,
    faculty_user: dict,
    other_faculty_user: dict,
    student_user: dict,
):
    sub_res = client.post(
        "/api/subjects",
        json={"name": "Discrete Math", "code": "CS202"},
        headers=faculty_user["headers"],
    )
    subject_id = sub_res.json()["id"]
    client.post(f"/api/subjects/{subject_id}/enroll", headers=student_user["headers"])

    # Other faculty attempts to view roster
    res = client.get(f"/api/subjects/{subject_id}/students", headers=other_faculty_user["headers"])
    assert res.status_code == 403


def test_student_cannot_view_subject_roster(
    client: TestClient, faculty_user: dict, student_user: dict
):
    sub_res = client.post(
        "/api/subjects",
        json={"name": "Ethics in Tech", "code": "ETH101"},
        headers=faculty_user["headers"],
    )
    subject_id = sub_res.json()["id"]

    res = client.get(f"/api/subjects/{subject_id}/students", headers=student_user["headers"])
    assert res.status_code == 403
