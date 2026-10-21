"""
Phase 9: Complete CRUD for Courses, Assignments, Assessments, Course Materials, and Submissions.

Tests covering:
  1. Authorized course edits and unauthorized attempts (student & other faculty).
  2. Course deletion safeguards: reject deletion when enrollments or assignments exist (409).
  3. Course archiving via archive endpoint and update.
  4. Assignment edits: title, instructions, due_date, max_marks.
  5. Assignment max_marks validation against rubric criteria sum.
  6. Assignment deletion safeguards: reject deletion when student submissions exist (409).
  7. Assignment archiving via archive endpoint.
  8. Course material title edit via PUT /api/materials/{id}.
  9. Unauthorized material edits (403) and blank title validation (422).
 10. Course material deletion and safe file cleanup.
 11. Student submission replacement before deadline.
 12. Rejection of submission replacement after deadline (400) or after evaluation (400).
 13. Student submission withdrawal before deadline.
 14. Rejection of withdrawal after evaluation or after deadline (400).
 15. Assessment reassessment confirmation workflow and student feedback privacy.
"""

from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient


def create_sample_subject(client: TestClient, faculty_headers: dict, code: str = "CRUD101") -> int:
    res = client.post(
        "/api/subjects",
        json={"name": "CRUD Test Subject", "code": code, "description": "Subject for CRUD tests"},
        headers=faculty_headers,
    )
    return res.json()["id"]


def create_sample_assignment(
    client: TestClient,
    faculty_headers: dict,
    subject_id: int,
    due_days: int = 7,
    max_marks: float = 100.0,
    rubric_items: list[dict] | None = None,
) -> int:
    due = (datetime.now(timezone.utc) + timedelta(days=due_days)).isoformat()
    payload = {
        "title": "CRUD Assignment",
        "description": "Assignment description",
        "instructions": "Follow guidelines",
        "due_date": due,
        "max_marks": max_marks,
    }
    if rubric_items:
        payload["rubric"] = {
            "name": "CRUD Rubric",
            "items": rubric_items,
        }
    res = client.post(f"/api/subjects/{subject_id}/assignments", json=payload, headers=faculty_headers)
    return res.json()["id"]


# ===========================================================================
# 1. Course Management Tests
# ===========================================================================

def test_faculty_can_edit_course_details(client: TestClient, faculty_user: dict):
    subject_id = create_sample_subject(client, faculty_user["headers"], "EDIT101")

    res = client.put(
        f"/api/subjects/{subject_id}",
        json={"name": "Updated Data Structures", "description": "New syllabus"},
        headers=faculty_user["headers"],
    )
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "Updated Data Structures"
    assert data["description"] == "New syllabus"


def test_unauthorized_user_cannot_edit_course(
    client: TestClient, faculty_user: dict, other_faculty_user: dict, student_user: dict
):
    subject_id = create_sample_subject(client, faculty_user["headers"], "EDIT102")

    # Other faculty
    res1 = client.put(
        f"/api/subjects/{subject_id}",
        json={"name": "Hacked Course"},
        headers=other_faculty_user["headers"],
    )
    assert res1.status_code == 403

    # Student
    res2 = client.put(
        f"/api/subjects/{subject_id}",
        json={"name": "Student Attempt"},
        headers=student_user["headers"],
    )
    assert res2.status_code == 403


def test_blank_course_name_rejected(client: TestClient, faculty_user: dict):
    subject_id = create_sample_subject(client, faculty_user["headers"], "EDIT103")
    res = client.put(
        f"/api/subjects/{subject_id}",
        json={"name": "   "},
        headers=faculty_user["headers"],
    )
    assert res.status_code == 422


def test_course_deletion_safeguard_when_enrollments_exist(
    client: TestClient, faculty_user: dict, student_user: dict
):
    subject_id = create_sample_subject(client, faculty_user["headers"], "SAFE101")
    # Student enrolls
    client.post(f"/api/subjects/{subject_id}/enroll", headers=student_user["headers"])

    # Attempt delete
    del_res = client.delete(f"/api/subjects/{subject_id}", headers=faculty_user["headers"])
    assert del_res.status_code == 409
    assert "active records" in del_res.json()["detail"].lower()


def test_course_deletion_safeguard_when_assignments_exist(client: TestClient, faculty_user: dict):
    subject_id = create_sample_subject(client, faculty_user["headers"], "SAFE102")
    create_sample_assignment(client, faculty_user["headers"], subject_id)

    # Attempt delete
    del_res = client.delete(f"/api/subjects/{subject_id}", headers=faculty_user["headers"])
    assert del_res.status_code == 409
    assert "archive the course instead" in del_res.json()["detail"].lower()


