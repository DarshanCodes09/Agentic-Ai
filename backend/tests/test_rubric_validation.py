"""
Focused tests for Rubric section validation and persistence.

Covers:
1. Atomic creation of assignment with embedded rubric and criteria
2. Validation rejecting criteria marks exceeding assignment max_marks
3. Duplicate criterion name prevention in rubric creation
4. Standalone rubric creation rejecting criteria marks exceeding assignment max_marks
5. Adding rubric item exceeding assignment max_marks rejected (422)
6. Adding rubric item with duplicate criterion name rejected (409)
7. Updating rubric item exceeding assignment max_marks rejected (422)
8. Updating rubric item to duplicate existing criterion name rejected (409)
9. Reducing assignment max_marks below existing rubric criteria sum rejected (422)
10. Enrolled student receiving embedded rubric in assignment details
11. Blank/whitespace-only criterion name rejected (422)
12. Assessment preparation service aligns total_max_marks with assignment max_marks
"""

from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.submission import Submission
from app.services.assessment.preparation_service import get_assessment_preparation_service


def test_create_assignment_with_embedded_rubric_success(
    client: TestClient, faculty_user: dict
):
    faculty_headers = faculty_user["headers"]
    code = f"VAL{datetime.now().strftime('%H%M%S%f')[:8]}"
    sub_res = client.post(
        "/api/subjects",
        json={"name": "Rubric Validation Subject", "code": code},
        headers=faculty_headers,
    )
    subject_id = sub_res.json()["id"]

    due = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    asg_payload = {
        "title": "Data Structures Project",
        "description": "Implement a balanced AVL tree",
        "instructions": "Submit full source code with unit tests",
        "due_date": due,
        "max_marks": 100.0,
        "rubric": {
            "name": "AVL Tree Evaluation Rubric",
            "description": "Strict criteria for algorithm correctness and efficiency",
            "items": [
                {
                    "criterion": "Algorithm Correctness",
                    "description": "Handles rotations and rebalancing accurately",
                    "max_marks": 50.0,
                },
                {
                    "criterion": "Time & Space Complexity",
                    "description": "Adheres to O(log N) operations",
                    "max_marks": 30.0,
                },
                {
                    "criterion": "Code Quality & Tests",
                    "description": "Clean modular code with high coverage",
                    "max_marks": 20.0,
                },
            ],
        },
    }

    res = client.post(
        f"/api/subjects/{subject_id}/assignments",
        json=asg_payload,
        headers=faculty_headers,
    )
    assert res.status_code == 201
    data = res.json()
    assert data["title"] == "Data Structures Project"
    assert data["max_marks"] == 100.0
    assert data["rubric"] is not None
    assert data["rubric"]["name"] == "AVL Tree Evaluation Rubric"
    assert len(data["rubric"]["items"]) == 3
    assert sum(item["max_marks"] for item in data["rubric"]["items"]) == 100.0


def test_create_assignment_with_embedded_rubric_exceeding_max_marks_rejected(
    client: TestClient, faculty_user: dict
):
    faculty_headers = faculty_user["headers"]
    code = f"VAL{datetime.now().strftime('%H%M%S%f')[:8]}"
    sub_res = client.post(
        "/api/subjects",
        json={"name": "Excess Subject", "code": code},
        headers=faculty_headers,
    )
    subject_id = sub_res.json()["id"]

    due = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    asg_payload = {
        "title": "Invalid Marks Assignment",
        "due_date": due,
        "max_marks": 50.0,
        "rubric": {
            "name": "Excessive Rubric",
            "items": [
                {"criterion": "Part 1", "max_marks": 30.0},
                {"criterion": "Part 2", "max_marks": 30.0},  # Sum = 60.0 > 50.0
            ],
        },
    }

    res = client.post(
        f"/api/subjects/{subject_id}/assignments",
        json=asg_payload,
        headers=faculty_headers,
    )
    assert res.status_code == 422
    assert "exceed" in res.text.lower()


