"""
Tests for Rubrics and Rubric Items endpoints — Phase 2.

Covers:
  1. Faculty can create rubric
  2. Student cannot create rubric (403)
  3. Duplicate rubric for same assignment rejected (409)
  4. Faculty can add rubric items
  5. Faculty can update rubric item
  6. Faculty cannot update another faculty's rubric item (403)
  7. Enrolled student can view rubric
  8. Unenrolled student cannot view rubric (403)
  9. Faculty can delete rubric item
"""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient


def create_subject_and_assignment(client: TestClient, faculty_headers: dict, code: str) -> tuple[int, int]:
    sub_res = client.post("/api/subjects", json={"name": "Sub", "code": code}, headers=faculty_headers)
    subject_id = sub_res.json()["id"]

    due = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    asg_res = client.post(
        f"/api/subjects/{subject_id}/assignments",
        json={"title": "Asg", "due_date": due, "max_marks": 100.0},
        headers=faculty_headers,
    )
    assignment_id = asg_res.json()["id"]
    return subject_id, assignment_id


def test_faculty_can_create_rubric(client: TestClient, faculty_user: dict):
    _, asg_id = create_subject_and_assignment(client, faculty_user["headers"], "RUB_SUB1")

    payload = {
        "name": "Standard Assessment Rubric",
        "description": "Grading criteria for midterm project",
        "items": [
            {"criterion": "Code Quality", "description": "Clean, readable, idiomatic code", "max_marks": 25.0},
            {"criterion": "Correctness", "description": "Passes all test cases", "max_marks": 50.0},
        ],
    }
    res = client.post(
        f"/api/assignments/{asg_id}/rubric",
        json=payload,
        headers=faculty_user["headers"],
    )
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == payload["name"]
    assert len(data["items"]) == 2
    assert data["assignment_id"] == asg_id


def test_student_cannot_create_rubric(
    client: TestClient, faculty_user: dict, student_user: dict
):
    _, asg_id = create_subject_and_assignment(client, faculty_user["headers"], "RUB_SUB2")

    res = client.post(
        f"/api/assignments/{asg_id}/rubric",
        json={"name": "Student Rubric"},
        headers=student_user["headers"],
    )
    assert res.status_code == 403


def test_duplicate_rubric_rejected(client: TestClient, faculty_user: dict):
    _, asg_id = create_subject_and_assignment(client, faculty_user["headers"], "RUB_SUB3")

    res1 = client.post(
        f"/api/assignments/{asg_id}/rubric",
        json={"name": "Rubric 1"},
        headers=faculty_user["headers"],
    )
    assert res1.status_code == 201

    res2 = client.post(
        f"/api/assignments/{asg_id}/rubric",
        json={"name": "Rubric 2"},
        headers=faculty_user["headers"],
    )
    assert res2.status_code == 409
    assert "already exists" in res2.json()["detail"].lower()


def test_faculty_can_add_rubric_item(client: TestClient, faculty_user: dict):
    _, asg_id = create_subject_and_assignment(client, faculty_user["headers"], "RUB_SUB4")

    rub_res = client.post(
        f"/api/assignments/{asg_id}/rubric",
        json={"name": "Rubric Base"},
        headers=faculty_user["headers"],
    )
    rubric_id = rub_res.json()["id"]

    item_payload = {
        "criterion": "Documentation",
        "description": "README and docstrings present",
        "max_marks": 15.0,
    }
    res = client.post(
        f"/api/rubrics/{rubric_id}/items",
        json=item_payload,
        headers=faculty_user["headers"],
    )
    assert res.status_code == 201
    assert res.json()["criterion"] == "Documentation"
    assert res.json()["max_marks"] == 15.0


def test_faculty_can_update_rubric_item(client: TestClient, faculty_user: dict):
    _, asg_id = create_subject_and_assignment(client, faculty_user["headers"], "RUB_SUB5")

    rub_res = client.post(
        f"/api/assignments/{asg_id}/rubric",
        json={"name": "Rubric Base"},
        headers=faculty_user["headers"],
    )
    rubric_id = rub_res.json()["id"]

    item_res = client.post(
        f"/api/rubrics/{rubric_id}/items",
        json={"criterion": "Old Criterion", "max_marks": 10.0},
        headers=faculty_user["headers"],
    )
    item_id = item_res.json()["id"]

    update_res = client.put(
        f"/api/rubric-items/{item_id}",
        json={"criterion": "New Criterion", "max_marks": 20.0},
        headers=faculty_user["headers"],
    )
    assert update_res.status_code == 200
    assert update_res.json()["criterion"] == "New Criterion"
    assert update_res.json()["max_marks"] == 20.0


def test_faculty_cannot_update_other_faculty_rubric_item(
    client: TestClient, faculty_user: dict, other_faculty_user: dict
):
    _, asg_id = create_subject_and_assignment(client, faculty_user["headers"], "RUB_SUB6")

    rub_res = client.post(
        f"/api/assignments/{asg_id}/rubric",
        json={"name": "Fac 1 Rubric"},
        headers=faculty_user["headers"],
    )
    rubric_id = rub_res.json()["id"]

    item_res = client.post(
        f"/api/rubrics/{rubric_id}/items",
        json={"criterion": "Fac 1 Item", "max_marks": 10.0},
        headers=faculty_user["headers"],
    )
    item_id = item_res.json()["id"]

    update_res = client.put(
        f"/api/rubric-items/{item_id}",
        json={"criterion": "Hacked Criterion"},
        headers=other_faculty_user["headers"],
    )
    assert update_res.status_code == 403


def test_enrolled_student_can_view_rubric(
    client: TestClient, faculty_user: dict, student_user: dict
):
    sub_id, asg_id = create_subject_and_assignment(client, faculty_user["headers"], "RUB_SUB7")
    client.post(
        f"/api/assignments/{asg_id}/rubric",
        json={
            "name": "Visible Rubric",
            "items": [{"criterion": "Completeness", "max_marks": 100.0}],
        },
        headers=faculty_user["headers"],
    )

    # Student enrolls
    client.post(f"/api/subjects/{sub_id}/enroll", headers=student_user["headers"])

    # Student views rubric
    res = client.get(f"/api/assignments/{asg_id}/rubric", headers=student_user["headers"])
    assert res.status_code == 200
    assert res.json()["name"] == "Visible Rubric"
    assert len(res.json()["items"]) == 1


def test_unenrolled_student_cannot_view_rubric(
    client: TestClient, faculty_user: dict, student_user: dict
):
    _, asg_id = create_subject_and_assignment(client, faculty_user["headers"], "RUB_SUB8")
    client.post(
        f"/api/assignments/{asg_id}/rubric",
        json={"name": "Hidden Rubric"},
        headers=faculty_user["headers"],
    )

    res = client.get(f"/api/assignments/{asg_id}/rubric", headers=student_user["headers"])
    assert res.status_code == 403


def test_faculty_can_delete_rubric_item(client: TestClient, faculty_user: dict):
    _, asg_id = create_subject_and_assignment(client, faculty_user["headers"], "RUB_SUB9")
    rub_res = client.post(
        f"/api/assignments/{asg_id}/rubric",
        json={"name": "Rubric Item Delete"},
        headers=faculty_user["headers"],
    )
    rubric_id = rub_res.json()["id"]

    item_res = client.post(
        f"/api/rubrics/{rubric_id}/items",
        json={"criterion": "To Delete", "max_marks": 5.0},
        headers=faculty_user["headers"],
    )
    item_id = item_res.json()["id"]

    del_res = client.delete(f"/api/rubric-items/{item_id}", headers=faculty_user["headers"])
    assert del_res.status_code == 204