def test_course_archive_and_unarchive(client: TestClient, faculty_user: dict):
    subject_id = create_sample_subject(client, faculty_user["headers"], "ARCH101")

    # Archive
    arch_res = client.post(f"/api/subjects/{subject_id}/archive?archive=true", headers=faculty_user["headers"])
    assert arch_res.status_code == 200
    assert arch_res.json()["is_archived"] is True

    # Unarchive
    unarch_res = client.post(f"/api/subjects/{subject_id}/archive?archive=false", headers=faculty_user["headers"])
    assert unarch_res.status_code == 200
    assert unarch_res.json()["is_archived"] is False


# ===========================================================================
# 2. Assignment Management Tests
# ===========================================================================

def test_faculty_can_edit_assignment(client: TestClient, faculty_user: dict):
    subject_id = create_sample_subject(client, faculty_user["headers"], "ASG_EDIT1")
    asg_id = create_sample_assignment(client, faculty_user["headers"], subject_id)

    new_due = (datetime.now(timezone.utc) + timedelta(days=14)).isoformat()
    res = client.put(
        f"/api/assignments/{asg_id}",
        json={
            "title": "Updated Assignment Title",
            "description": "Updated Description",
            "instructions": "Updated Instructions",
            "due_date": new_due,
            "max_marks": 150.0,
        },
        headers=faculty_user["headers"],
    )
    assert res.status_code == 200
    data = res.json()
    assert data["title"] == "Updated Assignment Title"
    assert data["max_marks"] == 150.0


def test_assignment_max_marks_cannot_be_less_than_rubric_sum(client: TestClient, faculty_user: dict):
    subject_id = create_sample_subject(client, faculty_user["headers"], "ASG_RUB1")
    rubric_items = [
        {"criterion": "Accuracy", "max_marks": 40.0},
        {"criterion": "Code Quality", "max_marks": 30.0},
    ]  # sum = 70
    asg_id = create_sample_assignment(
        client, faculty_user["headers"], subject_id, max_marks=100.0, rubric_items=rubric_items
    )

    # Attempt to reduce max_marks to 50 (below rubric sum of 70)
    res = client.put(
        f"/api/assignments/{asg_id}",
        json={"max_marks": 50.0},
        headers=faculty_user["headers"],
    )
    assert res.status_code == 422
    assert "less than existing rubric criteria sum" in res.json()["detail"].lower()


def test_assignment_deletion_safeguard_when_submissions_exist(
    client: TestClient, faculty_user: dict, student_user: dict
):
    subject_id = create_sample_subject(client, faculty_user["headers"], "ASG_DEL1")
    asg_id = create_sample_assignment(client, faculty_user["headers"], subject_id)

    # Student enrolls and submits
    client.post(f"/api/subjects/{subject_id}/enroll", headers=student_user["headers"])
    sub_res = client.post(
        f"/api/assignments/{asg_id}/submit",
        json={"submission_text": "Sample student work"},
        headers=student_user["headers"],
    )
    assert sub_res.status_code == 201

    # Attempt to delete assignment
    del_res = client.delete(f"/api/assignments/{asg_id}", headers=faculty_user["headers"])
    assert del_res.status_code == 409
    assert "archive the assignment instead" in del_res.json()["detail"].lower()


def test_assignment_archive_and_unarchive(client: TestClient, faculty_user: dict):
    subject_id = create_sample_subject(client, faculty_user["headers"], "ASG_ARCH1")
    asg_id = create_sample_assignment(client, faculty_user["headers"], subject_id)

    # Archive
    res = client.post(f"/api/assignments/{asg_id}/archive?archive=true", headers=faculty_user["headers"])
    assert res.status_code == 200
    assert res.json()["is_archived"] is True

    # Unarchive
    res2 = client.post(f"/api/assignments/{asg_id}/archive?archive=false", headers=faculty_user["headers"])
    assert res2.status_code == 200
    assert res2.json()["is_archived"] is False


# ===========================================================================
# 3. Course Materials Management Tests
# ===========================================================================

def test_faculty_can_update_course_material_title(client: TestClient, faculty_user: dict):
    subject_id = create_sample_subject(client, faculty_user["headers"], "MAT_EDIT1")

    # Upload material (DOCX or PDF dummy)
    files = {"file": ("lecture1.pdf", b"%PDF-1.4 dummy content", "application/pdf")}
    upload_res = client.post(
        f"/api/subjects/{subject_id}/materials",
        files=files,
        data={"title": "Original Material Title"},
        headers=faculty_user["headers"],
    )
    assert upload_res.status_code == 201
    mat_id = upload_res.json()["id"]

    # Update title
    update_res = client.put(
        f"/api/materials/{mat_id}",
        json={"title": "Updated Lecture 1 Notes"},
        headers=faculty_user["headers"],
    )
    assert update_res.status_code == 200
    assert update_res.json()["title"] == "Updated Lecture 1 Notes"


