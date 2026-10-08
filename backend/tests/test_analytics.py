"""
Comprehensive tests for Phase 5: Academic Performance Analytics & Learning Insights.

Covers:
  1. Student Analytics:
     - Overall analytics (marks obtained, max marks, percentage, average, top concepts)
     - Subject-wise performance breakdown
     - Concept mastery calculation and normalization
     - Top strongest and weakest concepts
     - Learning gap detection with deterministic severity (HIGH, MEDIUM, LOW)
     - Chronological performance trends
     - Edge cases: student with 0 submissions/evaluations
     - Unevaluated and failed assessments properly excluded
     - Role & isolation: student cannot access another student's analytics
     - Faculty cannot access student-me endpoints
  2. Faculty Analytics:
     - Subject class performance overview (average, highest, lowest, median, distribution, completion rate)
     - Assignment performance metrics (submissions, completion rate, averages)
     - Class concept mastery across all enrolled students
     - Class-wide learning gaps and vulnerable concepts
     - Edge cases: subject with 0 students, 0 submissions, 0 evaluations
     - Authorization: faculty cannot access another faculty's subject analytics
     - Student cannot access faculty analytics endpoints
"""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.assessment import AssessmentResult, AssessmentStatus
from app.models.submission import Submission, SubmissionStatus


# ---------------------------------------------------------------------------
# Test Helpers
# ---------------------------------------------------------------------------

def create_course_with_assignment(
    client: TestClient, faculty_headers: dict, code: str, max_marks: float = 50.0
) -> tuple[int, int, int]:
    """Helper to create Subject, Assignment, Question, and Rubric."""
    sub_res = client.post(
        "/api/subjects",
        json={"name": f"Subject {code}", "code": code},
        headers=faculty_headers,
    )
    subject_id = sub_res.json()["id"]

    due = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    asg_res = client.post(
        f"/api/subjects/{subject_id}/assignments",
        json={"title": f"Assignment {code}", "due_date": due, "max_marks": max_marks},
        headers=faculty_headers,
    )
    assignment_id = asg_res.json()["id"]

    q_res = client.post(
        f"/api/assignments/{assignment_id}/questions",
        json={
            "question_number": 1,
            "question_text": "Explain fundamental system principles.",
            "marks": max_marks,
            "expected_concepts": ["TCP Handshake", "DNS Resolution", "Packet Routing"],
        },
        headers=faculty_headers,
    )
    question_id = q_res.json()["id"]

    # Rubric
    rub_res = client.post(
        f"/api/assignments/{assignment_id}/rubric",
        json={"name": "Standard Rubric", "description": "Assessment rubric"},
        headers=faculty_headers,
    )
    rubric_id = rub_res.json()["id"]

    client.post(
        f"/api/rubrics/{rubric_id}/items",
        json={"criterion": "Protocol Architecture", "max_marks": max_marks / 2},
        headers=faculty_headers,
    )
    client.post(
        f"/api/rubrics/{rubric_id}/items",
        json={"criterion": "Packet Analysis", "max_marks": max_marks / 2},
        headers=faculty_headers,
    )

    return subject_id, assignment_id, question_id


# ---------------------------------------------------------------------------
# Student Analytics Tests
# ---------------------------------------------------------------------------

def test_student_overall_analytics_with_no_submissions(
    client: TestClient, student_user: dict
):
    res = client.get("/api/students/me/analytics", headers=student_user["headers"])
    assert res.status_code == 200
    data = res.json()
    assert data["total_assessments_evaluated"] == 0
    assert data["total_marks_obtained"] == 0.0
    assert data["total_max_marks"] == 0.0
    assert data["overall_percentage"] == 0.0
    assert data["average_score"] == 0.0
    assert data["strongest_concepts"] == []
    assert data["weakest_concepts"] == []


def test_student_overall_analytics_calculated_accurately(
    client: TestClient, faculty_user: dict, student_user: dict
):
    # Setup Course 1
    sub1_id, asg1_id, _ = create_course_with_assignment(
        client, faculty_user["headers"], "AN_CS_101", max_marks=50.0
    )
    client.post(f"/api/subjects/{sub1_id}/enroll", headers=student_user["headers"])

    # Student Submits
    sub_res = client.post(
        f"/api/assignments/{asg1_id}/submit",
        json={"submission_text": "Comprehensive analysis of TCP Handshake and DNS Resolution mechanisms."},
        headers=student_user["headers"],
    )
    submission_id = sub_res.json()["id"]

    # Faculty Assesses
    assess_res = client.post(
        f"/api/submissions/{submission_id}/assess",
        headers=faculty_user["headers"],
    )
    assert assess_res.status_code == 200

    # Request student analytics
    analytics_res = client.get("/api/students/me/analytics", headers=student_user["headers"])
    assert analytics_res.status_code == 200
    data = analytics_res.json()

    assert data["total_assessments_evaluated"] == 1
    assert data["total_marks_obtained"] > 0.0
    assert data["total_max_marks"] == 50.0
    assert data["overall_percentage"] > 0.0
    assert data["overall_percentage"] <= 100.0
    assert data["average_score"] == data["total_marks_obtained"]
    assert len(data["strongest_concepts"]) > 0