def test_create_assignment_with_duplicate_criteria_rejected(
    client: TestClient, faculty_user: dict
):
    faculty_headers = faculty_user["headers"]
    code = f"VAL{datetime.now().strftime('%H%M%S%f')[:8]}"
    sub_res = client.post(
        "/api/subjects",
        json={"name": "Dup Subject", "code": code},
        headers=faculty_headers,
    )
    subject_id = sub_res.json()["id"]

    due = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    asg_payload = {
        "title": "Duplicate Criteria Assignment",
        "due_date": due,
        "max_marks": 50.0,
        "rubric": {
            "name": "Duplicate Rubric",
            "items": [
                {"criterion": "Code Quality", "max_marks": 25.0},
                {"criterion": "code quality", "max_marks": 25.0},  # Duplicate case-insensitive
            ],
        },
    }

    res = client.post(
        f"/api/subjects/{subject_id}/assignments",
        json=asg_payload,
        headers=faculty_headers,
    )
    assert res.status_code in [409, 422]
    assert "duplicate" in res.text.lower()


def test_standalone_rubric_creation_exceeding_max_marks_rejected(
    client: TestClient, faculty_user: dict
):
    faculty_headers = faculty_user["headers"]
    code = f"VAL{datetime.now().strftime('%H%M%S%f')[:8]}"
    sub_res = client.post(
        "/api/subjects",
        json={"name": "Standalone Subject", "code": code},
        headers=faculty_headers,
    )
    subject_id = sub_res.json()["id"]

    due = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    asg_res = client.post(
        f"/api/subjects/{subject_id}/assignments",
        json={"title": "Standalone Assignment", "due_date": due, "max_marks": 40.0},
        headers=faculty_headers,
    )
    asg_id = asg_res.json()["id"]

    rub_res = client.post(
        f"/api/assignments/{asg_id}/rubric",
        json={
            "name": "Too High Rubric",
            "items": [
                {"criterion": "C1", "max_marks": 25.0},
                {"criterion": "C2", "max_marks": 20.0},  # Sum = 45.0 > 40.0
            ],
        },
        headers=faculty_headers,
    )
    assert rub_res.status_code == 422
    assert "exceed" in rub_res.text.lower()


def test_add_rubric_item_bounds_and_duplicate_validation(
    client: TestClient, faculty_user: dict
):
    faculty_headers = faculty_user["headers"]
    code = f"VAL{datetime.now().strftime('%H%M%S%f')[:8]}"
    sub_res = client.post(
        "/api/subjects",
        json={"name": "Bounds Subject", "code": code},
        headers=faculty_headers,
    )
    subject_id = sub_res.json()["id"]

    due = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    asg_res = client.post(
        f"/api/subjects/{subject_id}/assignments",
        json={"title": "Bound Assignment", "due_date": due, "max_marks": 50.0},
        headers=faculty_headers,
    )
    asg_id = asg_res.json()["id"]

    rub_res = client.post(
        f"/api/assignments/{asg_id}/rubric",
        json={
            "name": "Partial Rubric",
            "items": [{"criterion": "Initial Part", "max_marks": 40.0}],
        },
        headers=faculty_headers,
    )
    rubric_id = rub_res.json()["id"]

    # 1. Adding item exceeding remaining 10 marks -> 422
    add_excess = client.post(
        f"/api/rubrics/{rubric_id}/items",
        json={"criterion": "Second Part", "max_marks": 15.0},
        headers=faculty_headers,
    )
    assert add_excess.status_code == 422
    assert "exceed" in add_excess.text.lower()

    # 2. Adding duplicate criterion name -> 409
    add_dup = client.post(
        f"/api/rubrics/{rubric_id}/items",
        json={"criterion": "initial part", "max_marks": 5.0},
        headers=faculty_headers,
    )
    assert add_dup.status_code == 409
    assert "already exists" in add_dup.text.lower()

    # 3. Valid addition within remaining 10 marks -> 201
    add_valid = client.post(
        f"/api/rubrics/{rubric_id}/items",
        json={"criterion": "Second Part", "max_marks": 10.0},
        headers=faculty_headers,
    )
    assert add_valid.status_code == 201
    assert add_valid.json()["max_marks"] == 10.0


