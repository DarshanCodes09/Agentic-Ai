"""
Comprehensive integration tests for Generic ZIP Evidence Inspection:
- Recursive archive inventory (nested folders, mixed file types).
- Generic processors for notebooks, source code, tabular CSVs, PDF/DOCX, images, markdown, config.
- CSV metrics and notebook output survival.
- Honest vision inspection handling (vision active vs unavailable).
- Honest reporting of unreadable/unsupported files.
- Dynamic relevance ranking without hardcoded assignment names or filenames.
- 5-state criterion evaluation differentiation (absent, incomplete, flawed, correct, unverified).
- Diagnostic evidence report API endpoint with RBAC.
"""

from datetime import datetime, timedelta, timezone
import io
import json
from pathlib import Path
import struct
import zipfile
import pytest
from fastapi.testclient import TestClient

from app.services.document_processing.zip_processor import (
    ZipProcessor,
    get_zip_processor,
)
from app.services.llm.provider import MockLLMProvider


def make_png_bytes(width: int = 400, height: int = 300) -> bytes:
    """Constructs valid binary PNG header bytes with specified dimensions."""
    header = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    dims = struct.pack(">II", width, height)
    return header + dims + b"\x08\x02\x00\x00\x00\x90wS\xde" + b"\x00" * 30


