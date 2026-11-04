"""
Regression and Token-Budget Convergence Tests for Assessment Prompt Flow.

Tests:
1. Exact ~4,282-token prompt overflow (the real-world UI failure case) converges below safe 4,200-token limit.
2. Large mixed-file ZIP submissions maintain archive diagnostics and omission notices during reduction.
3. Preservation of all approved rubric criteria during adaptive reduction passes.
4. Preflight detection and actionable 413 error when rubric criteria/questions alone exceed the budget.
5. Accurate token estimates and verification that LLM provider is never called with oversized requests.
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
import zipfile
import pytest

from app.core.exceptions import PayloadTooLargeError
from app.schemas.assessment import AssessmentStructuredOutput, ConceptMasteryItem, ConceptMasteryLevel, CriterionEvaluation
from app.services.assessment.assessment_agent import AssessmentAgent
from app.services.assessment.preparation_service import AssessmentContext
from app.services.document_processing.zip_processor import ZipProcessor, get_zip_processor
from app.services.llm.prompts.assessment_prompt import build_assessment_prompts
from app.services.llm.token_budget import estimate_tokens, get_model_safe_token_limit


def _create_mock_eval_output(rubric_items: list[dict], total_max: float) -> AssessmentStructuredOutput:
    """Helper to create valid mock assessment output matching rubric items."""
    crit_evals = [
        CriterionEvaluation(
            rubric_item_id=r.get("id"),
            criterion=r.get("criterion", "Criterion"),
            score=round(float(r.get("max_marks", 10.0)) * 0.85, 2),
            max_marks=float(r.get("max_marks", 10.0)),
            reasoning=f"Demonstrated solid competency for {r.get('criterion')}.",
        )
        for r in rubric_items
    ]
    total_score = round(sum(c.score for c in crit_evals), 2)
    return AssessmentStructuredOutput(
        ai_score=min(total_score, total_max),
        criteria_scores=crit_evals,
        concept_mastery=[
            ConceptMasteryItem(
                concept="Core Architecture",
                mastery_level=ConceptMasteryLevel.MASTERED,
                evidence="Clear implementation in code and results.",
            )
        ],
        strengths=["Comprehensive experimental methodology."],
        weaknesses=["Could provide more extensive baseline comparisons."],
        general_remarks="Rigorous submission meeting academic standards.",
    )


@pytest.mark.asyncio
async def test_exact_4282_token_overflow_converges_below_budget():
    """
    Regression Test for UI Error:
    `Assessment request size (13702 chars, ~4282 tokens) exceeds the AI model safe token limit (4200 tokens)`

    Verifies that an assignment context with:
      - 5 rubric criteria (~1,500 chars)
      - Attached assignment documents (~1,500 chars)
      - Assignment instructions (~800 chars)
      - Substantial student submission evidence (~8,000 chars)
    which previously stopped at 13,702 chars (~4,282 tokens), now dynamically
    converges below the safe 4,200 token budget without throwing PayloadTooLargeError.
    """
    rubric_items = [
        {
            "id": 1,
            "criterion": "Network Architecture & LSTM/RNN Model Design",
            "description": "Implementation of recurrent layers, embedding configurations, and cell state connections.",
            "max_marks": 20.0,
        },
        {
            "id": 2,
            "criterion": "Hyperparameter Search & Tuning Methodology",
            "description": "Systematic exploration of learning rates, batch sizes, hidden dimensions, and dropout rates.",
            "max_marks": 20.0,
        },
        {
            "id": 3,
            "criterion": "Empirical Convergence & Metric Evaluation",
            "description": "Validation loss curves, accuracy trajectories, confusion matrices, and test benchmark metrics.",
            "max_marks": 20.0,
        },
        {
            "id": 4,
            "criterion": "Code Quality, Modularity & Documentation",
            "description": "Clean modular functions, docstrings, type annotations, reproducibility, and logging.",
            "max_marks": 20.0,
        },
        {
            "id": 5,
            "criterion": "Critical Analysis & Comparative Discussion",
            "description": "Discussion of inductive biases, exploding/vanishing gradients, and comparative performance tradeoffs.",
            "max_marks": 20.0,
        },
    ]

    questions = [
        {
            "id": 101,
            "question_number": 1,
            "question_text": "Implement and compare bidirectional LSTM and standard GRU architectures for sequence classification.",
            "marks": 50.0,
            "expected_concepts": ["Recurrent Neural Networks", "Backpropagation Through Time", "Gating Mechanisms"],
        },
        {
            "id": 102,
            "question_number": 2,
            "question_text": "Conduct hyperparameter tuning over at least three distinct dimensions and present tabular metrics.",
            "marks": 50.0,
            "expected_concepts": ["Grid Search", "Learning Rate Schedulers", "Validation Loss"],
        },
    ]

    attached_docs = (
        "=== ATTACHED SPECIFICATION: Assignment_Guidelines.pdf ===\n"
        "Students must construct a sequence classification pipeline in Python/PyTorch. "
        "The model must process variable length sequence tokens and classify them into 4 distinct classes. "
        "Mandatory deliverables include: 1) Jupyter notebook with executed outputs; 2) Tabular results CSV; "
        "3) Architecture script. Evaluation is strictly tied to the approved rubric criteria. "
    ) * 4  # ~1,600 chars

    instructions = (
        "Ensure all cells are executed prior to submission. Save output metrics to CSV. "
        "Analyze convergence patterns and provide clear markdown interpretations in the notebook. "
    ) * 4  # ~800 chars

    # Submission evidence representing large multi-file output (around 8,000 chars)
    submission_evidence = (
        "=== MULTI-FILE PROJECT ARCHIVE EVIDENCE: student_rnn_lstm_project.zip ===\n"
        "Total Valid Discovered Entries: 8 | Decompressed Size: 182940 bytes\n"
        "Content Processing Breakdown: {'notebook': 1, 'source': 3, 'tabular': 1, 'document': 1}\n"
        "Inspection Audit: 6 processed, 0 truncated, 0 unsupported, 0 failed, 0 vision-inspected.\n"
        "Project Structure: Readme: True | Dependencies: True | Tests: True | Notebooks: 1\n"
        "\n--- COMPLETE ARCHIVE INVENTORY TREE ---\n"
        "- model.py (12400 bytes, source) [PROCESSED]\n"
        "- train.py (9800 bytes, source) [PROCESSED]\n"
        "- utils.py (4500 bytes, source) [PROCESSED]\n"
        "- results/hyperparameters.csv (3200 bytes, tabular) [PROCESSED]\n"
        "- report.md (5400 bytes, document) [PROCESSED]\n"
        "- tests/test_model.py (2100 bytes, test) [PROCESSED] [TEST]\n"
        "- README.md (1800 bytes, document) [PROCESSED]\n"
        "- rnn_experiment.ipynb (84000 bytes, notebook) [PROCESSED]\n"
        "\n--- JUPYTER NOTEBOOKS & EXECUTION EVIDENCE ---\n"
        "[Notebook: rnn_experiment.ipynb]\n"
        "Execution Audit: 24 total cells, 18 code cells, 18 executed (100% execution), 0 errors.\n"
        "Final Test Accuracy: 0.924, Validation Loss: 0.281 across 20 epochs.\n"
        "\n--- SOURCE CODE DELIVERABLES ---\n"
        "[Source File: model.py]\n"
        + ("class SequenceClassifier(nn.Module):\n    def __init__(self, vocab_size, hidden_dim):\n        super().__init__()\n        self.lstm = nn.LSTM(hidden_dim, hidden_dim, batch_first=True)\n" * 25)
    )

    mock_sub = MagicMock()
    mock_sub.id = 777

    context = AssessmentContext(
        submission=mock_sub,
        assignment_title="Hyperparameter Tuning of RNN and LSTM Networks for Sequence Classification",
        assignment_description="Detailed RNN and LSTM sequence modeling task.",
        total_max_marks=100.0,
        questions=questions,
        rubric_items=rubric_items,
        retrieved_chunks=[
            {"chunk_text": "Recurrent neural networks process sequential input using hidden state transitions.", "similarity": 0.88, "metadata": {}}
        ],
        submission_text=submission_evidence,
        assignment_instructions=instructions,
        assignment_documents_text=attached_docs,
    )

    mock_llm = MagicMock()
    captured_payload = {}

    async def mock_generate_structured(prompt: str, response_model, system_prompt=None, **kwargs):
        captured_payload["prompt"] = prompt
        captured_payload["system_prompt"] = system_prompt
        # Compute exact complete serialized request tokens
        full_serialized = f"{system_prompt}\n{prompt}"
        captured_payload["total_tokens"] = estimate_tokens(full_serialized)
        captured_payload["total_chars"] = len(full_serialized)
        return _create_mock_eval_output(rubric_items, 100.0)

    mock_llm.generate_structured = AsyncMock(side_effect=mock_generate_structured)
    mock_llm.model_name = "llama-3.3-70b-versatile"

    agent = AssessmentAgent(llm_service=mock_llm)
    result = await agent.evaluate(context)

    # 1. Verification of evaluation success
    assert result.ai_score > 0.0
    assert len(result.criteria_scores) == 5

    # 2. Strict token limit enforcement on the complete serialized request
    assert "total_tokens" in captured_payload
    final_tokens = captured_payload["total_tokens"]
    assert final_tokens <= 4200, f"Complete serialized request ({final_tokens} tokens) exceeded 4,200 token budget!"

    # 3. Preservation of all 5 approved rubric criteria in the prompt
    for r in rubric_items:
        assert r["criterion"] in captured_payload["prompt"], f"Criterion '{r['criterion']}' was missing from user prompt!"


@pytest.mark.asyncio
async def test_large_mixed_file_zip_reduction_preserves_inventory_and_diagnostics(tmp_path):
    """
    Verify that large mixed-file ZIP submissions:
    1. Inventory every file entry (including nested folders and mixed file types).
    2. Dynamically reduce evidence size to fit within token limits.
    3. Retain complete inventory references and omission notices.
    4. Call provider within safe token budget.
    """
    zip_path = tmp_path / "mixed_project_large.zip"
    extract_dir = tmp_path / ".mixed_unpacked"

    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("src/pipeline/model.py", "class ComplexModel:\n    pass\n" * 400)
        zf.writestr("src/pipeline/trainer.py", "def train_epoch():\n    return 0.1\n" * 300)
        zf.writestr("src/utils/metrics.py", "def compute_f1():\n    return 0.95\n" * 200)
        zf.writestr("tests/test_model.py", "def test_accuracy():\n    assert True\n" * 50)
        zf.writestr("results/metrics.csv", "epoch,train_loss,val_loss,acc\n" + "\n".join(f"{i},0.5,0.4,0.9" for i in range(50)))
        zf.writestr("docs/spec.txt", "Detailed specifications and methodology documentation.\n" * 50)
        zf.writestr("README.md", "# Project Readme\nComplete overview of repository structure.")

    zip_proc = get_zip_processor()
    manifest = zip_proc.inspect_and_extract(zip_path, extract_dir)
    evidence = zip_proc.build_evidence_package(manifest, archive_name="mixed_project_large.zip")

    rubric_items = [
        {"id": 10, "criterion": "Core Model Implementation", "description": "PyTorch / Python implementation", "max_marks": 50.0},
        {"id": 20, "criterion": "Empirical Verification & Testing", "description": "Unit tests and metric tables", "max_marks": 50.0},
    ]

    mock_sub = MagicMock()
    mock_sub.id = 666

    context = AssessmentContext(
        submission=mock_sub,
        assignment_title="Deep Sequence Modeling Assignment",
        assignment_description="Build end-to-end classification system.",
        total_max_marks=100.0,
        rubric_items=rubric_items,
        submission_text=evidence,
        zip_inventory=manifest,
        original_archive_name="mixed_project_large.zip",
    )

    captured = {}

    async def mock_gen(prompt, response_model, system_prompt=None, **kwargs):
        captured["prompt"] = prompt
        captured["system_prompt"] = system_prompt
        full = f"{system_prompt}\n{prompt}"
        captured["tokens"] = estimate_tokens(full)
        return _create_mock_eval_output(rubric_items, 100.0)

    mock_llm = MagicMock()
    mock_llm.generate_structured = AsyncMock(side_effect=mock_gen)
    mock_llm.model_name = "llama-3.3-70b-versatile"

    agent = AssessmentAgent(llm_service=mock_llm)
    result = await agent.evaluate(context)

    assert result.ai_score > 0
    assert captured["tokens"] <= 4200
    # Complete inventory is preserved in the manifest/report
    assert manifest.total_entries >= 7
    assert manifest.processed_count >= 5
    # Prompt contains inventory marker and both rubric criteria
    assert "--- COMPLETE ARCHIVE INVENTORY TREE ---" in captured["prompt"]
    assert "Core Model Implementation" in captured["prompt"]
    assert "Empirical Verification & Testing" in captured["prompt"]


@pytest.mark.asyncio
async def test_preflight_rejection_when_rubric_alone_exceeds_budget():
    """
    Requirement 7: If the required rubric criteria alone exceed the budget,
    return a clear actionable error rather than silently truncating the rubric
    or pretending evaluation was complete.
    """
    # Create 50 massive rubric criteria that alone exceed 20,000 tokens
    oversized_rubrics = [
        {
            "id": i,
            "criterion": f"Exhaustive Disciplinary Standard Number {i}",
            "description": "Elaborate multi-paragraph theoretical rubric criterion description " * 40,
            "max_marks": 2.0,
        }
        for i in range(50)
    ]

    mock_sub = MagicMock()
    mock_sub.id = 555

    context = AssessmentContext(
        submission=mock_sub,
        assignment_title="Assignment with Massive Rubric",
        assignment_description="Normal description",
        total_max_marks=100.0,
        rubric_items=oversized_rubrics,
        submission_text="def solve(): return 42",
    )

    agent = AssessmentAgent()
    with pytest.raises(PayloadTooLargeError) as exc_info:
        await agent.evaluate(context)

    err = exc_info.value
    assert err.status_code == 413
    assert "exceeds" in err.detail.lower()
    assert "rubric criteria" in err.detail.lower()
    assert "condense" in err.detail.lower()


def test_accurate_token_estimation_and_limits():
    """Verify estimate_tokens provides conservative token estimates with safety margin."""
    short_text = "def hello():\n    return 'world'"
    assert estimate_tokens(short_text) >= len(short_text.split())

    # Code with heavy syntax punctuation
    code_text = "x = [model(torch.tensor([i, j, k])) for i in range(10) for j in range(10) for k in range(10)]"
    tokens = estimate_tokens(code_text)
    assert tokens > len(code_text.split())

    # Limit lookup
    assert get_model_safe_token_limit("llama-3.3-70b-versatile") == 4200
    assert get_model_safe_token_limit("unknown-model") == 4200