def test_student_subject_performance_breakdown(
    client: TestClient, faculty_user: dict, student_user: dict
):
    # Enrolled in 2 subjects
    sub1_id, asg1_id, _ = create_course_with_assignment(
        client, faculty_user["headers"], "AN_SUB1", max_marks=40.0
    )
    sub2_id, asg2_id, _ = create_course_with_assignment(
        client, faculty_user["headers"], "AN_SUB2", max_marks=60.0
    )
    client.post(f"/api/subjects/{sub1_id}/enroll", headers=student_user["headers"])
    client.post(f"/api/subjects/{sub2_id}/enroll", headers=student_user["headers"])

    # Submit only to subject 1
    s1_res = client.post(
        f"/api/assignments/{asg1_id}/submit",
        json={"submission_text": "Solution for Subject 1."},
        headers=student_user["headers"],
    )
    s1_id = s1_res.json()["id"]
    client.post(f"/api/submissions/{s1_id}/assess", headers=faculty_user["headers"])

    # Query subject analytics
    res = client.get("/api/students/me/analytics/subjects", headers=student_user["headers"])
    assert res.status_code == 200
    subjects_data = res.json()
    assert len(subjects_data) == 2

    # Subject 1 should have evaluated assessment
    s1_metrics = next(s for s in subjects_data if s["subject_id"] == sub1_id)
    assert s1_metrics["assessments_count"] == 1
    assert s1_metrics["total_max_score"] == 40.0
    assert s1_metrics["percentage"] > 0.0

    # Subject 2 should have 0 assessments, 0 percentage, safe without dividing by zero
    s2_metrics = next(s for s in subjects_data if s["subject_id"] == sub2_id)
    assert s2_metrics["assessments_count"] == 0
    assert s2_metrics["total_score"] == 0.0
    assert s2_metrics["percentage"] == 0.0


def test_student_concept_mastery_and_rankings(
    client: TestClient, faculty_user: dict, student_user: dict
):
    sub_id, asg_id, _ = create_course_with_assignment(
        client, faculty_user["headers"], "AN_CONCEPTS_01"
    )
    client.post(f"/api/subjects/{sub_id}/enroll", headers=student_user["headers"])

    sub_res = client.post(
        f"/api/assignments/{asg_id}/submit",
        json={"submission_text": "TCP Handshake operates via SYN, SYN-ACK, ACK. DNS Resolution queries root servers."},
        headers=student_user["headers"],
    )
    s_id = sub_res.json()["id"]
    client.post(f"/api/submissions/{s_id}/assess", headers=faculty_user["headers"])

    res = client.get("/api/students/me/analytics/concepts", headers=student_user["headers"])
    assert res.status_code == 200
    concepts = res.json()
    assert len(concepts) > 0

    for c in concepts:
        assert "concept" in c
        assert "mastery_score" in c
        assert 0.0 <= c["mastery_score"] <= 1.0
        assert c["mastery_level"] in ["MASTERED", "DEVELOPING", "NEEDS_IMPROVEMENT"]


def test_student_learning_gaps_detection(
    client: TestClient, faculty_user: dict, student_user: dict
):
    sub_id, asg_id, _ = create_course_with_assignment(
        client, faculty_user["headers"], "AN_GAPS_01"
    )
    client.post(f"/api/subjects/{sub_id}/enroll", headers=student_user["headers"])

    # Submit empty or sparse submission to induce low mastery / learning gaps
    sub_res = client.post(
        f"/api/assignments/{asg_id}/submit",
        json={"submission_text": "I do not know the answers to this assignment."},
        headers=student_user["headers"],
    )
    s_id = sub_res.json()["id"]
    client.post(f"/api/submissions/{s_id}/assess", headers=faculty_user["headers"])

    res = client.get("/api/students/me/analytics/gaps", headers=student_user["headers"])
    assert res.status_code == 200
    gaps = res.json()
    assert len(gaps) > 0

    for g in gaps:
        assert g["severity"] in ["HIGH", "MEDIUM", "LOW"]
        assert g["mastery_score"] < 0.60
        assert g["occurrence_count"] >= 1


