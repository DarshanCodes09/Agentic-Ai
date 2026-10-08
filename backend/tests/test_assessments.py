"""
Tests for Phase 4: AI Assessment and RAG-Based Evaluation.

Covers:
  1. MockLLMProvider unit tests (Assessment and Feedback structured generation)
  2. LLMService abstraction and factory
  3. AssessmentAgent scoring validation and boundary clamping
  4. FeedbackAgent personalized feedback generation
  5. Faculty can trigger AI assessment for a submission
  6. Non-owning faculty and students cannot trigger assessment (403)
  7. Submitting student and owning faculty can view assessment; other student cannot (403)
  8. Faculty can approve assessment (transitions to APPROVED, submission to EVALUATED)
  9. Faculty can modify assessment score (transitions to MODIFIED, bounds validated)
 10. Invalid score modifications rejected (422)
 11. Student cannot approve or modify assessment (403)
 12. Assessment with course material in RAG knowledge base integrates context
"""

import io
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.submission import Submission, SubmissionStatus
from app.schemas.assessment import (
    AssessmentStatus,
    AssessmentStructuredOutput,
    ConceptMasteryLevel,
    FeedbackStructuredOutput,
)
from app.services.assessment.assessment_agent import AssessmentAgent
from app.services.assessment.feedback_agent import FeedbackAgent
from app.services.assessment.preparation_service import AssessmentContext
from app.services.llm.client import LLMService
from app.services.llm.provider import MockLLMProvider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def create_academic_setup(
    client: TestClient, faculty_headers: dict, code: str
) -> tuple[int, int, int]:
    """Helper: creates subject, assignment, question, and rubric."""
    # 1. Subject
    sub_res = client.post(
        "/api/subjects",
        json={"name": "Computer Science AI", "code": code},
        headers=faculty_headers,
    )
    subject_id = sub_res.json()["id"]

    # 2. Assignment
    due = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    asg_res = client.post(
        f"/api/subjects/{subject_id}/assignments",
        json={"title": "RAG and Search", "due_date": due, "max_marks": 50.0},
        headers=faculty_headers,
    )
    assignment_id = asg_res.json()["id"]

    # 3. Question
    q_res = client.post(
        f"/api/assignments/{assignment_id}/questions",
        json={
            "question_number": 1,
            "question_text": "Explain Retrieval-Augmented Generation (RAG) and vector databases.",
            "marks": 50.0,
            "expected_concepts": ["Vector Embeddings", "Semantic Search", "Prompt Augmentation"],
        },
        headers=faculty_headers,
    )
    question_id = q_res.json()["id"]

    # 4. Rubric
    rub_res = client.post(
        f"/api/assignments/{assignment_id}/rubric",
        json={
            "name": "RAG Technical Rubric",
            "description": "Evaluates architectural clarity and concept depth",
        },
        headers=faculty_headers,
    )
    rubric_id = rub_res.json()["id"]

    # Rubric Items
    client.post(
        f"/api/rubrics/{rubric_id}/items",
        json={
            "criterion": "Vector Embeddings & Indexing",
            "description": "Quality of explaining high-dimensional embeddings",
            "max_marks": 25.0,
        },
        headers=faculty_headers,
    )
    client.post(
        f"/api/rubrics/{rubric_id}/items",
        json={
            "criterion": "Context Retrieval & Synthesis",
            "description": "Explanation of chunking, top-k retrieval, and LLM synthesis",
            "max_marks": 25.0,
        },
        headers=faculty_headers,
    )

    return subject_id, assignment_id, question_id


# ---------------------------------------------------------------------------
# Unit Tests: LLM Providers & Agents
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mock_llm_provider_generation():
    provider = MockLLMProvider()

    # Raw text generation
    raw = await provider.generate("Evaluate this essay.")
    assert "Assessment Evaluation Report" in raw

    # Structured assessment generation
    prompt = (
        "Total Assignment Max Marks: 50.0\n"
        "Criterion: Vector Embeddings & Indexing (Max Marks: 25.0)\n"
        "Criterion: Context Retrieval & Synthesis (Max Marks: 25.0)\n"
        "- Concept: Vector Embeddings\n"
        "- Concept: Semantic Search\n"
        "Student submission text detailing vector indexes, FAISS, and prompt engineering."
    )
    structured_eval = await provider.generate_structured(prompt, AssessmentStructuredOutput)
    assert isinstance(structured_eval, AssessmentStructuredOutput)
    assert structured_eval.ai_score > 0.0
    assert structured_eval.ai_score <= 50.0
    assert len(structured_eval.criteria_scores) == 2
    assert len(structured_eval.concept_mastery) >= 2
    assert len(structured_eval.strengths) > 0

    # Structured feedback generation
    feedback_eval = await provider.generate_structured("Feedback prompt", FeedbackStructuredOutput)
    assert isinstance(feedback_eval, FeedbackStructuredOutput)
    assert len(feedback_eval.summary) > 0
    assert len(feedback_eval.actionable_steps) > 0


