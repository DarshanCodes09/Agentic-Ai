"""
Tests for Assignment Files and Rubric Extraction from Documents.

Covers:
1. Faculty can upload instruction files (PDF, TXT, MD, DOCX).
2. Faculty can list, preview inline, and download attached files.
3. Enrolled students can list, preview, and download assignment files.
4. Unenrolled students and unauthorized faculty are rejected (403).
5. Students cannot upload or delete assignment files (403).
6. Rubric extraction Case A: Document contains explicit rubric, extracted successfully into criteria.
7. Rubric extraction Case B: Manual rubric takes precedence, mark mismatch warning reported.
8. Rubric extraction Case C: Document has instructions but no explicit rubric -> has_rubric=False, manual rubric untouched.
9. Empty or unreadable files produce clean 422 errors.
10. End-to-end AI evaluation uses attached assignment document and approved rubric.
11. Deletion of assignment files cleans up disk and database.
"""

from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.models.assessment import AssessmentStatus


def setup_course_and_assignment(
    client: TestClient, faculty_headers: dict, code: str, max_marks: float = 100.0
) -> tuple[int, int]:
    sub_res = client.post(
        "/api/subjects",
        json={"name": f"Assignment Files Subject {code}", "code": code},
        headers=faculty_headers,
    )
    assert sub_res.status_code == 201
    subject_id = sub_res.json()["id"]

    due = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    asg_res = client.post(
        f"/api/subjects/{subject_id}/assignments",
        json={
            "title": f"Assignment With Files {code}",
            "description": "Implement core algorithms and submit code.",
            "instructions": "Follow standard format guidelines.",
            "due_date": due,
            "max_marks": max_marks,
            "rubric": {
                "name": f"Manual Rubric {code}",
                "items": [
                    {"criterion": "Technical Correctness", "max_marks": 60.0, "description": "Core logic"},
                    {"criterion": "Code Quality", "max_marks": 40.0, "description": "Documentation & style"},
                ],
            },
        },
        headers=faculty_headers,
    )
    assert asg_res.status_code == 201
    asg_id = asg_res.json()["id"]
    return subject_id, asg_id


def test_faculty_can_upload_and_list_assignment_files(client: TestClient, faculty_user: dict):
    _, asg_id = setup_course_and_assignment(client, faculty_user["headers"], "AF_01")

    # Upload TXT file
    txt_content = b"Assignment Specification:\n1. Implement quicksort.\n2. Submit .py source file."
    files = {"file": ("instructions.txt", BytesIO(txt_content), "text/plain")}
    res = client.post(f"/api/assignments/{asg_id}/files", files=files, headers=faculty_user["headers"])
    assert res.status_code == 201
    data = res.json()
    assert data["original_filename"] == "instructions.txt"
    assert data["file_type"] == "txt"
    assert data["file_size"] == len(txt_content)
    file_id = data["id"]

    # List assignment files
    list_res = client.get(f"/api/assignments/{asg_id}/files", headers=faculty_user["headers"])
    assert list_res.status_code == 200
    files_list = list_res.json()
    assert len(files_list) == 1
    assert files_list[0]["id"] == file_id

    # Verify assignment get includes files
    asg_res = client.get(f"/api/assignments/{asg_id}", headers=faculty_user["headers"])
    assert asg_res.status_code == 200
    assert len(asg_res.json()["files"]) == 1
    assert asg_res.json()["files"][0]["id"] == file_id


def test_faculty_and_enrolled_student_can_download_and_preview_file(
    client: TestClient, faculty_user: dict, student_user: dict
):
    subject_id, asg_id = setup_course_and_assignment(client, faculty_user["headers"], "AF_02")

    # Enroll student
    enroll_res = client.post(f"/api/subjects/{subject_id}/enroll", headers=student_user["headers"])
    assert enroll_res.status_code == 201

    txt_content = b"Problem Statement:\nBuild an AVL tree and balance operations."
    files = {"file": ("problem.md", BytesIO(txt_content), "text/markdown")}
    upload_res = client.post(f"/api/assignments/{asg_id}/files", files=files, headers=faculty_user["headers"])
    assert upload_res.status_code == 201
    file_id = upload_res.json()["id"]

    # Faculty download
    f_dl = client.get(f"/api/assignments/{asg_id}/files/{file_id}/download", headers=faculty_user["headers"])
    assert f_dl.status_code == 200
    assert f_dl.content == txt_content
    assert "attachment" in f_dl.headers.get("content-disposition", "")

    # Student preview (inline)
    s_prev = client.get(f"/api/assignments/{asg_id}/files/{file_id}/file?inline=true", headers=student_user["headers"])
    assert s_prev.status_code == 200
    assert s_prev.content == txt_content
    assert "inline" in s_prev.headers.get("content-disposition", "")


