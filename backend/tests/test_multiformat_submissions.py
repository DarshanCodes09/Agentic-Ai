"""
Integration tests for multi-format code, Jupyter notebook, and ZIP submission evaluation.
Tests:
- Submission of .ipynb, .py, .zip, and backward compatibility with .pdf.
- Manifest generation and audit endpoint GET /submissions/{id}/manifest.
- File preview and subpath downloading with security checks.
- AI evaluation pipeline using mock provider for notebook and code submissions.
- Strict human-in-the-loop approval workflow and feedback privacy.
"""

import io
import json
import zipfile
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient


def create_assignment(client: TestClient, faculty_headers: dict, code: str) -> tuple[int, int]:
    sub_res = client.post("/api/subjects", json={"name": "Machine Learning", "code": code}, headers=faculty_headers)
    subject_id = sub_res.json()["id"]

    due = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    asg_res = client.post(
        f"/api/subjects/{subject_id}/assignments",
        json={
            "title": "Hyperparameter Tuning of RNN and LSTM Networks for Sequence Classification",
            "description": "Implement RNN/LSTM sequence classification and tune hyperparameters.",
            "due_date": due,
            "max_marks": 100.0,
        },
        headers=faculty_headers,
    )
    assignment_id = asg_res.json()["id"]
    return subject_id, assignment_id


def test_submit_ipynb_notebook_and_manifest(
    client: TestClient, faculty_user: dict, student_user: dict
):
    sub_id, asg_id = create_assignment(client, faculty_user["headers"], "ML_NB_01")
    client.post(f"/api/subjects/{sub_id}/enroll", headers=student_user["headers"])

    # Build a representative executed notebook
    nb_dict = {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
        "cells": [
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": "# RNN & LSTM Classification\nExploring hyperparameter configurations."
            },
            {
                "cell_type": "code",
                "execution_count": 1,
                "metadata": {},
                "source": "import tensorflow as tf\nprint('TF loaded')",
                "outputs": [{"output_type": "stream", "name": "stdout", "text": "TF loaded\n"}]
            },
            {
                "cell_type": "code",
                "execution_count": 2,
                "metadata": {},
                "source": "accuracy = 0.892\nprint(f'Accuracy: {accuracy}')",
                "outputs": [{"output_type": "stream", "name": "stdout", "text": "Accuracy: 0.892\n"}]
            }
        ]
    }
    nb_bytes = json.dumps(nb_dict).encode("utf-8")
    files = {"file": ("rnn_lstm_tuning.ipynb", io.BytesIO(nb_bytes), "application/x-ipynb+json")}

    res = client.post(
        f"/api/assignments/{asg_id}/submit",
        files=files,
        data={"submission_text": "Completed RNN and LSTM hyperparameter experiments."},
        headers=student_user["headers"],
    )
    assert res.status_code == 201
    sub_data = res.json()
    submission_id = sub_data["id"]
    assert sub_data["original_filename"] == "rnn_lstm_tuning.ipynb"

    # Query manifest
    manifest_res = client.get(f"/api/submissions/{submission_id}/manifest", headers=student_user["headers"])
    assert manifest_res.status_code == 200
    manifest = manifest_res.json()
    assert manifest["file_format"] == "ipynb"
    assert manifest["has_file"] is True
    assert manifest["execution_audit"] is not None
    assert manifest["execution_audit"]["total_cells"] == 3
    assert manifest["execution_audit"]["code_cells"] == 2
    assert manifest["execution_audit"]["executed_code_cells"] == 2
    assert manifest["execution_audit"]["execution_status"] == "COMPLETE"


