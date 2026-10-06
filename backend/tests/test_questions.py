"""
Tests for Questions endpoints — Phase 2.

Covers:
  1. Faculty can add question
  2. Student cannot add question (403)
  3. Duplicate question_number rejected (409)
  4. Invalid marks rejected (422)
  5. Faculty can update question
  6. Faculty cannot update question for another faculty's assignment (403)
  7. Enrolled student can list questions
  8. Unenrolled student cannot list questions (403)
  9. Faculty can delete question
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


def test_faculty_can_add_question(client: TestClient, faculty_user: dict):
    _, asg_id = create_subject_and_assignment(client, faculty_user["headers"], "Q_SUB1")

    payload = {
        "question_number": 1,
        "question_text": "Explain the difference between TCP and UDP.",
        "marks": 10.0,
        "expected_concepts": ["connection-oriented", "handshake", "packet loss", "latency"],
    }
    res = client.post(
        f"/api/assignments/{asg_id}/questions",
        json=payload,
        headers=faculty_user["headers"],
    )
    assert res.status_code == 201
    data = res.json()
    assert data["question_number"] == 1
    assert data["marks"] == 10.0
    assert "handshake" in data["expected_concepts"]


def test_student_cannot_add_question(
    client: TestClient, faculty_user: dict, student_user: dict
):
    _, asg_id = create_subject_and_assignment(client, faculty_user["headers"], "Q_SUB2")

    payload = {
        "question_number": 1,
        "question_text": "Student attempting to add question",
        "marks": 5.0,
    }
    res = client.post(
        f"/api/assignments/{asg_id}/questions",
        json=payload,
        headers=student_user["headers"],
    )
    assert res.status_code == 403


def test_duplicate_question_number_rejected(client: TestClient, faculty_user: dict):
    _, asg_id = create_subject_and_assignment(client, faculty_user["headers"], "Q_SUB3")

    payload1 = {"question_number": 1, "question_text": "Q1 Text", "marks": 5.0}
    res1 = client.post(f"/api/assignments/{asg_id}/questions", json=payload1, headers=faculty_user["headers"])
    assert res1.status_code == 201

    payload2 = {"question_number": 1, "question_text": "Duplicate Q1 Text", "marks": 10.0}
    res2 = client.post(f"/api/assignments/{asg_id}/questions", json=payload2, headers=faculty_user["headers"])
    assert res2.status_code == 409
    assert "already exists" in res2.json()["detail"].lower()


def test_invalid_marks_rejected(client: TestClient, faculty_user: dict):
    _, asg_id = create_subject_and_assignment(client, faculty_user["headers"], "Q_SUB4")

    res = client.post(
        f"/api/assignments/{asg_id}/questions",
        json={"question_number": 1, "question_text": "Text", "marks": 0.0},
        headers=faculty_user["headers"],
    )
    assert res.status_code == 422


def test_faculty_can_update_question(client: TestClient, faculty_user: dict):
    _, asg_id = create_subject_and_assignment(client, faculty_user["headers"], "Q_SUB5")

    q_res = client.post(
        f"/api/assignments/{asg_id}/questions",
        json={"question_number": 1, "question_text": "Original text", "marks": 5.0},
        headers=faculty_user["headers"],
    )
    question_id = q_res.json()["id"]

    update_res = client.put(
        f"/api/questions/{question_id}",
        json={"question_text": "Updated text", "marks": 8.0},
        headers=faculty_user["headers"],
    )
    assert update_res.status_code == 200
    assert update_res.json()["question_text"] == "Updated text"
    assert update_res.json()["marks"] == 8.0


def test_faculty_cannot_update_other_faculty_question(
    client: TestClient, faculty_user: dict, other_faculty_user: dict
):
    _, asg_id = create_subject_and_assignment(client, faculty_user["headers"], "Q_SUB6")

    q_res = client.post(
        f"/api/assignments/{asg_id}/questions",
        json={"question_number": 1, "question_text": "Fac 1 Question", "marks": 5.0},
        headers=faculty_user["headers"],
    )
    question_id = q_res.json()["id"]

    update_res = client.put(
        f"/api/questions/{question_id}",
        json={"question_text": "Fac 2 Attempt"},
        headers=other_faculty_user["headers"],
    )
    assert update_res.status_code == 403


def test_enrolled_student_can_list_questions(
    client: TestClient, faculty_user: dict, student_user: dict
):
    sub_id, asg_id = create_subject_and_assignment(client, faculty_user["headers"], "Q_SUB7")
    client.post(
        f"/api/assignments/{asg_id}/questions",
        json={"question_number": 1, "question_text": "Question 1", "marks": 10.0},
        headers=faculty_user["headers"],
    )

    # Student enrolls
    client.post(f"/api/subjects/{sub_id}/enroll", headers=student_user["headers"])

    # Student views questions
    res = client.get(f"/api/assignments/{asg_id}/questions", headers=student_user["headers"])
    assert res.status_code == 200
    questions = res.json()
    assert len(questions) == 1
    assert questions[0]["question_number"] == 1


def test_unenrolled_student_cannot_list_questions(
    client: TestClient, faculty_user: dict, student_user: dict
):
    _, asg_id = create_subject_and_assignment(client, faculty_user["headers"], "Q_SUB8")

    res = client.get(f"/api/assignments/{asg_id}/questions", headers=student_user["headers"])
    assert res.status_code == 403


def test_faculty_can_delete_question(client: TestClient, faculty_user: dict):
    _, asg_id = create_subject_and_assignment(client, faculty_user["headers"], "Q_SUB9")
    q_res = client.post(
        f"/api/assignments/{asg_id}/questions",
        json={"question_number": 1, "question_text": "To Delete", "marks": 5.0},
        headers=faculty_user["headers"],
    )
    question_id = q_res.json()["id"]

    del_res = client.delete(f"/api/questions/{question_id}", headers=faculty_user["headers"])
    assert del_res.status_code == 204