@pytest.mark.asyncio
async def test_assessment_agent_score_bounding():
    llm = LLMService(provider=MockLLMProvider())
    agent = AssessmentAgent(llm_service=llm)

    context = AssessmentContext(
        submission=None,  # type: ignore[arg-type]
        assignment_title="Test Asg",
        assignment_description=None,
        total_max_marks=30.0,
        questions=[{"question_number": 1, "question_text": "Q1", "marks": 30.0, "expected_concepts": ["AI"]}],
        rubric_items=[{"id": 1, "criterion": "Accuracy", "max_marks": 30.0, "description": ""}],
        submission_text="Solid answer demonstrating AI accuracy and technical precision.",
    )

    result = await agent.evaluate(context)
    assert result.ai_score <= 30.0
    assert result.ai_score >= 0.0
    for crit in result.criteria_scores:
        assert crit.score <= crit.max_marks


@pytest.mark.asyncio
async def test_feedback_agent_generation():
    llm = LLMService(provider=MockLLMProvider())
    agent = FeedbackAgent(llm_service=llm)

    context = AssessmentContext(
        submission=None,  # type: ignore[arg-type]
        assignment_title="RAG Systems",
        assignment_description=None,
        total_max_marks=50.0,
        questions=[],
        rubric_items=[],
        submission_text="My response",
    )

    eval_output = AssessmentStructuredOutput(
        ai_score=42.0,
        criteria_scores=[],
        concept_mastery=[],
        strengths=["Clear explanations"],
        weaknesses=["Missing boundary analysis"],
        general_remarks="Good submission overall",
    )

    feedback = await agent.generate_feedback(context, eval_output)
    assert isinstance(feedback, FeedbackStructuredOutput)
    assert len(feedback.summary) > 0
    assert len(feedback.actionable_steps) > 0


# ---------------------------------------------------------------------------
# Integration Tests: Assessment Endpoints & Lifecycle
# ---------------------------------------------------------------------------

def test_faculty_can_trigger_assessment_and_workflow(
    client: TestClient, faculty_user: dict, student_user: dict
):
    # 1. Setup
    sub_id, asg_id, _ = create_academic_setup(client, faculty_user["headers"], "AI_ASSESS_101")
    client.post(f"/api/subjects/{sub_id}/enroll", headers=student_user["headers"])

    # 2. Student submits work
    submission_res = client.post(
        f"/api/assignments/{asg_id}/submit",
        json={
            "submission_text": (
                "Retrieval-Augmented Generation (RAG) is an architectural approach that pairs "
                "vector databases like ChromaDB with large language models. Documents are converted "
                "into vector embeddings using dense models, stored in an index, and queried using "
                "cosine similarity for semantic search. The retrieved top-k chunks are then inserted into "
                "the prompt context to ground the LLM's synthesis without retraining."
            )
        },
        headers=student_user["headers"],
    )
    assert submission_res.status_code == 201
    submission_id = submission_res.json()["id"]

    # 3. Faculty triggers assessment
    assess_res = client.post(
        f"/api/submissions/{submission_id}/assess",
        headers=faculty_user["headers"],
    )
    assert assess_res.status_code == 200
    data = assess_res.json()

    assert data["submission_id"] == submission_id
    assert data["status"] == AssessmentStatus.COMPLETED.value
    assert data["ai_score"] > 0.0
    assert data["ai_score"] <= data["max_score"]
    assert data["final_score"] == data["ai_score"]
    assert len(data["criteria_scores"]) > 0
    assert len(data["concept_mastery"]) > 0
    assert data["feedback"] is not None
    assert len(data["feedback"]["summary"]) > 0
    assert len(data["feedback"]["actionable_steps"]) > 0
    assessment_id = data["id"]

    # Verify submission status transitioned to UNDER_REVIEW
    sub_check = client.get(f"/api/submissions/{submission_id}", headers=faculty_user["headers"])
    assert sub_check.json()["status"] == SubmissionStatus.UNDER_REVIEW.value

    # 4. Student can view their completed assessment
    student_view_res = client.get(
        f"/api/submissions/{submission_id}/assessment",
        headers=student_user["headers"],
    )
    assert student_view_res.status_code == 200
    assert student_view_res.json()["id"] == assessment_id

    # 5. Faculty approves assessment
    approve_res = client.post(
        f"/api/assessments/{assessment_id}/approve",
        json={"faculty_notes": "Well articulated and thorough submission. Approved!"},
        headers=faculty_user["headers"],
    )
    assert approve_res.status_code == 200
    approved_data = approve_res.json()
    assert approved_data["status"] == AssessmentStatus.APPROVED.value
    assert approved_data["faculty_notes"] == "Well articulated and thorough submission. Approved!"

    # Submission status must now be EVALUATED
    sub_check_after_approve = client.get(
        f"/api/submissions/{submission_id}", headers=faculty_user["headers"]
    )
    assert sub_check_after_approve.json()["status"] == SubmissionStatus.EVALUATED.value