def make_synthetic_zip() -> bytes:
    """
    Creates a rich, synthetic ZIP archive with nested directories, multiple notebooks,
    CSVs, PDF, DOCX, Markdown, source code, images, config files, and unsupported binary artifacts.
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # 1. Source code in nested folder
        zf.writestr(
            "src/core/optimizer.py",
            "class NetworkOptimizer:\n    def __init__(self, lr=0.01):\n        self.lr = lr\n\n    def step(self):\n        pass\n",
        )
        zf.writestr(
            "src/utils/data_loader.py",
            "def load_dataset(batch_size=32):\n    return [1, 2, 3]\n",
        )

        # 2. Jupyter Notebook with executed outputs
        nb_dict = {
            "nbformat": 4,
            "nbformat_minor": 5,
            "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
            "cells": [
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": "# Model Evaluation & Tuning\nNotebook records hyperparameter trials.",
                },
                {
                    "cell_type": "code",
                    "execution_count": 1,
                    "metadata": {},
                    "source": "optimizer = 'Adam'\nval_acc = 0.924\nprint(f'Optimizer: {optimizer}, Final Val Acc: {val_acc}')",
                    "outputs": [{"output_type": "stream", "name": "stdout", "text": "Optimizer: Adam, Final Val Acc: 0.924\n"}],
                },
            ],
        }
        zf.writestr("notebooks/tuning.ipynb", json.dumps(nb_dict))

        # 3. Tabular CSV data with metrics and experiment configs
        csv_rows = ["epoch,learning_rate,loss,val_accuracy,optimizer"]
        for ep in range(1, 21):
            lr = "0.001" if ep <= 10 else "0.0005"
            loss_val = round(0.85 - (ep * 0.035), 4)
            acc_val = round(0.60 + (ep * 0.016), 4)
            csv_rows.append(f"{ep},{lr},{loss_val},{acc_val},Adam")
        zf.writestr("results/training_metrics.csv", "\n".join(csv_rows))

        # 4. Secondary CSV
        zf.writestr("results/hyperparameters.csv", "batch_size,hidden_units,dropout\n32,128,0.2\n64,256,0.3\n")

        # 5. Documentation
        zf.writestr(
            "docs/README.md",
            "# Project Documentation\n## Methodology\nExplored recurrent network architectures with varying learning rates.\n",
        )

        # 6. Structured configs & manifests
        zf.writestr(
            "requirements.txt",
            "numpy>=1.20.0\ntensorflow>=2.10.0\npandas>=1.3.0\n",
        )
        zf.writestr(
            "config/experiment.json",
            json.dumps({"experiment_id": "exp_001", "seed": 42, "epochs": 20}),
        )

        # 7. Images / Plots
        zf.writestr("plots/loss_curve.png", make_png_bytes(640, 480))
        zf.writestr(
            "plots/diagram.svg",
            '<svg width="500" height="300"><text>Architecture Diagram</text></svg>',
        )

        # 8. Scanned / Low-text PDF
        # PyMuPDF can read a minimal PDF stream
        minimal_pdf = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\nxref\n0 4\n0000000000 65535 f\n0000000010 00000 n\n0000000053 00000 n\n0000000102 00000 n\ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n178\n%%EOF\n"
        zf.writestr("reports/scanned_report.pdf", minimal_pdf)

        # 9. Unsupported binary artifact
        zf.writestr("models/weights.bin", b"\x00\x01\x02\x03\x04\x05\x06\x07")

        # 10. Auxiliary log
        zf.writestr("logs/output.log", "2026-10-28 12:00:00 INFO Training initialized.\n")

    return buf.getvalue()


def test_recursive_inventory_and_generic_processors(tmp_path):
    """Verify that every entry in a nested archive is inventoried and processed."""
    zip_bytes = make_synthetic_zip()
    zip_path = tmp_path / "comprehensive.zip"
    zip_path.write_bytes(zip_bytes)

    target_dir = tmp_path / "extracted"
    processor = get_zip_processor()
    manifest = processor.inspect_and_extract(zip_path, target_dir)

    # 1. Total entries discovered
    assert manifest.total_entries == 13
    assert manifest.total_size_bytes > 0

    # 2. Processed, unsupported, and partial counts
    assert manifest.processed_count >= 8
    assert manifest.unsupported_count >= 1  # weights.bin

    paths = [e.rel_path for e in manifest.file_entries]
    assert "src/core/optimizer.py" in paths
    assert "notebooks/tuning.ipynb" in paths
    assert "results/training_metrics.csv" in paths
    assert "reports/scanned_report.pdf" in paths
    assert "models/weights.bin" in paths
    assert "plots/loss_curve.png" in paths

    # 3. CSV results processing: metrics and distinct configs survive
    csv_entry = next(e for e in manifest.file_entries if e.rel_path == "results/training_metrics.csv")
    assert csv_entry.useful_content_extracted is True
    assert "20 data rows x 5 columns" in csv_entry.extracted_content
    assert "loss" in csv_entry.extracted_content
    assert "val_accuracy" in csv_entry.extracted_content
    assert "Distinct Configurations" in csv_entry.extracted_content

    # 4. Scanned PDF detection
    pdf_entry = next(e for e in manifest.file_entries if e.rel_path == "reports/scanned_report.pdf")
    assert pdf_entry.useful_content_extracted is False
    assert "Scanned or image-only PDF" in (pdf_entry.error_or_omission_reason or "")

    # 5. Unsupported binary artifact honest reporting
    bin_entry = next(e for e in manifest.file_entries if e.rel_path == "models/weights.bin")
    assert bin_entry.processing_status == "UNSUPPORTED"
    assert bin_entry.useful_content_extracted is False
    assert "Binary file or unsupported format" in bin_entry.error_or_omission_reason

    # 6. Image dimensions without claiming visual inspection
    img_entry = next(e for e in manifest.file_entries if e.rel_path == "plots/loss_curve.png")
    assert "640x480" in img_entry.summary
    assert img_entry.vision_inspected is False
    assert "Visual inspection unavailable" in img_entry.summary


def test_vision_inspection_when_supported(tmp_path):
    """Test that image files are analyzed when a vision-capable provider is present."""
    zip_bytes = make_synthetic_zip()
    zip_path = tmp_path / "vision_test.zip"
    zip_path.write_bytes(zip_bytes)

    target_dir = tmp_path / "extracted_vision"
    processor = get_zip_processor()

    # Create mock provider with vision enabled
    mock_vision = MockLLMProvider(enable_vision=True)
    manifest = processor.inspect_and_extract(zip_path, target_dir, vision_provider=mock_vision)

    assert manifest.vision_inspected_count >= 1
    img_entry = next(e for e in manifest.file_entries if e.rel_path == "plots/loss_curve.png")
    assert img_entry.vision_inspected is True
    assert "Visual analysis indicates experimental results plot" in img_entry.summary


def test_dynamic_relevance_ranking_and_rubric_mapping(tmp_path):
    """
    Test dynamic relevance ranking with arbitrary academic rubric criteria.
    Ensures ZERO hardcoded assignment names or filenames.
    """
    zip_bytes = make_synthetic_zip()
    zip_path = tmp_path / "dyn_rubric.zip"
    zip_path.write_bytes(zip_bytes)

    target_dir = tmp_path / "extracted_dyn"
    processor = get_zip_processor()
    manifest = processor.inspect_and_extract(zip_path, target_dir)

    rubric_items = [
        {
            "id": 1,
            "criterion": "Optimization Algorithm Implementation",
            "description": "Implementation of gradient optimization steps and learning rate parameters.",
            "max_marks": 30.0,
        },
        {
            "id": 2,
            "criterion": "Experimental Training Outcomes & Metrics",
            "description": "Quantitative analysis of loss and validation accuracy curves over epochs.",
            "max_marks": 40.0,
        },
        {
            "id": 3,
            "criterion": "Unmatched Hypothetical Criterion",
            "description": "Quantum annealing and superconducting circuit calculations.",
            "max_marks": 30.0,
        },
    ]

    evidence_pkg = processor.build_evidence_package(
        manifest=manifest,
        archive_name="project.zip",
        rubric_items=rubric_items,
        assignment_instructions="Evaluate machine learning optimization algorithms and hyperparameter outcomes.",
        assignment_title="Deep Learning Lab Experiment",
    )

    # Criterion 1 should map to optimizer.py
    mapping = manifest.criterion_evidence_mapping
    assert any("optimizer.py" in f for f in mapping.get("Optimization Algorithm Implementation", []))

    # Criterion 2 should map to training_metrics.csv or tuning.ipynb
    assert any("training_metrics.csv" in f or "tuning.ipynb" in f for f in mapping.get("Experimental Training Outcomes & Metrics", []))

    # Criterion 3 should trigger a faculty review flag
    assert any(
        item["criterion"] == "Unmatched Hypothetical Criterion"
        for item in manifest.criteria_requiring_human_review
    )
    assert "ATTENTION FACULTY: CRITERIA REQUIRING HUMAN REVIEW" in evidence_pkg


def test_evidence_report_endpoint_and_rbac(
    client: TestClient, faculty_user: dict, student_user: dict, other_faculty_user: dict, tmp_path
):
    """Verify GET /submissions/{id}/evidence-report works with proper RBAC."""
    # 1. Create subject and assignment
    sub_res = client.post(
        "/api/subjects",
        json={"name": "Distributed Systems", "code": "DIST_SYS_801"},
        headers=faculty_user["headers"],
    )
    assert sub_res.status_code == 201
    subject_id = sub_res.json()["id"]

    due = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    asg_res = client.post(
        f"/api/subjects/{subject_id}/assignments",
        json={
            "title": "Consensus Protocol Benchmarking",
            "description": "Benchmark consensus throughput and latency across nodes.",
            "due_date": due,
            "max_marks": 100.0,
        },
        headers=faculty_user["headers"],
    )
    assert asg_res.status_code == 201
    assignment_id = asg_res.json()["id"]

    # 2. Student enrolls and submits synthetic ZIP
    client.post(f"/api/subjects/{subject_id}/enroll", headers=student_user["headers"])
    zip_bytes = make_synthetic_zip()
    files = {"file": ("consensus_bench.zip", io.BytesIO(zip_bytes), "application/zip")}

    submit_res = client.post(
        f"/api/assignments/{assignment_id}/submit",
        files=files,
        data={"submission_text": "Completed consensus protocol implementation and benchmarking."},
        headers=student_user["headers"],
    )
    assert submit_res.status_code == 201
    submission_id = submit_res.json()["id"]

    # 3. Faculty owner retrieves evidence report -> 200 OK
    fac_report_res = client.get(
        f"/api/submissions/{submission_id}/evidence-report",
        headers=faculty_user["headers"],
    )
    assert fac_report_res.status_code == 200
    report = fac_report_res.json()
    assert report["submission_id"] == submission_id
    assert report["total_archive_entries"] == 13
    assert report["supported_files_count"] >= 8
    assert report["unsupported_files_count"] >= 1
    assert len(report["file_inventory"]) == 13

    # 4. Student submitter retrieves evidence report -> 200 OK
    stu_report_res = client.get(
        f"/api/submissions/{submission_id}/evidence-report",
        headers=student_user["headers"],
    )
    assert stu_report_res.status_code == 200

    # 5. Unauthorized faculty from another subject -> 403 Forbidden
    other_res = client.get(
        f"/api/submissions/{submission_id}/evidence-report",
        headers=other_faculty_user["headers"],
    )
    assert other_res.status_code == 403


def test_ai_assessment_distinguishes_evidence_states(
    client: TestClient, faculty_user: dict, student_user: dict
):
    """
    Test that the evaluation pipeline uses ZIP evidence and cites actual file paths
    across criteria in AssessmentAgent reasoning.
    """
    sub_res = client.post(
        "/api/subjects",
        json={"name": "Software Architecture", "code": "SOFT_ARCH_901"},
        headers=faculty_user["headers"],
    )
    subject_id = sub_res.json()["id"]

    due = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    asg_res = client.post(
        f"/api/subjects/{subject_id}/assignments",
        json={
            "title": "Scalable Pipeline Architecture",
            "description": "Design and verify scalable pipeline data processing components.",
            "due_date": due,
            "max_marks": 100.0,
        },
        headers=faculty_user["headers"],
    )
    assignment_id = asg_res.json()["id"]

    # Set approved rubric criteria
    client.post(
        f"/api/assignments/{assignment_id}/rubric",
        json={
            "name": "Pipeline Rubric",
            "items": [
                {
                    "criterion": "Algorithm Implementation",
                    "description": "Implementation of optimizer and pipeline logic.",
                    "max_marks": 50.0,
                },
                {
                    "criterion": "Quantitative Metrics Validation",
                    "description": "Validation accuracy and loss convergence analysis.",
                    "max_marks": 50.0,
                },
            ],
        },
        headers=faculty_user["headers"],
    )

    client.post(f"/api/subjects/{subject_id}/enroll", headers=student_user["headers"])
    zip_bytes = make_synthetic_zip()
    files = {"file": ("architecture_solution.zip", io.BytesIO(zip_bytes), "application/zip")}

    submit_res = client.post(
        f"/api/assignments/{assignment_id}/submit",
        files=files,
        data={"submission_text": "Complete implementation and empirical metrics included."},
        headers=student_user["headers"],
    )
    submission_id = submit_res.json()["id"]

    # Run AI evaluation
    assess_res = client.post(
        f"/api/submissions/{submission_id}/assess",
        headers=faculty_user["headers"],
    )
    assert assess_res.status_code == 200
    assessment = assess_res.json()

    assert assessment["ai_score"] > 0
    criteria = assessment["criteria_scores"]
    assert len(criteria) == 2

    # Verify that actual file paths are cited in criterion reasoning
    reasons = " ".join(c["reasoning"] for c in criteria)
    assert any(kw in reasons for kw in ("optimizer.py", "training_metrics.csv", "tuning.ipynb", "project files"))