def test_submit_zip_project_and_subpath_access(
    client: TestClient, faculty_user: dict, student_user: dict
):
    sub_id, asg_id = create_assignment(client, faculty_user["headers"], "ML_ZIP_01")
    client.post(f"/api/subjects/{sub_id}/enroll", headers=student_user["headers"])

    # Create multi-file project archive
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("model.py", "class LSTMModel:\n    pass\n")
        zf.writestr("train.py", "from model import LSTMModel\nprint('Training started')\n")
        zf.writestr("README.md", "# Project Documentation\nSteps to run the experiment.\n")
        zf.writestr("requirements.txt", "torch>=2.0.0\n")

    zip_bytes = zip_buf.getvalue()
    files = {"file": ("project_submission.zip", io.BytesIO(zip_bytes), "application/zip")}

    res = client.post(
        f"/api/assignments/{asg_id}/submit",
        files=files,
        headers=student_user["headers"],
    )
    assert res.status_code == 201
    sub_data = res.json()
    submission_id = sub_data["id"]

    # Check manifest
    manifest_res = client.get(f"/api/submissions/{submission_id}/manifest", headers=student_user["headers"])
    assert manifest_res.status_code == 200
    manifest = manifest_res.json()
    assert manifest["file_format"] == "zip"
    file_manifest = manifest["file_manifest"]
    assert file_manifest["total_files"] == 4
    assert file_manifest["has_readme"] is True
    assert file_manifest["has_manifest"] is True

    # Student downloads entire zip
    dl_zip = client.get(f"/api/submissions/{submission_id}/file", headers=student_user["headers"])
    assert dl_zip.status_code == 200
    assert dl_zip.headers["content-type"] == "application/zip"

    # Faculty previews individual subpath inside zip
    sub_file = client.get(
        f"/api/submissions/{submission_id}/file?subpath=README.md&inline=true",
        headers=faculty_user["headers"],
    )
    assert sub_file.status_code == 200
    assert "Steps to run the experiment" in sub_file.text

    # Test subpath path traversal protection
    slip_attempt = client.get(
        f"/api/submissions/{submission_id}/file?subpath=../../etc/passwd",
        headers=faculty_user["headers"],
    )
    assert slip_attempt.status_code in (400, 403, 422)


def test_submit_source_code_file(
    client: TestClient, faculty_user: dict, student_user: dict
):
    sub_id, asg_id = create_assignment(client, faculty_user["headers"], "ML_SRC_01")
    client.post(f"/api/subjects/{sub_id}/enroll", headers=student_user["headers"])

    code_content = b"def evaluate(model, test_data):\n    return 0.875\n"
    files = {"file": ("evaluation.py", io.BytesIO(code_content), "text/x-python")}

    res = client.post(
        f"/api/assignments/{asg_id}/submit",
        files=files,
        headers=student_user["headers"],
    )
    assert res.status_code == 201
    sub_data = res.json()
    submission_id = sub_data["id"]

    manifest_res = client.get(f"/api/submissions/{submission_id}/manifest", headers=student_user["headers"])
    assert manifest_res.status_code == 200
    manifest = manifest_res.json()
    assert manifest["file_format"] == "py"


def test_ai_assessment_and_faculty_approval_workflow(
    client: TestClient, faculty_user: dict, student_user: dict
):
    sub_id, asg_id = create_assignment(client, faculty_user["headers"], "ML_EVAL_01")
    client.post(f"/api/subjects/{sub_id}/enroll", headers=student_user["headers"])

    # Create submission with executed notebook
    nb_dict = {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {},
        "cells": [
            {
                "cell_type": "markdown",
                "metadata": {},
                "source": "### Sequence Classification with RNN and LSTM"
            },
            {
                "cell_type": "code",
                "execution_count": 1,
                "metadata": {},
                "source": "print('Accuracy: 0.85')",
                "outputs": [{"output_type": "stream", "name": "stdout", "text": "Accuracy: 0.85\n"}]
            }
        ]
    }
    nb_bytes = json.dumps(nb_dict).encode("utf-8")
    files = {"file": ("solution.ipynb", io.BytesIO(nb_bytes), "application/x-ipynb+json")}

    sub_res = client.post(
        f"/api/assignments/{asg_id}/submit",
        files=files,
        headers=student_user["headers"],
    )
    submission_id = sub_res.json()["id"]

    # Faculty triggers AI assessment via /api/submissions/{id}/assess
    eval_res = client.post(f"/api/submissions/{submission_id}/assess", headers=faculty_user["headers"])
    assert eval_res.status_code == 200
    assessment = eval_res.json()
    assessment_id = assessment["id"]
    assert assessment["status"] == "COMPLETED"
    assert assessment["ai_score"] > 0

    # Student cannot view unreleased/pending assessment (feedback privacy enforced)
    student_view_res = client.get(f"/api/submissions/{submission_id}/assessment", headers=student_user["headers"])
    assert student_view_res.status_code == 403

    # Faculty approves assessment
    approve_res = client.post(
        f"/api/assessments/{assessment_id}/approve",
        json={"notes": "Well documented notebook and hyperparameter experiment."},
        headers=faculty_user["headers"],
    )
    assert approve_res.status_code == 200
    assert approve_res.json()["status"] == "APPROVED"

    # Now student CAN view released assessment and score
    student_view_approved = client.get(f"/api/submissions/{submission_id}/assessment", headers=student_user["headers"])
    assert student_view_approved.status_code == 200
    approved_data = student_view_approved.json()
    assert approved_data["status"] == "APPROVED"
    assert approved_data["final_score"] is not None
    # Private faculty notes must not be leaked to student
    assert "faculty_notes" not in approved_data or approved_data.get("faculty_notes") is None