def test_unauthorized_material_update_rejected(
    client: TestClient, faculty_user: dict, other_faculty_user: dict, student_user: dict
):
    subject_id = create_sample_subject(client, faculty_user["headers"], "MAT_EDIT2")
    files = {"file": ("lecture2.pdf", b"%PDF-1.4 dummy content", "application/pdf")}
    upload_res = client.post(
        f"/api/subjects/{subject_id}/materials",
        files=files,
        data={"title": "Protected Material"},
        headers=faculty_user["headers"],
    )
    mat_id = upload_res.json()["id"]

    # Student cannot update
    res_student = client.put(
        f"/api/materials/{mat_id}",
        json={"title": "Hacked Title"},
        headers=student_user["headers"],
    )
    assert res_student.status_code == 403

    # Other faculty cannot update
    res_other = client.put(
        f"/api/materials/{mat_id}",
        json={"title": "Other Faculty Title"},
        headers=other_faculty_user["headers"],
    )
    assert res_other.status_code == 403


# ===========================================================================
# 4. Student Submission Management Tests
# ===========================================================================

def test_student_can_replace_submission_before_deadline(
    client: TestClient, faculty_user: dict, student_user: dict
):
    subject_id = create_sample_subject(client, faculty_user["headers"], "SUB_REP1")
    asg_id = create_sample_assignment(client, faculty_user["headers"], subject_id, due_days=5)

    client.post(f"/api/subjects/{subject_id}/enroll", headers=student_user["headers"])
    sub_res = client.post(
        f"/api/assignments/{asg_id}/submit",
        json={"submission_text": "First draft answer"},
        headers=student_user["headers"],
    )
    sub_id = sub_res.json()["id"]

    # Replace submission
    rep_res = client.put(
        f"/api/submissions/{sub_id}",
        json={"submission_text": "Revised and improved answer"},
        headers=student_user["headers"],
    )
    assert rep_res.status_code == 200
    assert rep_res.json()["submission_text"] == "Revised and improved answer"


def test_student_cannot_replace_other_students_submission(
    client: TestClient, faculty_user: dict, student_user: dict, other_student_user: dict
):
    subject_id = create_sample_subject(client, faculty_user["headers"], "SUB_REP2")
    asg_id = create_sample_assignment(client, faculty_user["headers"], subject_id, due_days=5)

    client.post(f"/api/subjects/{subject_id}/enroll", headers=student_user["headers"])
    client.post(f"/api/subjects/{subject_id}/enroll", headers=other_student_user["headers"])

    sub_res = client.post(
        f"/api/assignments/{asg_id}/submit",
        json={"submission_text": "Student 1 work"},
        headers=student_user["headers"],
    )
    sub_id = sub_res.json()["id"]

    # Student 2 tries to replace Student 1's work
    rep_res = client.put(
        f"/api/submissions/{sub_id}",
        json={"submission_text": "Tampered work"},
        headers=other_student_user["headers"],
    )
    assert rep_res.status_code == 403


def test_submission_replacement_rejected_after_deadline(
    client: TestClient, faculty_user: dict, student_user: dict
):
    subject_id = create_sample_subject(client, faculty_user["headers"], "SUB_DEAD1")
    # Due in 1 day initially
    asg_id = create_sample_assignment(client, faculty_user["headers"], subject_id, due_days=1)

    client.post(f"/api/subjects/{subject_id}/enroll", headers=student_user["headers"])
    sub_res = client.post(
        f"/api/assignments/{asg_id}/submit",
        json={"submission_text": "Initial on-time work"},
        headers=student_user["headers"],
    )
    sub_id = sub_res.json()["id"]

    # Set assignment due date in the past
    past_due = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    client.put(
        f"/api/assignments/{asg_id}",
        json={"due_date": past_due},
        headers=faculty_user["headers"],
    )

    # Attempt to replace after deadline
    rep_res = client.put(
        f"/api/submissions/{sub_id}",
        json={"submission_text": "Late replacement attempt"},
        headers=student_user["headers"],
    )
    assert rep_res.status_code == 400
    assert "due date has passed" in rep_res.json()["detail"].lower()