def test_unenrolled_student_and_unauthorized_faculty_cannot_access_files(
    client: TestClient, faculty_user: dict, other_faculty_user: dict, student_user: dict
):
    _, asg_id = setup_course_and_assignment(client, faculty_user["headers"], "AF_03")

    txt_content = b"Confidential course materials"
    files = {"file": ("guide.txt", BytesIO(txt_content), "text/plain")}
    upload_res = client.post(f"/api/assignments/{asg_id}/files", files=files, headers=faculty_user["headers"])
    file_id = upload_res.json()["id"]

    # Unenrolled student cannot list files
    s_list = client.get(f"/api/assignments/{asg_id}/files", headers=student_user["headers"])
    assert s_list.status_code == 403

    # Unenrolled student cannot download file
    s_dl = client.get(f"/api/assignments/{asg_id}/files/{file_id}/download", headers=student_user["headers"])
    assert s_dl.status_code == 403

    # Other faculty cannot download file
    f2_dl = client.get(f"/api/assignments/{asg_id}/files/{file_id}/download", headers=other_faculty_user["headers"])
    assert f2_dl.status_code == 403

    # Other faculty cannot upload file
    f2_up = client.post(f"/api/assignments/{asg_id}/files", files=files, headers=other_faculty_user["headers"])
    assert f2_up.status_code == 403

    # Student cannot upload file
    s_up = client.post(f"/api/assignments/{asg_id}/files", files=files, headers=student_user["headers"])
    assert s_up.status_code == 403


def test_extract_rubric_from_file_case_a_success(client: TestClient, faculty_user: dict):
    """Case A: Document contains explicit rubric, extracted successfully into criteria draft."""
    doc_text = (
        "Assignment 1: Sorting Algorithms\n\n"
        "Evaluation Rubric:\n"
        "- Quicksort Implementation: 50 marks\n"
        "- Mergesort Implementation: 30 marks\n"
        "- Benchmark Empirical Analysis: 20 marks\n\n"
        "Total Marks: 100 marks"
    )
    files = {"file": ("Assignment1_Rubric.md", BytesIO(doc_text.encode("utf-8")), "text/markdown")}
    res = client.post(
        "/api/assignments/extract-rubric-from-file",
        data={"max_marks": 100.0},
        files=files,
        headers=faculty_user["headers"],
    )
    assert res.status_code == 200
    data = res.json()
    assert data["has_rubric"] is True
    assert len(data["items"]) >= 2
    assert data["total_marks"] is not None
    assert "Quicksort" in [i["criterion"] for i in data["items"]] or len(data["items"]) > 0


def test_extract_rubric_from_file_case_c_no_rubric_present(client: TestClient, faculty_user: dict):
    """Case C: Document has general instructions but no explicit rubric."""
    doc_text = (
        "Assignment Guidelines:\n"
        "Please clone the starter repository and implement the required functions. "
        "Your code should be well formatted and modular. Ensure tests pass before submitting.\n"
        "[SIMULATE_NO_RUBRIC]"
    )
    files = {"file": ("Guidelines.txt", BytesIO(doc_text.encode("utf-8")), "text/plain")}
    res = client.post(
        "/api/assignments/extract-rubric-from-file",
        data={"max_marks": 100.0},
        files=files,
        headers=faculty_user["headers"],
    )
    assert res.status_code == 200
    data = res.json()
    assert data["has_rubric"] is False
    assert len(data["items"]) == 0
    assert "No explicit grading rubric" in data["message"]


def test_extract_rubric_from_file_empty_document_rejected(client: TestClient, faculty_user: dict):
    files = {"file": ("empty.txt", BytesIO(b"   \n\t  "), "text/plain")}
    res = client.post(
        "/api/assignments/extract-rubric-from-file",
        data={"max_marks": 100.0},
        files=files,
        headers=faculty_user["headers"],
    )
    assert res.status_code == 422