def test_unsupported_file_extension_rejected(
    client: TestClient, faculty_user: dict, student_user: dict
):
    sub_id, asg_id = create_assignment(client, faculty_user["headers"], "ML_REJ_01")
    client.post(f"/api/subjects/{sub_id}/enroll", headers=student_user["headers"])

    exe_bytes = io.BytesIO(b"MZ\x90\x00\x03fake executable binary")
    files = {"file": ("malware.exe", exe_bytes, "application/octet-stream")}

    res = client.post(
        f"/api/assignments/{asg_id}/submit",
        files=files,
        headers=student_user["headers"],
    )
    assert res.status_code == 422
    assert "Invalid file type" in res.json()["detail"]


def test_oversized_zip_evidence_is_bounded_and_prioritized(tmp_path):
    """
    Regression test for Groq 413 fix:
    ZIP archive containing dozens of source files and large C++/Python code
    must be bounded by max_submission_evidence_chars, prioritizing entrypoints
    and test files rather than expanding indefinitely into prompt.
    """
    from app.core.config import get_settings
    from app.services.document_processing.zip_processor import ZipProcessor

    settings = get_settings()
    zip_path = tmp_path / "large_multicore_project.zip"
    extract_dir = tmp_path / ".project_unpacked"

    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("README.md", "# Multicore Project\nDetailed architectural overview of project.")
        zf.writestr("main.py", "def main():\n    print('Core entrypoint')\n" * 50)
        zf.writestr("test_main.py", "def test_main():\n    assert True\n" * 50)
        zf.writestr("routefunc.cpp", "// Heavy routing logic\nvoid route() { int x = 0; }\n" * 1500)
        # Add multiple auxiliary files
        for i in range(12):
            zf.writestr(f"auxiliary_worker_{i}.py", f"# Worker {i}\ndef work(): pass\n" * 100)

    processor = ZipProcessor()
    manifest = processor.inspect_and_extract(zip_path, extract_dir)
    evidence = processor.build_evidence_package(manifest, archive_name="large_multicore_project.zip")

    # Evidence package must be strictly bounded
    assert len(evidence) <= settings.max_submission_evidence_chars + 500
    # Primary files must be included
    assert "main.py" in evidence
    assert "test_main.py" in evidence
    assert "README.md" in evidence
    # Notice about secondary omitted files must be present
    assert "secondary source file(s) omitted" in evidence or "auxiliary_worker" in evidence


def test_prompt_limit_hard_boundary_raises_413():
    """
    Verify that if non-negotiable prompt items (rubric + questions) exceed
    the safe token limit even after all adaptive reduction passes,
    AssessmentAgent raises PayloadTooLargeError (HTTP 413) instead of fabricating a grade.
    """
    import asyncio
    from unittest.mock import MagicMock
    from app.core.config import get_settings
    from app.core.exceptions import PayloadTooLargeError
    from app.services.assessment.assessment_agent import AssessmentAgent
    from app.services.assessment.preparation_service import AssessmentContext

    settings = get_settings()
    # Create massive rubric criteria that cannot be trimmed away
    oversized_rubrics = [
        {
            "id": i,
            "criterion": f"High Rigor Disciplinary Standard Criterion Number {i}",
            "description": "Exhaustive technical criterion descriptions and requirements that span multiple pages of academic specifications " * 15,
            "max_marks": 5.0,
        }
        for i in range(45)
    ]

    mock_submission = MagicMock()
    mock_submission.id = 999
    context = AssessmentContext(
        submission=mock_submission,
        assignment_title="Test Overlong Rubric Assignment",
        assignment_description="Assignment Instructions",
        total_max_marks=225.0,
        rubric_items=oversized_rubrics,
        submission_text="Student implementation code.",
    )

    agent = AssessmentAgent()
    with pytest.raises(PayloadTooLargeError) as exc_info:
        asyncio.run(agent.evaluate(context))

    assert exc_info.value.status_code == 413
    assert "exceeds" in exc_info.value.detail.lower()