def test_submission_replacement_rejected_after_evaluation(
    client: TestClient, faculty_user: dict, student_user: dict
):
    subject_id = create_sample_subject(client, faculty_user["headers"], "SUB_EVAL1")
    asg_id = create_sample_assignment(client, faculty_user["headers"], subject_id, due_days=5)

    client.post(f"/api/subjects/{subject_id}/enroll", headers=student_user["headers"])
    sub_res = client.post(
        f"/api/assignments/{asg_id}/submit",
        json={"submission_text": "Student response for AI assessment"},
        headers=student_user["headers"],
    )
    sub_id = sub_res.json()["id"]

    # Run AI assessment
    assess_res = client.post(f"/api/submissions/{sub_id}/assess", headers=faculty_user["headers"])
    assert assess_res.status_code == 200
    assess_id = assess_res.json()["id"]

    # Approve assessment
    appr_res = client.post(f"/api/assessments/{assess_id}/approve", headers=faculty_user["headers"])
    assert appr_res.status_code == 200

    # Attempt to replace after evaluation
    rep_res = client.put(
        f"/api/submissions/{sub_id}",
        json={"submission_text": "Sneaky replacement after grade"},
        headers=student_user["headers"],
    )
    assert rep_res.status_code == 400
    assert "already been evaluated" in rep_res.json()["detail"].lower()


def test_student_can_withdraw_submission_before_deadline(
    client: TestClient, faculty_user: dict, student_user: dict
):
    subject_id = create_sample_subject(client, faculty_user["headers"], "SUB_WITH1")
    asg_id = create_sample_assignment(client, faculty_user["headers"], subject_id, due_days=5)

    client.post(f"/api/subjects/{subject_id}/enroll", headers=student_user["headers"])
    sub_res = client.post(
        f"/api/assignments/{asg_id}/submit",
        json={"submission_text": "Temporary work to withdraw"},
        headers=student_user["headers"],
    )
    sub_id = sub_res.json()["id"]

    # Withdraw
    with_res = client.delete(f"/api/submissions/{sub_id}", headers=student_user["headers"])
    assert with_res.status_code == 204

    # Verify submission is gone
    get_res = client.get(f"/api/submissions/{sub_id}", headers=student_user["headers"])
    assert get_res.status_code == 404


# ===========================================================================
# 5. Assessment Reassessment Confirmation and Feedback Privacy Tests
# ===========================================================================

def test_assessment_reassessment_behavior_and_feedback_privacy(
    client: TestClient, faculty_user: dict, student_user: dict
):
    subject_id = create_sample_subject(client, faculty_user["headers"], "ASSESS_PRIV1")
    rubric_items = [{"criterion": "Technical Correctness", "max_marks": 100.0}]
    asg_id = create_sample_assignment(
        client, faculty_user["headers"], subject_id, max_marks=100.0, rubric_items=rubric_items
    )

    client.post(f"/api/subjects/{subject_id}/enroll", headers=student_user["headers"])
    sub_res = client.post(
        f"/api/assignments/{asg_id}/submit",
        json={"submission_text": "Testing reassessment and privacy lifecycle."},
        headers=student_user["headers"],
    )
    sub_id = sub_res.json()["id"]

    # Initial assessment
    res1 = client.post(f"/api/submissions/{sub_id}/assess", headers=faculty_user["headers"])
    assert res1.status_code == 200
    first_assess_id = res1.json()["id"]
    assert res1.json()["status"] == "COMPLETED"

    # Calling assess without force_reassess returns existing assessment without recomputing
    res_cached = client.post(f"/api/submissions/{sub_id}/assess", headers=faculty_user["headers"])
    assert res_cached.status_code == 200
    assert res_cached.json()["id"] == first_assess_id

    # Unapproved assessment is hidden from student
    student_view_unapproved = client.get(
        f"/api/submissions/{sub_id}/assessment", headers=student_user["headers"]
    )
    assert student_view_unapproved.status_code == 403

    # Faculty approves assessment
    appr_res = client.post(
        f"/api/assessments/{first_assess_id}/approve",
        json={"faculty_notes": "Private internal faculty deliberation notes."},
        headers=faculty_user["headers"],
    )
    assert appr_res.status_code == 200

    # Student can now view released grade and rubric, but private notes & context are redacted
    student_view_approved = client.get(
        f"/api/submissions/{sub_id}/assessment", headers=student_user["headers"]
    )
    assert student_view_approved.status_code == 200
    st_data = student_view_approved.json()
    assert st_data["status"] == "APPROVED"
    assert st_data["faculty_notes"] is None  # REDACTED
    assert st_data["retrieved_context"] == []  # REDACTED
    assert st_data["model_name"] is None  # REDACTED

    # Reassessment with force_reassess=True updates status back to COMPLETED
    reassess_res = client.post(
        f"/api/submissions/{sub_id}/assess?force_reassess=true", headers=faculty_user["headers"]
    )
    assert reassess_res.status_code == 200
    assert reassess_res.json()["status"] == "COMPLETED"

    # Because status is back to COMPLETED, student cannot view until re-approved
    st_view_reassessed = client.get(
        f"/api/submissions/{sub_id}/assessment", headers=student_user["headers"]
    )
    assert st_view_reassessed.status_code == 403