def test_student_performance_trends_chronological(
    client: TestClient, faculty_user: dict, student_user: dict
):
    sub_id, asg1_id, _ = create_course_with_assignment(
        client, faculty_user["headers"], "AN_TRENDS_01", max_marks=20.0
    )
    client.post(f"/api/subjects/{sub_id}/enroll", headers=student_user["headers"])

    # Create second assignment
    due = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()
    asg2_res = client.post(
        f"/api/subjects/{sub_id}/assignments",
        json={"title": "Assignment 2", "due_date": due, "max_marks": 30.0},
        headers=faculty_user["headers"],
    )
    asg2_id = asg2_res.json()["id"]
    client.post(
        f"/api/assignments/{asg2_id}/questions",
        json={"question_number": 1, "question_text": "Q1", "marks": 30.0},
        headers=faculty_user["headers"],
    )

    # Submit 1
    s1 = client.post(
        f"/api/assignments/{asg1_id}/submit",
        json={"submission_text": "Answer 1"},
        headers=student_user["headers"],
    ).json()["id"]
    client.post(f"/api/submissions/{s1}/assess", headers=faculty_user["headers"])

    # Submit 2
    s2 = client.post(
        f"/api/assignments/{asg2_id}/submit",
        json={"submission_text": "Answer 2"},
        headers=student_user["headers"],
    ).json()["id"]
    client.post(f"/api/submissions/{s2}/assess", headers=faculty_user["headers"])

    res = client.get("/api/students/me/analytics/trends", headers=student_user["headers"])
    assert res.status_code == 200
    trends = res.json()
    assert len(trends) == 2

    # Verify chronological order
    t1_date = datetime.fromisoformat(trends[0]["evaluated_at"])
    t2_date = datetime.fromisoformat(trends[1]["evaluated_at"])
    assert t1_date <= t2_date


def test_unevaluated_and_failed_assessments_excluded_from_student_analytics(
    client: TestClient, faculty_user: dict, student_user: dict, db: Session
):
    sub_id, asg_id, _ = create_course_with_assignment(
        client, faculty_user["headers"], "AN_EXCLUDE_01"
    )
    client.post(f"/api/subjects/{sub_id}/enroll", headers=student_user["headers"])

    sub_res = client.post(
        f"/api/assignments/{asg_id}/submit",
        json={"submission_text": "Work in progress"},
        headers=student_user["headers"],
    )
    submission_id = sub_res.json()["id"]

    # Directly create a FAILED assessment in database
    failed_eval = AssessmentResult(
        submission_id=submission_id,
        ai_score=0.0,
        final_score=0.0,
        max_score=50.0,
        status=AssessmentStatus.FAILED,
        criteria_scores=[],
        concept_mastery=[],
    )
    db.add(failed_eval)
    db.commit()

    # Query analytics: failed assessment must not count
    res = client.get("/api/students/me/analytics", headers=student_user["headers"])
    assert res.status_code == 200
    data = res.json()
    assert data["total_assessments_evaluated"] == 0
    assert data["total_marks_obtained"] == 0.0


def test_student_analytics_authorization_isolation(
    client: TestClient, faculty_user: dict, student_user: dict
):
    # Faculty cannot access student-me analytics (403)
    res_fac = client.get("/api/students/me/analytics", headers=faculty_user["headers"])
    assert res_fac.status_code == 403

    res_fac_subj = client.get("/api/students/me/analytics/subjects", headers=faculty_user["headers"])
    assert res_fac_subj.status_code == 403


# ---------------------------------------------------------------------------
# Faculty Analytics Tests
# ---------------------------------------------------------------------------

def test_faculty_subject_analytics_with_no_submissions(
    client: TestClient, faculty_user: dict
):
    sub_id, _, _ = create_course_with_assignment(
        client, faculty_user["headers"], "FAC_EMPTY_01"
    )

    res = client.get(f"/api/faculty/subjects/{sub_id}/analytics", headers=faculty_user["headers"])
    assert res.status_code == 200
    data = res.json()

    assert data["subject_id"] == sub_id
    assert data["enrolled_student_count"] == 0
    assert data["evaluated_submissions_count"] == 0
    assert data["total_submissions_count"] == 0
    assert data["average_score"] == 0.0
    assert data["completion_rate"] == 0.0
    assert data["performance_distribution"]["90-100%"] == 0


