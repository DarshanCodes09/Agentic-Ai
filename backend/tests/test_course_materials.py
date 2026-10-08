"""
Tests for Course Material upload, management, processing pipeline, and RAG search — Phase 3.
"""

import io
from pathlib import Path

import docx
import fitz
import pytest
from fastapi.testclient import TestClient


def create_sample_pdf_bytes(text: str = "Academic course notes on Software Engineering.") -> io.BytesIO:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 72), text)
    pdf_bytes = doc.tobytes()
    doc.close()
    return io.BytesIO(pdf_bytes)


def create_sample_docx_bytes(text: str = "Academic syllabus and module lecture notes.") -> io.BytesIO:
    doc = docx.Document()
    doc.add_paragraph(text)
    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf


def create_subject(client: TestClient, faculty_headers: dict, code: str) -> int:
    res = client.post(
        "/api/subjects",
        json={"name": "Test Subject", "code": code},
        headers=faculty_headers,
    )
    return res.json()["id"]


# ---------------------------------------------------------------------------
# Upload & Role Access Tests
# ---------------------------------------------------------------------------

def test_faculty_can_upload_pdf_material(client: TestClient, faculty_user: dict):
    subject_id = create_subject(client, faculty_user["headers"], "MAT_SUB1")
    pdf_file = create_sample_pdf_bytes("Lecture 1: Introduction to Data Structures and Trees.")

    files = {"file": ("lecture1.pdf", pdf_file, "application/pdf")}
    data = {"title": "Lecture 1: Trees"}

    res = client.post(
        f"/api/subjects/{subject_id}/materials",
        data=data,
        files=files,
        headers=faculty_user["headers"],
    )
    assert res.status_code == 201
    body = res.json()
    assert body["title"] == "Lecture 1: Trees"
    assert body["original_filename"] == "lecture1.pdf"
    assert body["file_type"] == "pdf"
    assert body["subject_id"] == subject_id
    assert body["processing_status"] in ["UPLOADED", "PROCESSED"]