def test_update_rubric_item_bounds_and_duplicate_validation(
    client: TestClient, faculty_user: dict
):
    faculty_headers = faculty_user["headers"]
    code = f"VAL{datetime.now().strftime('%H%M%S%f')[:8]}"
    sub_res = client.post(
        "/api/subjects",
        json={"name": "Update Item Subject", "code": code},
        headers=faculty_headers,
    )
    subject_id = sub_res.json()["id"]

    due = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    asg_res = client.post(
        f"/api/subjects/{subject_id}/assignments",
        json={"title": "Update Assignment", "due_date": due, "max_marks": 50.0},
        headers=faculty_headers,
    )
    asg_id = asg_res.json()["id"]

    rub_res = client.post(
        f"/api/assignments/{asg_id}/rubric",
        json={
            "name": "Two Items Rubric",
            "items": [
                {"criterion": "Criterion A", "max_marks": 25.0},
                {"criterion": "Criterion B", "max_marks": 25.0},
            ],
        },
        headers=faculty_headers,
    )
    rubric_id = rub_res.json()["id"]
    item_b_id = rub_res.json()["items"][1]["id"]

    # 1. Update criterion B max_marks from 25 to 30 (sum = 55 > 50) -> 422
    up_excess = client.put(
        f"/api/rubric-items/{item_b_id}",
        json={"max_marks": 30.0},
        headers=faculty_headers,
    )
    assert up_excess.status_code == 422

    # 2. Update criterion B name to 'Criterion A' -> 409
    up_dup = client.put(
        f"/api/rubric-items/{item_b_id}",
        json={"criterion": "criterion a"},
        headers=faculty_headers,
    )
    assert up_dup.status_code == 409

    # 3. Valid update -> 200
    up_valid = client.put(
        f"/api/rubric-items/{item_b_id}",
        json={"criterion": "Criterion B Renamed", "max_marks": 20.0},
        headers=faculty_headers,
    )
    assert up_valid.status_code == 200
    assert up_valid.json()["criterion"] == "Criterion B Renamed"
    assert up_valid.json()["max_marks"] == 20.0


def test_reducing_assignment_max_marks_below_rubric_sum_rejected(
    client: TestClient, faculty_user: dict
):
    faculty_headers = faculty_user["headers"]
    code = f"VAL{datetime.now().strftime('%H%M%S%f')[:8]}"
    sub_res = client.post(
        "/api/subjects",
        json={"name": "Reduce Subject", "code": code},
        headers=faculty_headers,
    )
    subject_id = sub_res.json()["id"]

    due = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    asg_res = client.post(
        f"/api/subjects/{subject_id}/assignments",
        json={
            "title": "Reduce Marks Assignment",
            "due_date": due,
            "max_marks": 100.0,
            "rubric": {
                "name": "Full Rubric",
                "items": [
                    {"criterion": "Main Item", "max_marks": 80.0},
                ],
            },
        },
        headers=faculty_headers,
    )
    asg_id = asg_res.json()["id"]

    # Try to reduce assignment max_marks to 50.0 (less than 80.0) -> 422
    up_res = client.put(
        f"/api/assignments/{asg_id}",
        json={"max_marks": 50.0},
        headers=faculty_headers,
    )
    assert up_res.status_code == 422
    assert "adjust rubric criteria" in up_res.text.lower()


