"""
Tests for Submissions endpoints — Phase 2.

Covers:
  1. Enrolled student can submit text
  2. Enrolled student can submit PDF file
  3. Enrolled student can submit DOCX file
  4. Non-enrolled student cannot submit (403)
  5. Student can view own submission
  6. Student cannot view another student's submission (403)
  7. Faculty can view submissions for own assignment
  8. Faculty cannot view submissions for another faculty's assignment (403)
  9. Unsupported file types rejected (422)
 10. Submitting without text and file rejected (422)
"""

import io
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


def test_enrolled_student_can_submit_text(
    client: TestClient, faculty_user: dict, student_user: dict
):
    sub_id, asg_id = create_subject_and_assignment(client, faculty_user["headers"], "SUBM_S1")
    # Enroll
    client.post(f"/api/subjects/{sub_id}/enroll", headers=student_user["headers"])

    # Submit JSON text
    payload = {"submission_text": "This is my solution to question 1 and 2."}
    res = client.post(
        f"/api/assignments/{asg_id}/submit",
        json=payload,
        headers=student_user["headers"],
    )
    assert res.status_code == 201
    data = res.json()
    assert data["assignment_id"] == asg_id
    assert data["submission_text"] == payload["submission_text"]
    assert data["status"] == "SUBMITTED"
    assert "id" in data


def test_enrolled_student_can_submit_pdf(
    client: TestClient, faculty_user: dict, student_user: dict
):
    sub_id, asg_id = create_subject_and_assignment(client, faculty_user["headers"], "SUBM_S2")
    client.post(f"/api/subjects/{sub_id}/enroll", headers=student_user["headers"])

    fake_pdf = io.BytesIO(b"%PDF-1.4 sample pdf content")
    files = {"file": ("report.pdf", fake_pdf, "application/pdf")}
    data = {"submission_text": "Attached report"}

    res = client.post(
        f"/api/assignments/{asg_id}/submit",
        data=data,
        files=files,
        headers=student_user["headers"],
    )
    assert res.status_code == 201
    resp_data = res.json()
    assert resp_data["original_filename"] == "report.pdf"
    assert resp_data["file_path"] is not None
    assert "submissions" in resp_data["file_path"]


def test_enrolled_student_can_submit_docx(
    client: TestClient, faculty_user: dict, student_user: dict
):
    sub_id, asg_id = create_subject_and_assignment(client, faculty_user["headers"], "SUBM_S3")
    client.post(f"/api/subjects/{sub_id}/enroll", headers=student_user["headers"])

    fake_docx = io.BytesIO(b"PK\x03\x04 fake docx bytes")
    files = {
        "file": (
            "essay.docx",
            fake_docx,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    }

    res = client.post(
        f"/api/assignments/{asg_id}/submit",
        files=files,
        headers=student_user["headers"],
    )
    assert res.status_code == 201
    assert res.json()["original_filename"] == "essay.docx"


def test_non_enrolled_student_cannot_submit(
    client: TestClient, faculty_user: dict, student_user: dict
):
    _, asg_id = create_subject_and_assignment(client, faculty_user["headers"], "SUBM_S4")

    # Student does NOT enroll
    payload = {"submission_text": "Unauthorized submission"}
    res = client.post(
        f"/api/assignments/{asg_id}/submit",
        json=payload,
        headers=student_user["headers"],
    )
    assert res.status_code == 403


def test_student_can_view_own_submission(
    client: TestClient, faculty_user: dict, student_user: dict
):
    sub_id, asg_id = create_subject_and_assignment(client, faculty_user["headers"], "SUBM_S5")
    client.post(f"/api/subjects/{sub_id}/enroll", headers=student_user["headers"])

    submit_res = client.post(
        f"/api/assignments/{asg_id}/submit",
        json={"submission_text": "My answers"},
        headers=student_user["headers"],
    )
    submission_id = submit_res.json()["id"]

    view_res = client.get(f"/api/submissions/{submission_id}", headers=student_user["headers"])
    assert view_res.status_code == 200
    assert view_res.json()["id"] == submission_id


def test_student_cannot_view_other_student_submission(
    client: TestClient,
    faculty_user: dict,
    student_user: dict,
    other_student_user: dict,
):
    sub_id, asg_id = create_subject_and_assignment(client, faculty_user["headers"], "SUBM_S6")
    client.post(f"/api/subjects/{sub_id}/enroll", headers=student_user["headers"])

    # Student 1 submits
    submit_res = client.post(
        f"/api/assignments/{asg_id}/submit",
        json={"submission_text": "Student 1 secret answer"},
        headers=student_user["headers"],
    )
    submission_id = submit_res.json()["id"]

    # Student 2 tries to view Student 1's submission
    view_res = client.get(f"/api/submissions/{submission_id}", headers=other_student_user["headers"])
    assert view_res.status_code == 403


def test_faculty_can_view_submissions_for_own_assignment(
    client: TestClient, faculty_user: dict, student_user: dict
):
    sub_id, asg_id = create_subject_and_assignment(client, faculty_user["headers"], "SUBM_S7")
    client.post(f"/api/subjects/{sub_id}/enroll", headers=student_user["headers"])

    client.post(
        f"/api/assignments/{asg_id}/submit",
        json={"submission_text": "Work for grading"},
        headers=student_user["headers"],
    )

    res = client.get(f"/api/assignments/{asg_id}/submissions", headers=faculty_user["headers"])
    assert res.status_code == 200
    submissions = res.json()
    assert len(submissions) == 1
    assert submissions[0]["submission_text"] == "Work for grading"


def test_faculty_cannot_view_submissions_for_other_faculty_assignment(
    client: TestClient,
    faculty_user: dict,
    other_faculty_user: dict,
    student_user: dict,
):
    sub_id, asg_id = create_subject_and_assignment(client, faculty_user["headers"], "SUBM_S8")
    client.post(f"/api/subjects/{sub_id}/enroll", headers=student_user["headers"])

    client.post(
        f"/api/assignments/{asg_id}/submit",
        json={"submission_text": "Class work"},
        headers=student_user["headers"],
    )

    # Other faculty attempts to list submissions
    res = client.get(f"/api/assignments/{asg_id}/submissions", headers=other_faculty_user["headers"])
    assert res.status_code == 403


def test_unsupported_file_types_rejected(
    client: TestClient, faculty_user: dict, student_user: dict
):
    sub_id, asg_id = create_subject_and_assignment(client, faculty_user["headers"], "SUBM_S9")
    client.post(f"/api/subjects/{sub_id}/enroll", headers=student_user["headers"])

    # Try uploading malicious .exe or script
    fake_exe = io.BytesIO(b"MZ\x90\x00 fake executable")
    files = {"file": ("malware.exe", fake_exe, "application/octet-stream")}

    res = client.post(
        f"/api/assignments/{asg_id}/submit",
        files=files,
        headers=student_user["headers"],
    )
    assert res.status_code == 422


def test_empty_submission_rejected(
    client: TestClient, faculty_user: dict, student_user: dict
):
    sub_id, asg_id = create_subject_and_assignment(client, faculty_user["headers"], "SUBM_S10")
    client.post(f"/api/subjects/{sub_id}/enroll", headers=student_user["headers"])

    res = client.post(
        f"/api/assignments/{asg_id}/submit",
        json={},
        headers=student_user["headers"],
    )
    assert res.status_code == 422