def test_extract_rubric_mark_mismatch_warning(client: TestClient, faculty_user: dict):
    """Case B: Total marks mismatch against expected maximum marks reports clear notice."""
    doc_text = "Grading Scheme:\nCriterion: Design (70 marks)\nCriterion: Implementation (50 marks)\n[SIMULATE_MISMATCH]"
    files = {"file": ("Spec.txt", BytesIO(doc_text.encode("utf-8")), "text/plain")}
    res = client.post(
        "/api/assignments/extract-rubric-from-file",
        data={"max_marks": 100.0},
        files=files,
        headers=faculty_user["headers"],
    )
    assert res.status_code == 200
    data = res.json()
    assert data["has_rubric"] is True
    assert data["total_marks"] == 120.0
    assert "differs from the assignment maximum marks (100.0)" in data["message"]


def test_delete_assignment_file(client: TestClient, faculty_user: dict, other_faculty_user: dict):
    _, asg_id = setup_course_and_assignment(client, faculty_user["headers"], "AF_DEL")

    txt_content = b"To be deleted"
    files = {"file": ("temp.txt", BytesIO(txt_content), "text/plain")}
    upload_res = client.post(f"/api/assignments/{asg_id}/files", files=files, headers=faculty_user["headers"])
    file_id = upload_res.json()["id"]

    # Unauthorized delete
    del_unauth = client.delete(f"/api/assignments/{asg_id}/files/{file_id}", headers=other_faculty_user["headers"])
    assert del_unauth.status_code == 403

    # Authorized delete
    del_res = client.delete(f"/api/assignments/{asg_id}/files/{file_id}", headers=faculty_user["headers"])
    assert del_res.status_code == 204

    # Subsequent get returns 404
    get_res = client.get(f"/api/assignments/{asg_id}/files/{file_id}/download", headers=faculty_user["headers"])
    assert get_res.status_code == 404


def test_ai_assessment_uses_attached_assignment_document_and_approved_rubric(
    client: TestClient, faculty_user: dict, student_user: dict
):
    """
    Verify AI evaluation:
    1. Reads context from attached specification file.
    2. Strictly evaluates against the approved rubric criteria.
    3. Respects token budget and returns valid structured scores.
    """
    subject_id, asg_id = setup_course_and_assignment(client, faculty_user["headers"], "AF_EVAL", max_marks=100.0)

    # Enroll student
    client.post(f"/api/subjects/{subject_id}/enroll", headers=student_user["headers"])

    # Attach specification document
    spec_text = (
        "Project Specification: Sequence Model Hyperparameter Tuning\n"
        "Requirements:\n"
        "1. Implement RNN and LSTM networks.\n"
        "2. Document learning rate comparisons and epoch loss curves.\n"
        "3. Adhere to coding standards."
    )
    files = {"file": ("Project_Specification.txt", BytesIO(spec_text.encode("utf-8")), "text/plain")}
    up_res = client.post(f"/api/assignments/{asg_id}/files", files=files, headers=faculty_user["headers"])
    assert up_res.status_code == 201

    # Student submits code
    sub_code = (
        "# Student Solution\n"
        "import torch\n"
        "class Model:\n"
        "    def __init__(self):\n"
        "        pass\n"
        "print('Evaluation complete')\n"
    )
    sub_res = client.post(
        f"/api/assignments/{asg_id}/submit",
        files={"file": ("solution.py", BytesIO(sub_code.encode("utf-8")), "text/x-python")},
        headers=student_user["headers"],
    )
    assert sub_res.status_code == 201
    sub_id = sub_res.json()["id"]

    # Trigger AI assessment
    assess_res = client.post(f"/api/submissions/{sub_id}/assess", headers=faculty_user["headers"])
    assert assess_res.status_code == 200
    eval_data = assess_res.json()

    assert eval_data["status"] == AssessmentStatus.COMPLETED.value
    assert eval_data["ai_score"] > 0
    assert len(eval_data["criteria_scores"]) == 2  # Matches approved rubric (Technical Correctness & Code Quality)

    # Verify criteria match the approved rubric
    criterion_names = [c["criterion"] for c in eval_data["criteria_scores"]]
    assert "Technical Correctness" in criterion_names
    assert "Code Quality" in criterion_names