def test_faculty_can_upload_docx_material(client: TestClient, faculty_user: dict):
    subject_id = create_subject(client, faculty_user["headers"], "MAT_SUB2")
    docx_file = create_sample_docx_bytes("Module 2: Object-Oriented Design Patterns.")

    files = {
        "file": (
            "module2.docx",
            docx_file,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    }
    data = {"title": "Module 2: Patterns"}

    res = client.post(
        f"/api/subjects/{subject_id}/materials",
        data=data,
        files=files,
        headers=faculty_user["headers"],
    )
    assert res.status_code == 201
    assert res.json()["file_type"] == "docx"
    assert res.json()["processing_status"] in ["UPLOADED", "PROCESSED"]


def test_faculty_cannot_upload_to_other_faculty_subject(
    client: TestClient, faculty_user: dict, other_faculty_user: dict
):
    subject_id = create_subject(client, faculty_user["headers"], "MAT_SUB3")
    pdf_file = create_sample_pdf_bytes()

    files = {"file": ("rogue.pdf", pdf_file, "application/pdf")}
    res = client.post(
        f"/api/subjects/{subject_id}/materials",
        files=files,
        headers=other_faculty_user["headers"],
    )
    assert res.status_code == 403


def test_student_cannot_upload_material(
    client: TestClient, faculty_user: dict, student_user: dict
):
    subject_id = create_subject(client, faculty_user["headers"], "MAT_SUB4")
    pdf_file = create_sample_pdf_bytes()

    files = {"file": ("student.pdf", pdf_file, "application/pdf")}
    res = client.post(
        f"/api/subjects/{subject_id}/materials",
        files=files,
        headers=student_user["headers"],
    )
    assert res.status_code == 403


def test_invalid_file_type_rejected(client: TestClient, faculty_user: dict):
    subject_id = create_subject(client, faculty_user["headers"], "MAT_SUB5")
    bad_file = io.BytesIO(b"echo 'malicious script'")

    files = {"file": ("script.sh", bad_file, "text/x-shellscript")}
    res = client.post(
        f"/api/subjects/{subject_id}/materials",
        files=files,
        headers=faculty_user["headers"],
    )
    assert res.status_code == 422


# ---------------------------------------------------------------------------
# Listing & Viewing Tests
# ---------------------------------------------------------------------------

def test_enrolled_student_can_list_and_view_materials(
    client: TestClient, faculty_user: dict, student_user: dict
):
    subject_id = create_subject(client, faculty_user["headers"], "MAT_SUB6")
    pdf_file = create_sample_pdf_bytes("Syllabus details for the semester.")

    # Upload
    upload_res = client.post(
        f"/api/subjects/{subject_id}/materials",
        files={"file": ("syllabus.pdf", pdf_file, "application/pdf")},
        data={"title": "Syllabus"},
        headers=faculty_user["headers"],
    )
    material_id = upload_res.json()["id"]

    # Student enrolls
    client.post(f"/api/subjects/{subject_id}/enroll", headers=student_user["headers"])

    # List materials
    list_res = client.get(f"/api/subjects/{subject_id}/materials", headers=student_user["headers"])
    assert list_res.status_code == 200
    materials = list_res.json()
    assert len(materials) == 1
    assert materials[0]["id"] == material_id

    # View single material
    get_res = client.get(f"/api/materials/{material_id}", headers=student_user["headers"])
    assert get_res.status_code == 200
    assert get_res.json()["title"] == "Syllabus"


def test_unenrolled_student_cannot_access_materials(
    client: TestClient, faculty_user: dict, student_user: dict
):
    subject_id = create_subject(client, faculty_user["headers"], "MAT_SUB7")
    pdf_file = create_sample_pdf_bytes()

    upload_res = client.post(
        f"/api/subjects/{subject_id}/materials",
        files={"file": ("notes.pdf", pdf_file, "application/pdf")},
        headers=faculty_user["headers"],
    )
    mat_id = upload_res.json()["id"]

    # Unenrolled student tries listing
    list_res = client.get(f"/api/subjects/{subject_id}/materials", headers=student_user["headers"])
    assert list_res.status_code == 403

    # Unenrolled student tries getting by ID
    get_res = client.get(f"/api/materials/{mat_id}", headers=student_user["headers"])
    assert get_res.status_code == 403


# ---------------------------------------------------------------------------
# Deletion Tests
# ---------------------------------------------------------------------------

def test_faculty_can_delete_own_material(client: TestClient, faculty_user: dict):
    subject_id = create_subject(client, faculty_user["headers"], "MAT_SUB8")
    pdf_file = create_sample_pdf_bytes()

    upload_res = client.post(
        f"/api/subjects/{subject_id}/materials",
        files={"file": ("to_delete.pdf", pdf_file, "application/pdf")},
        headers=faculty_user["headers"],
    )
    mat_id = upload_res.json()["id"]

    del_res = client.delete(f"/api/materials/{mat_id}", headers=faculty_user["headers"])
    assert del_res.status_code == 204

    # Confirm 404 after deletion
    get_res = client.get(f"/api/materials/{mat_id}", headers=faculty_user["headers"])
    assert get_res.status_code == 404


def test_faculty_cannot_delete_other_faculty_material(
    client: TestClient, faculty_user: dict, other_faculty_user: dict
):
    subject_id = create_subject(client, faculty_user["headers"], "MAT_SUB9")
    pdf_file = create_sample_pdf_bytes()

    upload_res = client.post(
        f"/api/subjects/{subject_id}/materials",
        files={"file": ("protected.pdf", pdf_file, "application/pdf")},
        headers=faculty_user["headers"],
    )
    mat_id = upload_res.json()["id"]

    del_res = client.delete(f"/api/materials/{mat_id}", headers=other_faculty_user["headers"])
    assert del_res.status_code == 403


# ---------------------------------------------------------------------------
# Processing Pipeline & Semantic Search Tests
# ---------------------------------------------------------------------------

def test_manual_processing_trigger_and_semantic_search(
    client: TestClient, faculty_user: dict, student_user: dict
):
    subject_id = create_subject(client, faculty_user["headers"], "MAT_SUB10")
    pdf_content = (
        "Operating System Kernels and Monolithic vs Microkernel Architectures. "
        "A microkernel structures the operating system by removing all nonessential components "
        "from the kernel and implementing them as system and user-level programs."
    )
    pdf_file = create_sample_pdf_bytes(pdf_content)

    upload_res = client.post(
        f"/api/subjects/{subject_id}/materials",
        files={"file": ("kernel_architectures.pdf", pdf_file, "application/pdf")},
        data={"title": "Kernel Architectures"},
        headers=faculty_user["headers"],
    )
    assert upload_res.status_code == 201
    mat_id = upload_res.json()["id"]

    # Trigger manual process
    process_res = client.post(f"/api/materials/{mat_id}/process", headers=faculty_user["headers"])
    assert process_res.status_code == 200
    assert process_res.json()["processing_status"] == "PROCESSED"

    # Enroll student and perform semantic search
    client.post(f"/api/subjects/{subject_id}/enroll", headers=student_user["headers"])

    search_payload = {
        "query": "microkernel architecture nonessential components",
        "top_k": 3,
    }
    search_res = client.post(
        f"/api/subjects/{subject_id}/materials/search",
        json=search_payload,
        headers=student_user["headers"],
    )
    assert search_res.status_code == 200
    results = search_res.json()
    assert len(results) > 0
    assert "microkernel" in results[0]["chunk_text"].lower()
