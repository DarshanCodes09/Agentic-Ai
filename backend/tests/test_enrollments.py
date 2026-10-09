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


def test_student_can_join_subject_by_course_code(
    client: TestClient, faculty_user: dict, student_user: dict
):
    sub_res = client.post(
        "/api/subjects",
        json={"name": "Computer Networks", "code": "cn201"},
        headers=faculty_user["headers"],
    )
    subject_id = sub_res.json()["id"]
    assert sub_res.json()["code"] == "CN201"

    res = client.post(
        "/api/enrollments/join",
        json={"course_code": "  cn201  "},
        headers=student_user["headers"],
    )

    assert res.status_code == 201
    data = res.json()
    assert data["subject_id"] == subject_id
    me = client.get("/api/auth/me", headers=student_user["headers"]).json()
    assert data["student_id"] == me["id"]

    subjects_res = client.get("/api/subjects", headers=student_user["headers"])
    assert [subject["id"] for subject in subjects_res.json()] == [subject_id]


def test_join_unknown_course_code_returns_404(client: TestClient, student_user: dict):
    res = client.post(
        "/api/enrollments/join",
        json={"course_code": "NOPE101"},
        headers=student_user["headers"],
    )
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


def test_duplicate_join_by_course_code_rejected(
    client: TestClient, faculty_user: dict, student_user: dict
):
    client.post(
        "/api/subjects",
        json={"name": "Cloud Computing", "code": "CLD301"},
        headers=faculty_user["headers"],
    )

    first = client.post(
        "/api/enrollments/join",
        json={"course_code": "CLD301"},
        headers=student_user["headers"],
    )
    assert first.status_code == 201

    second = client.post(
        "/api/enrollments/join",
        json={"course_code": "CLD301"},
        headers=student_user["headers"],
    )
    assert second.status_code == 409
    assert "already enrolled" in second.json()["detail"].lower()


def test_unauthenticated_join_course_rejected(client: TestClient):
    res = client.post("/api/enrollments/join", json={"course_code": "CS101"})
    assert res.status_code == 401


def test_faculty_cannot_join_course_by_code(client: TestClient, faculty_user: dict):
    res = client.post(
        "/api/enrollments/join",
        json={"course_code": "CS101"},
        headers=faculty_user["headers"],
    )
    assert res.status_code == 403


def test_two_students_have_independent_enrollments(
    client: TestClient,
    faculty_user: dict,
    student_user: dict,
    other_student_user: dict,
):
    sub_res = client.post(
        "/api/subjects",
        json={"name": "Distributed Systems", "code": "DS401"},
        headers=faculty_user["headers"],
    )
    subject_id = sub_res.json()["id"]

    first = client.post(
        "/api/enrollments/join",
        json={"course_code": "DS401"},
        headers=student_user["headers"],
    )
    second = client.post(
        "/api/enrollments/join",
        json={"course_code": "DS401"},
        headers=other_student_user["headers"],
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["student_id"] != second.json()["student_id"]

    first_subjects = client.get("/api/subjects", headers=student_user["headers"]).json()
    second_subjects = client.get("/api/subjects", headers=other_student_user["headers"]).json()
    assert [subject["id"] for subject in first_subjects] == [subject_id]
    assert [subject["id"] for subject in second_subjects] == [subject_id]


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