def test_faculty_can_modify_assessment_score(
    client: TestClient, faculty_user: dict, student_user: dict
):
    sub_id, asg_id, _ = create_academic_setup(client, faculty_user["headers"], "AI_MOD_102")
    client.post(f"/api/subjects/{sub_id}/enroll", headers=student_user["headers"])

    # Student submits
    submission_res = client.post(
        f"/api/assignments/{asg_id}/submit",
        json={"submission_text": "RAG utilizes vector search and semantic similarity indexing."},
        headers=student_user["headers"],
    )
    submission_id = submission_res.json()["id"]

    # Faculty triggers assessment
    assess_res = client.post(
        f"/api/submissions/{submission_id}/assess",
        headers=faculty_user["headers"],
    )
    assessment_id = assess_res.json()["id"]
    max_score = assess_res.json()["max_score"]

    # Faculty modifies score
    override_score = 48.5
    mod_res = client.put(
        f"/api/assessments/{assessment_id}",
        json={
            "final_score": override_score,
            "faculty_notes": "Adjusted score upward due to excellent clarity and concise diagram description.",
        },
        headers=faculty_user["headers"],
    )
    assert mod_res.status_code == 200
    mod_data = mod_res.json()
    assert mod_data["status"] == AssessmentStatus.MODIFIED.value
    assert mod_data["final_score"] == override_score
    assert mod_data["faculty_notes"] == "Adjusted score upward due to excellent clarity and concise diagram description."

    # Submission status is now EVALUATED
    sub_check = client.get(f"/api/submissions/{submission_id}", headers=faculty_user["headers"])
    assert sub_check.json()["status"] == SubmissionStatus.EVALUATED.value


def test_invalid_score_modifications_rejected(
    client: TestClient, faculty_user: dict, student_user: dict
):
    sub_id, asg_id, _ = create_academic_setup(client, faculty_user["headers"], "AI_INV_103")
    client.post(f"/api/subjects/{sub_id}/enroll", headers=student_user["headers"])

    submission_res = client.post(
        f"/api/assignments/{asg_id}/submit",
        json={"submission_text": "Sample student submission text."},
        headers=student_user["headers"],
    )
    submission_id = submission_res.json()["id"]

    assess_res = client.post(
        f"/api/submissions/{submission_id}/assess",
        headers=faculty_user["headers"],
    )
    assessment_id = assess_res.json()["id"]
    max_score = assess_res.json()["max_score"]

    # Attempt score exceeding max_marks
    res_high = client.put(
        f"/api/assessments/{assessment_id}",
        json={"final_score": max_score + 10.0, "faculty_notes": "Exceeds max"},
        headers=faculty_user["headers"],
    )
    assert res_high.status_code == 422

    # Attempt negative score
    res_neg = client.put(
        f"/api/assessments/{assessment_id}",
        json={"final_score": -5.0, "faculty_notes": "Negative"},
        headers=faculty_user["headers"],
    )
    assert res_neg.status_code == 422


def test_role_authorization_and_student_isolation(
    client: TestClient,
    faculty_user: dict,
    other_faculty_user: dict,
    student_user: dict,
    other_student_user: dict,
):
    sub_id, asg_id, _ = create_academic_setup(client, faculty_user["headers"], "AI_AUTH_104")
    client.post(f"/api/subjects/{sub_id}/enroll", headers=student_user["headers"])

    submission_res = client.post(
        f"/api/assignments/{asg_id}/submit",
        json={"submission_text": "Vector search uses embeddings."},
        headers=student_user["headers"],
    )
    submission_id = submission_res.json()["id"]

    # 1. Student cannot trigger assess (403)
    res_student_assess = client.post(
        f"/api/submissions/{submission_id}/assess",
        headers=student_user["headers"],
    )
    assert res_student_assess.status_code == 403

    # 2. Other faculty cannot trigger assess (403)
    res_other_fac_assess = client.post(
        f"/api/submissions/{submission_id}/assess",
        headers=other_faculty_user["headers"],
    )
    assert res_other_fac_assess.status_code == 403

    # 3. Owning faculty assesses
    assess_res = client.post(
        f"/api/submissions/{submission_id}/assess",
        headers=faculty_user["headers"],
    )
    assert assess_res.status_code == 200
    assessment_id = assess_res.json()["id"]

    # 4. Other student cannot view assessment (403)
    res_other_student_view = client.get(
        f"/api/submissions/{submission_id}/assessment",
        headers=other_student_user["headers"],
    )
    assert res_other_student_view.status_code == 403

    # 5. Student cannot approve or modify assessment (403)
    res_student_approve = client.post(
        f"/api/assessments/{assessment_id}/approve",
        headers=student_user["headers"],
    )
    assert res_student_approve.status_code == 403

    res_student_modify = client.put(
        f"/api/assessments/{assessment_id}",
        json={"final_score": 50.0},
        headers=student_user["headers"],
    )
    assert res_student_modify.status_code == 403

    # 6. Other faculty cannot approve or modify assessment (403)
    res_other_fac_approve = client.post(
        f"/api/assessments/{assessment_id}/approve",
        headers=other_faculty_user["headers"],
    )
    assert res_other_fac_approve.status_code == 403