def test_enrolled_student_can_view_embedded_rubric_in_assignment(
    client: TestClient, faculty_user: dict, student_user: dict
):
    faculty_headers = faculty_user["headers"]
    student_headers = student_user["headers"]

    code = f"VAL{datetime.now().strftime('%H%M%S%f')[:8]}"
    sub_res = client.post(
        "/api/subjects",
        json={"name": "Student View Subject", "code": code},
        headers=faculty_headers,
    )
    subject_id = sub_res.json()["id"]

    due = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    asg_res = client.post(
        f"/api/subjects/{subject_id}/assignments",
        json={
            "title": "Student Rubric Assignment",
            "due_date": due,
            "max_marks": 50.0,
            "rubric": {
                "name": "Attached Rubric",
                "items": [
                    {"criterion": "Clarity", "max_marks": 20.0},
                    {"criterion": "Logic", "max_marks": 30.0},
                ],
            },
        },
        headers=faculty_headers,
    )
    asg_id = asg_res.json()["id"]

    # Student enrolls
    client.post(f"/api/subjects/{subject_id}/enroll", headers=student_headers)

    # Student gets assignment details
    view_res = client.get(f"/api/assignments/{asg_id}", headers=student_headers)
    assert view_res.status_code == 200
    assignment_data = view_res.json()
    assert assignment_data["rubric"] is not None
    assert assignment_data["rubric"]["name"] == "Attached Rubric"
    assert len(assignment_data["rubric"]["items"]) == 2


def test_blank_criterion_title_rejected(client: TestClient, faculty_user: dict):
    faculty_headers = faculty_user["headers"]
    code = f"VAL{datetime.now().strftime('%H%M%S%f')[:8]}"
    sub_res = client.post(
        "/api/subjects",
        json={"name": "Blank Subject", "code": code},
        headers=faculty_headers,
    )
    subject_id = sub_res.json()["id"]

    due = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    asg_payload = {
        "title": "Blank Criterion Assignment",
        "due_date": due,
        "max_marks": 50.0,
        "rubric": {
            "name": "Blank Criterion Rubric",
            "items": [{"criterion": "   ", "max_marks": 50.0}],
        },
    }

    res = client.post(
        f"/api/subjects/{subject_id}/assignments",
        json=asg_payload,
        headers=faculty_headers,
    )
    assert res.status_code == 422


def test_preparation_service_respects_assignment_max_marks_with_rubric(
    client: TestClient, faculty_user: dict, student_user: dict, db: Session
):
    faculty_headers = faculty_user["headers"]
    student_headers = student_user["headers"]

    code = f"VAL{datetime.now().strftime('%H%M%S%f')[:8]}"
    sub_res = client.post(
        "/api/subjects",
        json={"name": "Prep Service Subject", "code": code},
        headers=faculty_headers,
    )
    subject_id = sub_res.json()["id"]

    due = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    asg_res = client.post(
        f"/api/subjects/{subject_id}/assignments",
        json={
            "title": "Prep Service Assignment",
            "due_date": due,
            "max_marks": 75.0,
            "rubric": {
                "name": "Prep Rubric",
                "items": [
                    {"criterion": "Part A", "max_marks": 40.0},
                    {"criterion": "Part B", "max_marks": 35.0},
                ],
            },
        },
        headers=faculty_headers,
    )
    asg_id = asg_res.json()["id"]

    # Student enrolls and submits
    client.post(f"/api/subjects/{subject_id}/enroll", headers=student_headers)
    subm_res = client.post(
        f"/api/assignments/{asg_id}/submit",
        json={"submission_text": "Here is my submission text."},
        headers=student_headers,
    )
    assert subm_res.status_code == 201
    submission_id = subm_res.json()["id"]

    prep_service = get_assessment_preparation_service()
    context = prep_service.prepare_context(db, submission_id)

    assert context.total_max_marks == 75.0
    assert len(context.rubric_items) == 2
    assert context.rubric_items[0]["criterion"] == "Part A"
    assert context.rubric_items[1]["criterion"] == "Part B"