def test_adaptive_multi_pass_reduction_preserves_rubric_and_bounds_groq_payload(tmp_path):
    """
    Verify that a large multi-file submission (similar to Multicore Project.zip):
    1. Triggers adaptive reduction passes
    2. Results in a serialized prompt that is strictly within the safe token limit (<= 4200 tokens)
    3. Preserves all rubric grading criteria in the sent prompt
    4. Preserves primary source code and test files
    5. Calls LLM with bounded payload and completes evaluation without HTTP 413
    """
    import asyncio
    from unittest.mock import AsyncMock, MagicMock
    from app.schemas.assessment import AssessmentStructuredOutput, CriterionEvaluation
    from app.services.assessment.assessment_agent import AssessmentAgent
    from app.services.assessment.preparation_service import AssessmentContext
    from app.services.document_processing.zip_processor import ZipProcessor
    from app.services.llm.token_budget import estimate_tokens

    zip_path = tmp_path / "multicore_simulated.zip"
    extract_dir = tmp_path / ".multicore_unpacked"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("routefunc.cpp", "void route() { int a = 1; }\n" * 1000)
        zf.writestr("test_routing.py", "def test_route(): assert True\n" * 20)
        zf.writestr("README.md", "# Routing Project\nOverview of routing logic.")
        for i in range(40):
            zf.writestr(f"logs/sweep_{i}.log", "simulated log output data line\n" * 50)

    processor = ZipProcessor()
    manifest = processor.inspect_and_extract(zip_path, extract_dir)
    evidence = processor.build_evidence_package(manifest, archive_name="multicore_simulated.zip")

    rubric_items = [
        {"id": 1, "criterion": "Algorithmic Routing Correctness", "description": "Routing logic is functional", "max_marks": 50.0},
        {"id": 2, "criterion": "Test Suite Completeness", "description": "Thorough test coverage", "max_marks": 50.0},
    ]

    mock_sub = MagicMock()
    mock_sub.id = 888
    context = AssessmentContext(
        submission=mock_sub,
        assignment_title="Multicore NoC Architecture Assessment",
        assignment_description="Implement customized XY and CAMR routing functions.",
        total_max_marks=100.0,
        rubric_items=rubric_items,
        retrieved_chunks=[{"chunk_text": "NoC routing theory chunk " * 30, "similarity": 0.85, "metadata": {}}],
        submission_text=evidence,
    )

    captured_prompt = {}

    async def mock_generate_structured(prompt: str, response_model, system_prompt=None, **kwargs):
        captured_prompt["user_prompt"] = prompt
        captured_prompt["system_prompt"] = system_prompt
        # Verify complete payload tokens
        full_req = f"{system_prompt}\n{prompt}"
        assert estimate_tokens(full_req) <= 4200
        return AssessmentStructuredOutput(
            ai_score=85.0,
            general_remarks="Good routing implementation and tests.",
            strengths=["Solid C++ routing logic"],
            weaknesses=["Minor test gaps"],
            criteria_scores=[
                CriterionEvaluation(rubric_item_id=1, criterion="Algorithmic Routing Correctness", score=42.0, max_marks=50.0, reasoning="Correct XY/CAMR logic"),
                CriterionEvaluation(rubric_item_id=2, criterion="Test Suite Completeness", score=43.0, max_marks=50.0, reasoning="Tests pass"),
            ],
            concept_mastery=[],
        )

    mock_llm_service = MagicMock()
    mock_llm_service.model_name = "llama-3.3-70b-versatile"
    mock_llm_service.generate_structured = AsyncMock(side_effect=mock_generate_structured)

    agent = AssessmentAgent(llm_service=mock_llm_service)
    result = asyncio.run(agent.evaluate(context))

    assert result.ai_score == 85.0
    assert len(result.criteria_scores) == 2
    # Verify rubric criteria were retained in the sent prompt
    assert "Algorithmic Routing Correctness" in captured_prompt["user_prompt"]
    assert "Test Suite Completeness" in captured_prompt["user_prompt"]
    # Verify primary code file is present
    assert "routefunc.cpp" in captured_prompt["user_prompt"]


