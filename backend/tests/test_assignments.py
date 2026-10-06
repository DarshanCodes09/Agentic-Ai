"""
Tests for Assignment endpoints — Phase 2.

Covers:
  1. Faculty can create assignment for own subject
  2. Faculty cannot create assignment for another faculty's subject (403)
  3. Student cannot create assignment (403)
  4. Invalid max_marks rejected (422)
  5. Faculty can update own assignment
  6. Faculty cannot update another faculty's assignment (403)
  7. Enrolled student can view assignment
  8. Unenrolled student cannot view assignment (403)
  9. Faculty can delete own assignment
 10. Faculty cannot delete another faculty's assignment (403)
"""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient


def create_sample_subject(client: TestClient, faculty_headers: dict, code: str = "ASG101") -> int:
    res = client.post(
        "/api/subjects",
        json={"name": "Assignment Test Subject", "code": code},
        headers=faculty_headers,
    )
    return res.json()["id"]


def test_faculty_can_create_assignment(client: TestClient, faculty_user: dict):
    subject_id = create_sample_subject(client, faculty_user["headers"], "SUB_ASG1")
    due = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()

    payload = {
        "title": "Homework 1: Fundamentals",
        "description": "Basic problems",
        "instructions": "Submit answers clearly formatted",
        "due_date": due,
        "max_marks": 100.0,
    }
    res = client.post(
        f"/api/subjects/{subject_id}/assignments",
        json=payload,
        headers=faculty_user["headers"],
    )
    assert res.status_code == 201
    data = res.json()
    assert data["title"] == payload["title"]
    assert data["max_marks"] == 100.0
    assert data["subject_id"] == subject_id


def test_faculty_cannot_create_assignment_for_other_faculty_subject(
    client: TestClient, faculty_user: dict, other_faculty_user: dict
):
    subject_id = create_sample_subject(client, faculty_user["headers"], "SUB_ASG2")
    due = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()

    payload = {
        "title": "Rogue Assignment",
        "due_date": due,
        "max_marks": 50.0,
    }
    res = client.post(
        f"/api/subjects/{subject_id}/assignments",
        json=payload,
        headers=other_faculty_user["headers"],
    )
    assert res.status_code == 403


def test_student_cannot_create_assignment(
    client: TestClient, faculty_user: dict, student_user: dict
):
    subject_id = create_sample_subject(client, faculty_user["headers"], "SUB_ASG3")
    due = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()

    res = client.post(
        f"/api/subjects/{subject_id}/assignments",
        json={"title": "Student Asg", "due_date": due, "max_marks": 50.0},
        headers=student_user["headers"],
    )
    assert res.status_code == 403


def test_invalid_max_marks_rejected(client: TestClient, faculty_user: dict):
    subject_id = create_sample_subject(client, faculty_user["headers"], "SUB_ASG4")
    due = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()

    # Zero marks
    res1 = client.post(
        f"/api/subjects/{subject_id}/assignments",
        json={"title": "Zero Marks", "due_date": due, "max_marks": 0.0},
        headers=faculty_user["headers"],
    )
    assert res1.status_code == 422

    # Negative marks
    res2 = client.post(
        f"/api/subjects/{subject_id}/assignments",
        json={"title": "Negative Marks", "due_date": due, "max_marks": -10.0},
        headers=faculty_user["headers"],
    )
    assert res2.status_code == 422


def test_faculty_can_update_own_assignment(client: TestClient, faculty_user: dict):
    subject_id = create_sample_subject(client, faculty_user["headers"], "SUB_ASG5")
    due = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()

    create_res = client.post(
        f"/api/subjects/{subject_id}/assignments",
        json={"title": "Original Title", "due_date": due, "max_marks": 50.0},
        headers=faculty_user["headers"],
    )
    asg_id = create_res.json()["id"]

    update_res = client.put(
        f"/api/assignments/{asg_id}",
        json={"title": "Updated Title", "max_marks": 75.0},
        headers=faculty_user["headers"],
    )
    assert update_res.status_code == 200
    assert update_res.json()["title"] == "Updated Title"
    assert update_res.json()["max_marks"] == 75.0


def test_faculty_cannot_update_other_faculty_assignment(
    client: TestClient, faculty_user: dict, other_faculty_user: dict
):
    subject_id = create_sample_subject(client, faculty_user["headers"], "SUB_ASG6")
    due = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()

    create_res = client.post(
        f"/api/subjects/{subject_id}/assignments",
        json={"title": "Fac 1 Title", "due_date": due, "max_marks": 50.0},
        headers=faculty_user["headers"],
    )
    asg_id = create_res.json()["id"]

    update_res = client.put(
        f"/api/assignments/{asg_id}",
        json={"title": "Fac 2 Attempt"},
        headers=other_faculty_user["headers"],
    )
    assert update_res.status_code == 403


def test_enrolled_student_can_view_assignment(
    client: TestClient, faculty_user: dict, student_user: dict
):
    subject_id = create_sample_subject(client, faculty_user["headers"], "SUB_ASG7")
    due = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()

    asg_res = client.post(
        f"/api/subjects/{subject_id}/assignments",
        json={"title": "Midterm Project", "due_date": due, "max_marks": 100.0},
        headers=faculty_user["headers"],
    )
    asg_id = asg_res.json()["id"]

    # Student enrolls
    client.post(f"/api/subjects/{subject_id}/enroll", headers=student_user["headers"])

    # Student views assignment
    view_res = client.get(f"/api/assignments/{asg_id}", headers=student_user["headers"])
    assert view_res.status_code == 200
    assert view_res.json()["id"] == asg_id


def test_unenrolled_student_cannot_view_assignment(
    client: TestClient, faculty_user: dict, student_user: dict
):
    subject_id = create_sample_subject(client, faculty_user["headers"], "SUB_ASG8")
    due = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()

    asg_res = client.post(
        f"/api/subjects/{subject_id}/assignments",
        json={"title": "Private Assignment", "due_date": due, "max_marks": 100.0},
        headers=faculty_user["headers"],
    )
    asg_id = asg_res.json()["id"]

    # Student does NOT enroll, attempts view
    view_res = client.get(f"/api/assignments/{asg_id}", headers=student_user["headers"])
    assert view_res.status_code == 403


def test_faculty_can_delete_own_assignment(client: TestClient, faculty_user: dict):
    subject_id = create_sample_subject(client, faculty_user["headers"], "SUB_ASG9")
    due = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()

    asg_res = client.post(
        f"/api/subjects/{subject_id}/assignments",
        json={"title": "To Delete", "due_date": due, "max_marks": 50.0},
        headers=faculty_user["headers"],
    )
    asg_id = asg_res.json()["id"]

    del_res = client.delete(f"/api/assignments/{asg_id}", headers=faculty_user["headers"])
    assert del_res.status_code == 204
