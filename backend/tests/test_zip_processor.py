"""
Tests for safe ZIP inspection, extraction, Zip Slip prevention, and resource limits.
"""

import io
from pathlib import Path
import zipfile
import pytest
from app.core.exceptions import AppException, FileTooLargeError
from app.services.document_processing.zip_processor import (
    ZipProcessor,
    get_zip_processor,
)


def create_in_memory_zip(file_dict: dict) -> bytes:
    """Helper to construct in-memory ZIP archives."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path, content in file_dict.items():
            if isinstance(content, str):
                zf.writestr(path, content.encode("utf-8"))
            else:
                zf.writestr(path, content)
    return buf.getvalue()


def test_safe_zip_extraction(tmp_path):
    project_files = {
        "src/main.py": "def main():\n    print('Hello World')\n\nif __name__ == '__main__':\n    main()\n",
        "src/utils.py": "def add(a, b):\n    return a + b\n",
        "tests/test_main.py": "from src.utils import add\n\ndef test_add():\n    assert add(1, 2) == 3\n",
        "README.md": "# Project Title\nThis project implements a sequence classifier.\n",
        "requirements.txt": "numpy>=1.20\ntensorflow>=2.10\n",
        "data/sample.csv": "id,feature_1,feature_2,label\n1,0.5,1.2,1\n2,0.1,0.8,0\n3,0.9,1.5,1\n",
    }
    zip_bytes = create_in_memory_zip(project_files)
    zip_path = tmp_path / "project.zip"
    zip_path.write_bytes(zip_bytes)

    target_dir = tmp_path / "extracted_project"

    processor = get_zip_processor()
    manifest = processor.inspect_and_extract(zip_path, target_dir)

    assert manifest.total_files == 6
    assert manifest.has_readme is True
    assert manifest.has_tests is True
    assert manifest.has_manifest is True
    assert manifest.category_counts.get("source", 0) == 2
    assert manifest.category_counts.get("test", 0) == 1
    assert manifest.category_counts.get("doc", 0) == 1
    assert manifest.category_counts.get("manifest", 0) == 1
    assert manifest.category_counts.get("data", 0) == 1

    # Check evidence generation
    evidence = processor.extract_project_evidence(manifest, archive_name="project.zip")
    assert "MULTI-FILE PROJECT ARCHIVE" in evidence
    assert "src/main.py" in evidence
    assert "tests/test_main.py" in evidence
    assert "README.md" in evidence
    assert "data/sample.csv" in evidence


def test_zip_filters_git_cache_and_venv(tmp_path):
    files = {
        "src/model.py": "import torch\n",
        ".git/HEAD": "ref: refs/heads/main\n",
        "__pycache__/model.cpython-310.pyc": b"\x00\x01\x02\x03",
        ".venv/pyvenv.cfg": "home = /usr/bin\n",
        "node_modules/package.json": "{}\n",
    }
    zip_bytes = create_in_memory_zip(files)
    zip_path = tmp_path / "filtered.zip"
    zip_path.write_bytes(zip_bytes)
    target_dir = tmp_path / "filtered_project"

    processor = get_zip_processor()
    manifest = processor.inspect_and_extract(zip_path, target_dir)

    # Only src/model.py should be extracted
    assert manifest.total_files == 1
    assert manifest.file_entries[0].rel_path == "src/model.py"
    assert not (target_dir / ".git").exists()
    assert not (target_dir / "__pycache__").exists()
    assert not (target_dir / ".venv").exists()
    assert not (target_dir / "node_modules").exists()


def test_zip_slip_relative_path_traversal_rejected(tmp_path):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("../../evil.py", "import os; os.system('malicious')")
    zip_bytes = buf.getvalue()
    zip_path = tmp_path / "slip.zip"
    zip_path.write_bytes(zip_bytes)

    target_dir = tmp_path / "slip_test"
    processor = get_zip_processor()
    with pytest.raises(AppException, match="Illegal archive path traversal"):
        processor.inspect_and_extract(zip_path, target_dir)


def test_zip_slip_absolute_path_rejected(tmp_path):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("/etc/passwd", "root:x:0:0::/root:/bin/bash")
    zip_bytes = buf.getvalue()
    zip_path = tmp_path / "abs.zip"
    zip_path.write_bytes(zip_bytes)

    target_dir = tmp_path / "abs_test"
    processor = get_zip_processor()
    with pytest.raises(AppException, match="Illegal archive path traversal"):
        processor.inspect_and_extract(zip_path, target_dir)


def test_zip_file_count_limit_rejected(tmp_path):
    files = {f"file_{i}.txt": f"Content {i}" for i in range(10)}
    zip_bytes = create_in_memory_zip(files)
    zip_path = tmp_path / "limit.zip"
    zip_path.write_bytes(zip_bytes)

    target_dir = tmp_path / "limit_test"
    processor = ZipProcessor(max_file_count=5)
    with pytest.raises(AppException, match="contains too many files"):
        processor.inspect_and_extract(zip_path, target_dir)


def test_zip_extracted_size_limit_rejected(tmp_path):
    # Use uncompressible random bytes so compression ratio check does not trigger before size limit
    import os
    large_content = os.urandom(2 * 1024 * 1024)
    zip_bytes = create_in_memory_zip({"large.bin": large_content})
    zip_path = tmp_path / "size.zip"
    zip_path.write_bytes(zip_bytes)

    target_dir = tmp_path / "size_test"
    processor = ZipProcessor(max_extracted_mb=1)
    with pytest.raises(FileTooLargeError):
        processor.inspect_and_extract(zip_path, target_dir)
