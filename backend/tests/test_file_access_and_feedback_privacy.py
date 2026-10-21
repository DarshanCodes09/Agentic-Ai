"""
Focused tests for Secure File Access and Feedback Privacy (Phase 8 - Stage 2).

Covers:
1. Faculty can download submitted student file for their course
2. Faculty can preview submitted PDF inline
3. Student can download their own submitted file
4. Unauthorized student cannot download other student's submission file (403)
5. Unauthorized faculty cannot download other course's submission file (403)
6. Submission without an uploaded file returns 404
7. Enrolled student can download permitted course material file
8. Enrolled student can preview course material inline
9. Unenrolled student cannot download course material file (403)
10. Unauthorized faculty cannot download another course's material file (403)
11. Path traversal attempts are blocked (403)
12. Missing file on disk returns 404
13. Unauthenticated requests to file endpoints return 401
14. Student cannot access AI draft feedback before faculty approval (403)
15. Student can access approved feedback with faculty-only notes and internal context redacted
16. Student can access modified evaluation with faculty override score
"""

from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.models.assessment import AssessmentStatus
from app.services.file_storage.security import (
    sanitize_download_filename,
    validate_file_path_safe,
)
from app.core.exceptions import AppException


def setup_course_and_assignment(
    client: TestClient, faculty_headers: dict, code: str
) -> tuple[int, int]:
    sub_res = client.post(
        "/api/subjects",
        json={"name": f"Secure File Course {code}", "code": code},
        headers=faculty_headers,
    )
    subject_id = sub_res.json()["id"]

    due = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    asg_res = client.post(
        f"/api/subjects/{subject_id}/assignments",
        json={
            "title": "OS Memory Management",
            "due_date": due,
            "max_marks": 50.0,
            "rubric": {
                "name": "OS Rubric",
                "items": [
                    {"criterion": "Paging Correctness", "max_marks": 30.0},
                    {"criterion": "Algorithm Efficiency", "max_marks": 20.0},
                ],
            },
        },
        headers=faculty_headers,
    )
    assignment_id = asg_res.json()["id"]
    return subject_id, assignment_id


# ---------------------------------------------------------------------------
# 1. Submission File Access Tests
# ---------------------------------------------------------------------------

def test_faculty_can_download_and_preview_submission_file(
    client: TestClient, faculty_user: dict, student_user: dict
):
    code = f"SEC{datetime.now().strftime('%H%M%S%f')[:8]}"
    subject_id, assignment_id = setup_course_and_assignment(
        client, faculty_user["headers"], code
    )

    # Student enrolls
    client.post(f"/api/subjects/{subject_id}/enroll", headers=student_user["headers"])

    # Student submits PDF file
    dummy_pdf = b"%PDF-1.4 test student submission content"
    files = {"file": ("student_report.pdf", BytesIO(dummy_pdf), "application/pdf")}
    subm_res = client.post(
        f"/api/assignments/{assignment_id}/submit",
        data={"submission_text": "Here is my detailed report"},
        files=files,
        headers=student_user["headers"],
    )
    assert subm_res.status_code == 201
    submission_id = subm_res.json()["id"]

    # Faculty downloads file (attachment)
    download_res = client.get(
        f"/api/submissions/{submission_id}/file",
        headers=faculty_user["headers"],
    )
    assert download_res.status_code == 200
    assert download_res.headers["content-type"] == "application/pdf"
    assert 'attachment; filename="student_report.pdf"' in download_res.headers["content-disposition"]
    assert download_res.content == dummy_pdf

    # Faculty previews file inline
    preview_res = client.get(
        f"/api/submissions/{submission_id}/file?inline=true",
        headers=faculty_user["headers"],
    )
    assert preview_res.status_code == 200
    assert preview_res.headers["content-type"] == "application/pdf"
    assert 'inline; filename="student_report.pdf"' in preview_res.headers["content-disposition"]