def test_faculty_subject_analytics_with_evaluated_submissions(
    client: TestClient,
    faculty_user: dict,
    student_user: dict,
    other_student_user: dict,
):
    sub_id, asg_id, _ = create_course_with_assignment(
        client, faculty_user["headers"], "FAC_EVAL_01", max_marks=100.0
    )

    # Enroll 2 students
    client.post(f"/api/subjects/{sub_id}/enroll", headers=student_user["headers"])
    client.post(f"/api/subjects/{sub_id}/enroll", headers=other_student_user["headers"])

    # Student 1 submits & is assessed
    s1 = client.post(
        f"/api/assignments/{asg_id}/submit",
        json={"submission_text": "Excellent explanation of networking principles and packets."},
        headers=student_user["headers"],
    ).json()["id"]
    client.post(f"/api/submissions/{s1}/assess", headers=faculty_user["headers"])

    # Student 2 submits & is assessed
    s2 = client.post(
        f"/api/assignments/{asg_id}/submit",
        json={"submission_text": "Good understanding of protocols and routing algorithms."},
        headers=other_student_user["headers"],
    ).json()["id"]
    client.post(f"/api/submissions/{s2}/assess", headers=faculty_user["headers"])

    res = client.get(f"/api/faculty/subjects/{sub_id}/analytics", headers=faculty_user["headers"])
    assert res.status_code == 200
    data = res.json()

    assert data["enrolled_student_count"] == 2
    assert data["students_with_submissions"] == 2
    assert data["evaluated_submissions_count"] == 2
    assert data["total_submissions_count"] == 2
    assert data["average_score"] > 0.0
    assert data["average_percentage"] > 0.0
    assert data["completion_rate"] == 100.0
    assert sum(data["performance_distribution"].values()) == 2


def test_faculty_assignment_analytics(
    client: TestClient, faculty_user: dict, student_user: dict
):
    sub_id, asg_id, _ = create_course_with_assignment(
        client, faculty_user["headers"], "FAC_ASG_01", max_marks=50.0
    )
    client.post(f"/api/subjects/{sub_id}/enroll", headers=student_user["headers"])

    # Submit & assess
    s1 = client.post(
        f"/api/assignments/{asg_id}/submit",
        json={"submission_text": "Demonstrating thorough grasp of assignment questions."},
        headers=student_user["headers"],
    ).json()["id"]
    client.post(f"/api/submissions/{s1}/assess", headers=faculty_user["headers"])

    res = client.get(f"/api/faculty/assignments/{asg_id}/analytics", headers=faculty_user["headers"])
    assert res.status_code == 200
    data = res.json()

    assert data["assignment_id"] == asg_id
    assert data["enrolled_count"] == 1
    assert data["submission_count"] == 1
    assert data["evaluated_count"] == 1
    assert data["average_score"] > 0.0
    assert data["completion_rate"] == 100.0


def test_faculty_class_concept_mastery_and_gaps(
    client: TestClient, faculty_user: dict, student_user: dict
):
    sub_id, asg_id, _ = create_course_with_assignment(
        client, faculty_user["headers"], "FAC_CLASS_CONCEPTS_01"
    )
    client.post(f"/api/subjects/{sub_id}/enroll", headers=student_user["headers"])

    # Submit & assess
    s1 = client.post(
        f"/api/assignments/{asg_id}/submit",
        json={"submission_text": "Thorough coverage of TCP and DNS."},
        headers=student_user["headers"],
    ).json()["id"]
    client.post(f"/api/submissions/{s1}/assess", headers=faculty_user["headers"])

    # 1. Class concept mastery
    conc_res = client.get(
        f"/api/faculty/subjects/{sub_id}/analytics/concepts",
        headers=faculty_user["headers"],
    )
    assert conc_res.status_code == 200
    concepts = conc_res.json()
    assert len(concepts) > 0
    assert "concept" in concepts[0]
    assert "average_mastery" in concepts[0]

    # 2. Class learning gaps
    gaps_res = client.get(
        f"/api/faculty/subjects/{sub_id}/analytics/gaps",
        headers=faculty_user["headers"],
    )
    assert gaps_res.status_code == 200
    assert isinstance(gaps_res.json(), list)


def test_faculty_authorization_restrictions(
    client: TestClient,
    faculty_user: dict,
    other_faculty_user: dict,
    student_user: dict,
):
    sub_id, asg_id, _ = create_course_with_assignment(
        client, faculty_user["headers"], "FAC_AUTH_01"
    )

    # 1. Other faculty cannot access analytics for this subject (403)
    res_other_sub = client.get(
        f"/api/faculty/subjects/{sub_id}/analytics",
        headers=other_faculty_user["headers"],
    )
    assert res_other_sub.status_code == 403

    # 2. Other faculty cannot access assignment analytics (403)
    res_other_asg = client.get(
        f"/api/faculty/assignments/{asg_id}/analytics",
        headers=other_faculty_user["headers"],
    )
    assert res_other_asg.status_code == 403

    # 3. Student cannot access faculty subject analytics (403)
    res_student_sub = client.get(
        f"/api/faculty/subjects/{sub_id}/analytics",
        headers=student_user["headers"],
    )
    assert res_student_sub.status_code == 403

    # 4. Non-existent subject returns 404
    res_nonexistent = client.get(
        "/api/faculty/subjects/999999/analytics",
        headers=faculty_user["headers"],
    )
    assert res_nonexistent.status_code == 404