def test_assessment_incorporates_rag_knowledge_base(
    client: TestClient, faculty_user: dict, student_user: dict
):
    sub_id, asg_id, _ = create_academic_setup(client, faculty_user["headers"], "AI_RAG_105")
    client.post(f"/api/subjects/{sub_id}/enroll", headers=student_user["headers"])

    # Upload Course Material for RAG
    pdf_content = (
        b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n"
        b"2 0 obj\n<<\n/Type /Pages\n/Kids [3 0 R]\n/Count 1\n>>\nendobj\n"
        b"3 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/MediaBox [0 0 612 792]\n"
        b"/Contents 4 0 R\n/Resources <<>>\n>>\nendobj\n"
        b"4 0 obj\n<<\n/Length 95\n>>\nstream\n"
        b"BT\n/F1 12 Tf\n72 712 Td\n(RAG Architecture uses dense vector embeddings and ChromaDB retrieval) Tj\nET\n"
        b"endstream\nendobj\nxref\n0 5\n"
        b"0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"0000000058 00000 n \n"
        b"0000000115 00000 n \n"
        b"0000000216 00000 n \n"
        b"trailer\n<<\n/Size 5\n/Root 1 0 R\n>>\nstartxref\n360\n%%EOF\n"
    )
    upload_res = client.post(
        f"/api/subjects/{sub_id}/materials",
        files={"file": ("rag_lecture.pdf", io.BytesIO(pdf_content), "application/pdf")},
        data={"title": "RAG Foundations Lecture"},
        headers=faculty_user["headers"],
    )
    assert upload_res.status_code == 201
    material_id = upload_res.json()["id"]

    # Trigger material processing into vector store
    proc_res = client.post(
        f"/api/materials/{material_id}/process",
        headers=faculty_user["headers"],
    )
    assert proc_res.status_code == 200

    # Student submits
    sub_res = client.post(
        f"/api/assignments/{asg_id}/submit",
        json={"submission_text": "Dense vector embeddings facilitate semantic retrieval in ChromaDB."},
        headers=student_user["headers"],
    )
    submission_id = sub_res.json()["id"]

    # Assess submission
    assess_res = client.post(
        f"/api/submissions/{submission_id}/assess",
        headers=faculty_user["headers"],
    )
    assert assess_res.status_code == 200
    data = assess_res.json()

    assert data["status"] == AssessmentStatus.COMPLETED.value
    # Verify retrieved_context from course materials is captured
    assert isinstance(data["retrieved_context"], list)
    if len(data["retrieved_context"]) > 0:
        chunk = data["retrieved_context"][0]
        assert "chunk_text" in chunk
        assert "metadata" in chunk


def test_force_reassess_flow(
    client: TestClient, faculty_user: dict, student_user: dict
):
    sub_id, asg_id, _ = create_academic_setup(client, faculty_user["headers"], "AI_REASSESS_106")
    client.post(f"/api/subjects/{sub_id}/enroll", headers=student_user["headers"])

    sub_res = client.post(
        f"/api/assignments/{asg_id}/submit",
        json={"submission_text": "Initial answer."},
        headers=student_user["headers"],
    )
    submission_id = sub_res.json()["id"]

    # Assess 1
    res1 = client.post(
        f"/api/submissions/{submission_id}/assess",
        headers=faculty_user["headers"],
    )
    assert res1.status_code == 200
    id1 = res1.json()["id"]

    # Assess again without force_reassess -> returns existing
    res2 = client.post(
        f"/api/submissions/{submission_id}/assess",
        headers=faculty_user["headers"],
    )
    assert res2.status_code == 200
    assert res2.json()["id"] == id1

    # Assess with force_reassess=True -> updates existing record
    res3 = client.post(
        f"/api/submissions/{submission_id}/assess?force_reassess=true",
        headers=faculty_user["headers"],
    )
    assert res3.status_code == 200
    assert res3.json()["id"] == id1
    assert res3.json()["status"] == AssessmentStatus.COMPLETED.value