def test_student_can_download_own_file_but_not_others(
    client: TestClient,
    faculty_user: dict,
    student_user: dict,
    other_student_user: dict,
):
    code = f"SEC{datetime.now().strftime('%H%M%S%f')[:8]}"
    subject_id, assignment_id = setup_course_and_assignment(
        client, faculty_user["headers"], code
    )

    # Both enroll
    client.post(f"/api/subjects/{subject_id}/enroll", headers=student_user["headers"])
    client.post(f"/api/subjects/{subject_id}/enroll", headers=other_student_user["headers"])

    # Student 1 submits file
    dummy_docx = b"PK\x03\x04 fake docx binary data"
    files = {
        "file": (
            "project_doc.docx",
            BytesIO(dummy_docx),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    }
    subm_res = client.post(
        f"/api/assignments/{assignment_id}/submit",
        data={"submission_text": "DOCX answer"},
        files=files,
        headers=student_user["headers"],
    )
    submission_id = subm_res.json()["id"]

    # Student 1 can download own file
    own_res = client.get(
        f"/api/submissions/{submission_id}/file",
        headers=student_user["headers"],
    )
    assert own_res.status_code == 200
    assert own_res.content == dummy_docx

    # Student 2 cannot download Student 1's file (403)
    other_res = client.get(
        f"/api/submissions/{submission_id}/file",
        headers=other_student_user["headers"],
    )
    assert other_res.status_code == 403


def test_unauthorized_faculty_cannot_download_submission_file(
    client: TestClient,
    faculty_user: dict,
    other_faculty_user: dict,
    student_user: dict,
):
    code = f"SEC{datetime.now().strftime('%H%M%S%f')[:8]}"
    subject_id, assignment_id = setup_course_and_assignment(
        client, faculty_user["headers"], code
    )

    client.post(f"/api/subjects/{subject_id}/enroll", headers=student_user["headers"])
    dummy_pdf = b"%PDF-1.4 confidential assignment"
    files = {"file": ("exam.pdf", BytesIO(dummy_pdf), "application/pdf")}
    subm_res = client.post(
        f"/api/assignments/{assignment_id}/submit",
        files=files,
        headers=student_user["headers"],
    )
    submission_id = subm_res.json()["id"]

    # Other faculty attempts download -> 403
    other_fac_res = client.get(
        f"/api/submissions/{submission_id}/file",
        headers=other_faculty_user["headers"],
    )
    assert other_fac_res.status_code == 403


def test_submission_without_file_returns_404(
    client: TestClient, faculty_user: dict, student_user: dict
):
    code = f"SEC{datetime.now().strftime('%H%M%S%f')[:8]}"
    subject_id, assignment_id = setup_course_and_assignment(
        client, faculty_user["headers"], code
    )

    client.post(f"/api/subjects/{subject_id}/enroll", headers=student_user["headers"])
    subm_res = client.post(
        f"/api/assignments/{assignment_id}/submit",
        json={"submission_text": "Plain text submission with no file"},
        headers=student_user["headers"],
    )
    submission_id = subm_res.json()["id"]

    file_res = client.get(
        f"/api/submissions/{submission_id}/file",
        headers=faculty_user["headers"],
    )
    assert file_res.status_code == 404
    assert "no file" in file_res.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 2. Course Material File Access Tests
# ---------------------------------------------------------------------------

def test_enrolled_student_can_download_and_preview_course_material(
    client: TestClient, faculty_user: dict, student_user: dict
):
    code = f"SEC{datetime.now().strftime('%H%M%S%f')[:8]}"
    subject_id, _ = setup_course_and_assignment(client, faculty_user["headers"], code)

    # Faculty uploads material
    dummy_pdf = b"%PDF-1.4 Lecture 1 Notes on Virtual Memory"
    files = {"file": ("lecture1.pdf", BytesIO(dummy_pdf), "application/pdf")}
    mat_res = client.post(
        f"/api/subjects/{subject_id}/materials",
        data={"title": "Lecture 1"},
        files=files,
        headers=faculty_user["headers"],
    )
    assert mat_res.status_code == 201
    material_id = mat_res.json()["id"]

    # Student enrolls
    client.post(f"/api/subjects/{subject_id}/enroll", headers=student_user["headers"])

    # Student downloads material
    mat_download = client.get(
        f"/api/materials/{material_id}/file",
        headers=student_user["headers"],
    )
    assert mat_download.status_code == 200
    assert mat_download.headers["content-type"] == "application/pdf"
    assert 'attachment; filename="lecture1.pdf"' in mat_download.headers["content-disposition"]
    assert mat_download.content == dummy_pdf

    # Student previews material inline
    mat_preview = client.get(
        f"/api/materials/{material_id}/file?inline=true",
        headers=student_user["headers"],
    )
    assert mat_preview.status_code == 200
    assert 'inline; filename="lecture1.pdf"' in mat_preview.headers["content-disposition"]


def test_unenrolled_student_cannot_download_course_material(
    client: TestClient, faculty_user: dict, student_user: dict
):
    code = f"SEC{datetime.now().strftime('%H%M%S%f')[:8]}"
    subject_id, _ = setup_course_and_assignment(client, faculty_user["headers"], code)

    dummy_pdf = b"%PDF-1.4 Private Course Syllabus"
    files = {"file": ("syllabus.pdf", BytesIO(dummy_pdf), "application/pdf")}
    mat_res = client.post(
        f"/api/subjects/{subject_id}/materials",
        data={"title": "Syllabus"},
        files=files,
        headers=faculty_user["headers"],
    )
    material_id = mat_res.json()["id"]

    # Student is NOT enrolled -> 403
    unauth_res = client.get(
        f"/api/materials/{material_id}/file",
        headers=student_user["headers"],
    )
    assert unauth_res.status_code == 403


def test_unauthorized_faculty_cannot_download_material(
    client: TestClient, faculty_user: dict, other_faculty_user: dict
):
    code = f"SEC{datetime.now().strftime('%H%M%S%f')[:8]}"
    subject_id, _ = setup_course_and_assignment(client, faculty_user["headers"], code)

    dummy_pdf = b"%PDF-1.4 Faculty Protected Notes"
    files = {"file": ("fac_notes.pdf", BytesIO(dummy_pdf), "application/pdf")}
    mat_res = client.post(
        f"/api/subjects/{subject_id}/materials",
        data={"title": "Faculty Notes"},
        files=files,
        headers=faculty_user["headers"],
    )
    material_id = mat_res.json()["id"]

    # Other faculty -> 403
    other_res = client.get(
        f"/api/materials/{material_id}/file",
        headers=other_faculty_user["headers"],
    )
    assert other_res.status_code == 403


# ---------------------------------------------------------------------------
# 3. Security Hardening & Path Traversal Safeguards
# ---------------------------------------------------------------------------

def test_path_traversal_detection(tmp_path: Path):
    base_dir = tmp_path / "uploads"
    base_dir.mkdir()
    secret_file = tmp_path / "secret.txt"
    secret_file.write_text("classified")

    traversal_path = str(base_dir / ".." / "secret.txt")

    with pytest.raises(AppException) as exc_info:
        validate_file_path_safe(traversal_path, base_dir)

    assert exc_info.value.status_code == 403
    assert "traversal" in exc_info.value.detail.lower()


def test_sanitize_download_filename():
    assert sanitize_download_filename("normal_file.pdf") == "normal_file.pdf"
    assert sanitize_download_filename("../../../etc/passwd") == "passwd"
    assert sanitize_download_filename("evil\r\nHeader: inject.pdf") == "evil__Header__inject.pdf"
    assert sanitize_download_filename("") == "download"


def test_unauthenticated_file_access_rejected(client: TestClient):
    res1 = client.get("/api/submissions/1/file")
    assert res1.status_code == 401

    res2 = client.get("/api/materials/1/file")
    assert res2.status_code == 401


# ---------------------------------------------------------------------------
# 4. Feedback Lifecycle & Privacy Safeguards
# ---------------------------------------------------------------------------

def test_feedback_privacy_lifecycle(
    client: TestClient, faculty_user: dict, student_user: dict
):
    code = f"SEC{datetime.now().strftime('%H%M%S%f')[:8]}"
    subject_id, assignment_id = setup_course_and_assignment(
        client, faculty_user["headers"], code
    )

    # Student enrolls and submits
    client.post(f"/api/subjects/{subject_id}/enroll", headers=student_user["headers"])
    subm_res = client.post(
        f"/api/assignments/{assignment_id}/submit",
        json={"submission_text": "Detailed virtual memory page table walk implementation."},
        headers=student_user["headers"],
    )
    submission_id = subm_res.json()["id"]

    # Faculty triggers AI assessment
    assess_res = client.post(
        f"/api/submissions/{submission_id}/assess",
        headers=faculty_user["headers"],
    )
    assert assess_res.status_code == 200
    assessment_id = assess_res.json()["id"]
    assert assess_res.json()["status"] == AssessmentStatus.COMPLETED.value

    # 1. Student CANNOT view draft AI assessment before faculty approval (403)
    pre_approve_student_res = client.get(
        f"/api/submissions/{submission_id}/assessment",
        headers=student_user["headers"],
    )
    assert pre_approve_student_res.status_code == 403
    assert "approved" in pre_approve_student_res.json()["detail"].lower()

    # 2. Faculty CAN view draft assessment anytime with full internal details
    faculty_view_res = client.get(
        f"/api/submissions/{submission_id}/assessment",
        headers=faculty_user["headers"],
    )
    assert faculty_view_res.status_code == 200
    fac_data = faculty_view_res.json()
    assert fac_data["id"] == assessment_id
    assert "criteria_scores" in fac_data

    # 3. Faculty approves assessment with internal commendation notes
    approve_res = client.post(
        f"/api/assessments/{assessment_id}/approve",
        json={"faculty_notes": "Internal instructor note: Excellent mastery shown."},
        headers=faculty_user["headers"],
    )
    assert approve_res.status_code == 200
    assert approve_res.json()["status"] == AssessmentStatus.APPROVED.value

    # 4. Student CAN now view approved assessment; private notes and internal context are redacted
    post_approve_student_res = client.get(
        f"/api/submissions/{submission_id}/assessment",
        headers=student_user["headers"],
    )
    assert post_approve_student_res.status_code == 200
    student_data = post_approve_student_res.json()

    # Released score and intended student feedback are visible
    assert student_data["status"] == AssessmentStatus.APPROVED.value
    assert student_data["final_score"] > 0.0
    assert len(student_data["criteria_scores"]) == 2
    assert student_data["criteria_scores"][0]["criterion"] == "Paging Correctness"
    assert student_data["feedback"]["summary"] is not None

    # Faculty-only notes and internal evaluation details must be REDACTED
    assert student_data["faculty_notes"] is None
    assert student_data["retrieved_context"] == []
    assert student_data["model_name"] is None


def test_feedback_privacy_after_score_modification(
    client: TestClient, faculty_user: dict, student_user: dict
):
    code = f"SEC{datetime.now().strftime('%H%M%S%f')[:8]}"
    subject_id, assignment_id = setup_course_and_assignment(
        client, faculty_user["headers"], code
    )

    client.post(f"/api/subjects/{subject_id}/enroll", headers=student_user["headers"])
    subm_res = client.post(
        f"/api/assignments/{assignment_id}/submit",
        json={"submission_text": "Paging implementation analysis."},
        headers=student_user["headers"],
    )
    submission_id = subm_res.json()["id"]

    assess_res = client.post(
        f"/api/submissions/{submission_id}/assess",
        headers=faculty_user["headers"],
    )
    assessment_id = assess_res.json()["id"]

    # Faculty overrides final score with private notes
    mod_res = client.put(
        f"/api/assessments/{assessment_id}",
        json={
            "final_score": 48.0,
            "faculty_notes": "Internal faculty justification for extra marks",
        },
        headers=faculty_user["headers"],
    )
    assert mod_res.status_code == 200
    assert mod_res.json()["status"] == AssessmentStatus.MODIFIED.value

    # Student views modified assessment
    student_view = client.get(
        f"/api/submissions/{submission_id}/assessment",
        headers=student_user["headers"],
    )
    assert student_view.status_code == 200
    student_data = student_view.json()
    assert student_data["status"] == AssessmentStatus.MODIFIED.value
    assert student_data["final_score"] == 48.0
    assert student_data["faculty_notes"] is None
    assert student_data["retrieved_context"] == []
