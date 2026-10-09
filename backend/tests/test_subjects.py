"""
Tests for Subjects endpoints — Phase 2.

Covers:
  1. Faculty can create subject
  2. Student cannot create subject (403)
  3. Faculty can update own subject
  4. Faculty cannot update another faculty's subject (403)
  5. Duplicate subject code rejected (409)
  6. Faculty can delete own subject
  7. Faculty cannot delete another faculty's subject (403)
  8. Unauthenticated access rejected (401)
  9. Student and faculty can list subjects
 10. Non-existent subject returns 404
"""

import pytest
from fastapi.testclient import TestClient


def test_faculty_can_create_subject(client: TestClient, faculty_user: dict):
    payload = {
        "name": "Introduction to Computer Science",
        "code": "CS101",
        "description": "Foundational course on computing principles",
    }
    response = client.post("/api/subjects", json=payload, headers=faculty_user["headers"])
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == payload["name"]
    assert data["code"] == payload["code"]
    assert data["faculty_id"] is not None
    assert "id" in data


def test_student_cannot_create_subject(client: TestClient, student_user: dict):
    payload = {
        "name": "Unauthorized Subject",
        "code": "CS999",
        "description": "Student attempt",
    }
    response = client.post("/api/subjects", json=payload, headers=student_user["headers"])
    assert response.status_code == 403


def test_duplicate_subject_code_rejected(client: TestClient, faculty_user: dict):
    payload = {
        "name": "Algorithms",
        "code": "CS201",
        "description": "Data structures and algorithms",
    }
    res1 = client.post("/api/subjects", json=payload, headers=faculty_user["headers"])
    assert res1.status_code == 201

    res2 = client.post("/api/subjects", json=payload, headers=faculty_user["headers"])
    assert res2.status_code == 409
    assert "already exists" in res2.json()["detail"].lower()


def test_faculty_can_update_own_subject(client: TestClient, faculty_user: dict):
    # Create
    create_res = client.post(
        "/api/subjects",
        json={"name": "Database Systems", "code": "CS301", "description": "SQL basics"},
        headers=faculty_user["headers"],
    )
    subject_id = create_res.json()["id"]

    # Update
    update_res = client.put(
        f"/api/subjects/{subject_id}",
        json={"name": "Advanced Database Systems", "description": "PostgreSQL & indexing"},
        headers=faculty_user["headers"],
    )
    assert update_res.status_code == 200
    assert update_res.json()["name"] == "Advanced Database Systems"


def test_faculty_cannot_update_another_facultys_subject(
    client: TestClient, faculty_user: dict, other_faculty_user: dict
):
    # Faculty 1 creates
    create_res = client.post(
        "/api/subjects",
        json={"name": "Operating Systems", "code": "CS401"},
        headers=faculty_user["headers"],
    )
    subject_id = create_res.json()["id"]

    # Faculty 2 attempts update
    update_res = client.put(
        f"/api/subjects/{subject_id}",
        json={"name": "Hacked OS"},
        headers=other_faculty_user["headers"],
    )
    assert update_res.status_code == 403


def test_faculty_can_delete_own_subject(client: TestClient, faculty_user: dict):
    create_res = client.post(
        "/api/subjects",
        json={"name": "Subject to Delete", "code": "DEL101"},
        headers=faculty_user["headers"],
    )
    subject_id = create_res.json()["id"]

    del_res = client.delete(f"/api/subjects/{subject_id}", headers=faculty_user["headers"])
    assert del_res.status_code == 204


def test_faculty_cannot_delete_another_facultys_subject(
    client: TestClient, faculty_user: dict, other_faculty_user: dict
):
    create_res = client.post(
        "/api/subjects",
        json={"name": "Protected Subject", "code": "PROT101"},
        headers=faculty_user["headers"],
    )
    subject_id = create_res.json()["id"]

    del_res = client.delete(f"/api/subjects/{subject_id}", headers=other_faculty_user["headers"])
    assert del_res.status_code == 403


def test_unauthenticated_subject_creation_rejected(client: TestClient):
    response = client.post("/api/subjects", json={"name": "Anon", "code": "ANON101"})
    assert response.status_code == 401


def test_list_subjects(client: TestClient, faculty_user: dict, student_user: dict):
    subject_res = client.post(
        "/api/subjects",
        json={"name": "Math 101", "code": "MATH101"},
        headers=faculty_user["headers"],
    )
    subject_id = subject_res.json()["id"]

    # Student listing is enrolled-only.
    res_student = client.get("/api/subjects", headers=student_user["headers"])
    assert res_student.status_code == 200
    assert res_student.json() == []

    client.post(f"/api/subjects/{subject_id}/enroll", headers=student_user["headers"])
    res_student_enrolled = client.get("/api/subjects", headers=student_user["headers"])
    assert res_student_enrolled.status_code == 200
    assert [subject["id"] for subject in res_student_enrolled.json()] == [subject_id]

    # Faculty listing
    res_faculty = client.get("/api/subjects", headers=faculty_user["headers"])
    assert res_faculty.status_code == 200
    assert len(res_faculty.json()) >= 1


def test_get_nonexistent_subject_returns_404(client: TestClient, faculty_user: dict):
    response = client.get("/api/subjects/99999", headers=faculty_user["headers"])
    assert response.status_code == 404