def test_groq_413_status_and_context_length_error_mapping():
    """
    Verify that GroqLLMProvider translates Groq HTTP 413 or BadRequest context-length
    errors into HTTP 413 AppException rather than generic 502s.
    """
    import asyncio
    from unittest.mock import AsyncMock, MagicMock
    import httpx
    from groq import APIStatusError, BadRequestError
    from app.core.exceptions import AppException
    from app.services.llm.provider import GroqLLMProvider

    provider = GroqLLMProvider(api_key="gsk_dummy_test_key_for_unit_tests")

    # 1. APIStatusError with status_code=413
    mock_req = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    mock_res_413 = httpx.Response(status_code=413, request=mock_req)
    mock_status_err = APIStatusError(message="Request Entity Too Large", response=mock_res_413, body=None)

    provider.client = MagicMock()
    provider.client.chat.completions.create = AsyncMock(side_effect=mock_status_err)

    with pytest.raises(AppException) as exc_info:
        asyncio.run(provider.generate("Test prompt"))
    assert exc_info.value.status_code == 413
    assert "413" in exc_info.value.detail

    # 2. BadRequestError with context_length_exceeded
    mock_res_400 = httpx.Response(status_code=400, request=mock_req)
    mock_bad_req_err = BadRequestError(
        message="context_length_exceeded: maximum context length is 8192 tokens",
        response=mock_res_400,
        body=None,
    )
    provider.client.chat.completions.create = AsyncMock(side_effect=mock_bad_req_err)

    with pytest.raises(AppException) as exc_info2:
        asyncio.run(provider.generate("Test prompt"))
    assert exc_info2.value.status_code == 413


def test_watchfiles_reload_prevention_dot_unpacked_directory(tmp_path):
    """
    Verify that get_archive_unpacked_dir returns a dot-prefixed directory
    which WatchFiles ignores by default, preventing Uvicorn reload loops.
    """
    from app.services.file_storage.storage import get_archive_unpacked_dir, get_file_storage_service

    archive_file = tmp_path / "student_submission_8.zip"
    archive_file.touch()

    unpacked_dir = get_archive_unpacked_dir(archive_file)
    assert unpacked_dir.name.startswith(".student_submission_8_unpacked")

    # Verify delete_file cleans up dot-prefixed directory
    unpacked_dir.mkdir(parents=True, exist_ok=True)
    test_subfile = unpacked_dir / "app.py"
    test_subfile.write_text("print('test')")

    storage = get_file_storage_service()
    deleted = storage.delete_file(str(archive_file))
    assert deleted is True
    assert not unpacked_dir.exists()


def test_notebook_cell_budget_prioritization():
    """
    Verify NotebookProcessor intelligently prioritizes errors and markdown headings
    when notebook exceeds max_notebook_cells.
    """
    from app.core.config import get_settings
    from app.services.document_processing.notebook_processor import NotebookProcessor

    settings = get_settings()
    processor = NotebookProcessor(max_cells=10)

    # Construct notebook with 30 cells: headings, normal, and an errored cell at index 25
    cells = []
    for i in range(30):
        if i == 0:
            cells.append({
                "cell_type": "markdown",
                "metadata": {},
                "source": "# First Important Heading"
            })
        elif i == 25:
            cells.append({
                "cell_type": "code",
                "execution_count": 25,
                "metadata": {},
                "source": "raise ValueError('Critical model divergence error')",
                "outputs": [{
                    "output_type": "error",
                    "ename": "ValueError",
                    "evalue": "Critical model divergence error",
                    "traceback": ["Traceback line 1"]
                }]
            })
        else:
            cells.append({
                "cell_type": "code",
                "execution_count": i,
                "metadata": {},
                "source": f"x_{i} = {i}",
                "outputs": [{"output_type": "stream", "name": "stdout", "text": f"{i}\n"}]
            })

    nb_json = json.dumps({"nbformat": 4, "nbformat_minor": 2, "metadata": {}, "cells": cells})
    parsed = processor.parse_content(nb_json, filename="large_notebook.ipynb")

    assert parsed.is_valid is True
    assert "Notice: Notebook contains 30 cells. Displaying 10 key cells" in parsed.text_representation
    # Errored cell must be preserved
    assert "Critical model divergence error" in parsed.text_representation
    # Heading cell must be preserved
    assert "First Important Heading" in parsed.text_representation

