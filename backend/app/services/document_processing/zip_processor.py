"""
Generic, Safe ZIP Archive Inspector, Extractor, Content Processor,
and Dynamic Academic Evidence Builder.

Features:
  - Recursive inventory of every archive entry (including nested folders and mixed file types).
  - Strict security safeguards:
      * Zip Slip / path traversal rejection.
      * Symlink rejection.
      * Suspicious compression ratio (Zip bomb) rejection.
      * Configurable limits on archive size, file count, and uncompressed bytes.
      * Filtering of noise/build directories (.git, __pycache__, .venv, node_modules).
  - Generic safe content processors for:
      * Jupyter notebooks (.ipynb): Markdown, code cells, execution outputs, counts, error audits.
      * Source code (.py, .js, .ts, .java, .cpp, .c, .h, .cs, .go, .rs, etc.): syntax structure, line counts, bounded code.
      * Tabular/CSV (.csv, .tsv): dimensions, headers, numeric metric summaries (min/max/mean/final), distinct experiment configs, sample rows.
      * Documents (.pdf, .docx, .doc): extracted text, headings, sections, scanned/low-text detection (<50 chars).
      * Markdown & text (.md, .txt, .rst): sections, methodology, results, discussion.
      * Config & Manifests (.json, .yaml, .yml, .xml, .toml, requirements.txt, etc.): parameters, dependencies, structured keys.
      * Images (.png, .jpg, .jpeg, .webp, .svg): dimensions, format, optional vision model inspection, honest fallback when vision unavailable.
      * Other/unsupported: honest diagnostic reporting without pretending inspection occurred.
  - Multi-stage evaluation evidence assembly:
      1. Complete inventory.
      2. Safe content extraction.
      3. Searchable evidence index.
      4. Dynamic relevance ranking against rubric criteria and assignment instructions (Zero hardcoded subjects or filenames).
      5. Token-budgeted package with criterion-level mapping and human review flags for unverified/omitted work.
  - Safe static inspection only; never executes submitted code.
"""

import csv
from dataclasses import dataclass, field
import io
import json
import logging
import mimetypes
import os
from pathlib import Path
import re
import struct
from typing import Any
import xml.etree.ElementTree as ET
import zipfile

from app.core.config import get_settings
from app.core.exceptions import AppException, FileTooLargeError
from app.services.document_processing.docx_processor import extract_text_from_docx
from app.services.document_processing.notebook_processor import (
    ParsedNotebook,
    get_notebook_processor,
)
from app.services.document_processing.pdf_processor import extract_text_from_pdf

logger = logging.getLogger(__name__)

# Noise directories to safely ignore during extraction
IGNORED_DIRECTORIES = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "__macosx",
    ".idea",
    ".vscode",
    ".tox",
    ".ipynb_checkpoints",
}

# Operating system / cache files to skip
IGNORED_FILES = {
    ".ds_store",
    "thumbs.db",
    "desktop.ini",
}

# Standard English stopwords for dynamic term extraction
STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are",
    "aren't", "as", "at", "be", "because", "been", "before", "being", "below", "between", "both",
    "but", "by", "can", "can't", "cannot", "could", "couldn't", "did", "didn't", "do", "does",
    "doesn't", "doing", "don't", "down", "during", "each", "few", "for", "from", "further", "had",
    "hadn't", "has", "hasn't", "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her",
    "here", "here's", "hers", "herself", "him", "himself", "his", "how", "how's", "i", "i'd",
    "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it", "it's", "its", "itself", "let's",
    "me", "more", "most", "mustn't", "my", "myself", "no", "nor", "not", "of", "off", "on", "once",
    "only", "or", "other", "ought", "our", "ours", "ourselves", "out", "over", "own", "same", "shan't",
    "she", "she'd", "she'll", "she's", "should", "shouldn't", "so", "some", "such", "than", "that",
    "that's", "the", "their", "theirs", "them", "themselves", "then", "there", "there's", "these",
    "they", "they'd", "they'll", "they're", "they've", "this", "those", "through", "to", "too",
    "under", "until", "up", "very", "was", "wasn't", "we", "we'd", "we'll", "we're", "we've",
    "were", "weren't", "what", "what's", "when", "when's", "where", "where's", "which", "while",
    "who", "who's", "whom", "why", "why's", "with", "won't", "would", "wouldn't", "you", "you'd",
    "you'll", "you're", "you've", "your", "yours", "yourself", "yourselves",
}

SOURCE_CODE_EXTENSIONS = {
    ".py", ".java", ".cpp", ".c", ".h", ".hpp", ".cs", ".js", ".ts",
    ".jsx", ".tsx", ".html", ".css", ".r", ".sql", ".sh", ".scala",
    ".kt", ".go", ".rs", ".rb", ".php", ".m", ".swift",
}

DOCUMENT_EXTENSIONS = {
    ".md", ".txt", ".pdf", ".docx", ".doc", ".rst",
}

TABULAR_EXTENSIONS = {
    ".csv", ".tsv",
}

IMAGE_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".webp", ".svg", ".bmp", ".gif",
}

CONFIG_MANIFEST_FILENAMES = {
    "requirements.txt", "environment.yml", "environment.yaml",
    "pyproject.toml", "pipfile", "pipfile.lock", "setup.py",
    "package.json", "package-lock.json", "pom.xml", "build.gradle",
    "dockerfile", "makefile", "gemfile",
}

CONFIG_EXTENSIONS = {
    ".json", ".yaml", ".yml", ".xml", ".toml", ".ini", ".cfg",
}


@dataclass
class ArchiveFileInventoryItem:
    """Detailed record of an individual file within an archive."""
    rel_path: str
    filename: str
    extension: str
    detected_content_type: str
    category: str  # "notebook", "source", "tabular", "document", "config", "image", "test", "other"
    size_bytes: int
    processing_status: str  # "PROCESSED", "PARTIAL", "UNSUPPORTED", "FAILED", "OMITTED"
    useful_content_extracted: bool
    summary: str
    extracted_content: str = ""
    error_or_omission_reason: str | None = None
    vision_inspected: bool = False
    is_test: bool = False
    relevance_score: float = 0.0

    @property
    def size(self) -> int:
        """Backwards compatibility for legacy ZipFileEntry.size."""
        return self.size_bytes


# Alias for backwards compatibility
ZipFileEntry = ArchiveFileInventoryItem


@dataclass
class ZipEvidenceInventory:
    """Structured archive manifest and diagnostic evidence inventory."""
    total_entries: int = 0
    supported_count: int = 0
    processed_count: int = 0
    failed_count: int = 0
    unsupported_count: int = 0
    truncated_count: int = 0
    omitted_count: int = 0
    vision_inspected_count: int = 0
    total_size_bytes: int = 0
    category_counts: dict[str, int] = field(default_factory=dict)
    file_entries: list[ArchiveFileInventoryItem] = field(default_factory=list)
    extracted_dir: str | None = None
    notebooks: list[ParsedNotebook] = field(default_factory=list)
    has_readme: bool = False
    has_tests: bool = False
    has_manifest: bool = False
    criterion_evidence_mapping: dict[str, list[str]] = field(default_factory=dict)
    criteria_requiring_human_review: list[dict[str, str]] = field(default_factory=list)

    @property
    def total_files(self) -> int:
        """Backwards compatibility for legacy ZipManifest.total_files."""
        return self.total_entries

    @total_files.setter
    def total_files(self, value: int) -> None:
        self.total_entries = value


# Alias for backwards compatibility
ZipManifest = ZipEvidenceInventory


class ZipProcessor:
    """Safe, generic inspector, content processor, and evidence builder for ZIP submissions."""

    def __init__(
        self,
        max_file_count: int | None = None,
        max_extracted_mb: int | None = None,
        max_code_file_kb: int | None = None,
        max_evidence_chars: int | None = None,
        max_code_file_chars: int | None = None,
        max_source_files: int | None = None,
    ) -> None:
        settings = get_settings()
        self.max_file_count = max_file_count or settings.max_zip_file_count
        self.max_extracted_bytes = (max_extracted_mb or settings.max_zip_extracted_size_mb) * 1024 * 1024
        self.max_code_file_bytes = (max_code_file_kb or settings.max_code_file_size_kb) * 1024
        self.max_evidence_chars = max_evidence_chars or settings.max_submission_evidence_chars
        self.max_code_file_chars = max_code_file_chars or settings.max_code_file_chars
        self.max_source_files = max_source_files or settings.max_project_source_files

    # -------------------------------------------------------------------------
    # STAGE 1 & 2: RECURSIVE INVENTORY & GENERIC CONTENT PROCESSING
    # -------------------------------------------------------------------------

    def inspect_and_extract(
        self,
        zip_path: str | Path,
        target_extract_dir: str | Path,
        vision_provider: Any = None,
    ) -> ZipEvidenceInventory:
        """
        Safely inspects every archive entry in a ZIP file, extracts valid files,
        and processes content across all supported formats.
        """
        zip_file_path = Path(zip_path)
        extract_dir = Path(target_extract_dir).resolve()
        extract_dir.mkdir(parents=True, exist_ok=True)

        if not zipfile.is_zipfile(zip_file_path):
            raise AppException(
                detail="Uploaded file is not a valid or readable ZIP archive.",
                status_code=422,
            )

        manifest = ZipEvidenceInventory(extracted_dir=str(extract_dir))
        notebook_processor = get_notebook_processor()

        with zipfile.ZipFile(zip_file_path, "r") as zf:
            infolist = zf.infolist()

            # 1. Check file count limit
            non_dir_entries = [e for e in infolist if not e.is_dir()]
            if len(non_dir_entries) > self.max_file_count:
                raise AppException(
                    detail=f"ZIP archive contains too many files ({len(non_dir_entries)}). Limit is {self.max_file_count}.",
                    status_code=422,
                )

            total_uncompressed = 0

            # 2. Security pre-scan: Zip Slip, symlinks, compression ratio (zip bombs)
            for info in non_dir_entries:
                unix_mode = (info.external_attr >> 16) & 0o177777
                if (unix_mode & 0o120000) == 0o120000:
                    raise AppException(
                        detail=f"Security violation: Symlinks are not permitted in submission archive: {info.filename}",
                        status_code=422,
                    )

                norm_name = os.path.normpath(info.filename).replace("\\", "/")
                if (
                    norm_name.startswith("/")
                    or norm_name.startswith("../")
                    or "/../" in norm_name
                    or ":" in norm_name
                ):
                    raise AppException(
                        detail=f"Security violation: Illegal archive path traversal entry: {info.filename}",
                        status_code=422,
                    )

                if info.compress_size > 0:
                    ratio = info.file_size / info.compress_size
                    if ratio > 120 and info.file_size > 1024 * 1024:
                        raise AppException(
                            detail=f"Security violation: Suspicious compression ratio detected in file {info.filename}",
                            status_code=422,
                        )

                total_uncompressed += info.file_size
                if total_uncompressed > self.max_extracted_bytes:
                    max_mb = self.max_extracted_bytes // (1024 * 1024)
                    raise FileTooLargeError(max_mb=max_mb)

            manifest.total_size_bytes = total_uncompressed

            # 3. Safe Extraction and Entry Inventory
            for info in infolist:
                norm_name = os.path.normpath(info.filename).replace("\\", "/")
                if not norm_name or norm_name == ".":
                    continue

                parts = [p.lower() for p in norm_name.split("/")]
                if any(part in IGNORED_DIRECTORIES for part in parts):
                    continue
                if parts[-1] in IGNORED_FILES or parts[-1].startswith("._"):
                    continue

                dest = (extract_dir / norm_name).resolve()
                try:
                    dest.relative_to(extract_dir)
                except ValueError:
                    raise AppException(
                        detail="Security violation: Path resolution escaped destination directory.",
                        status_code=422,
                    )

                if info.is_dir():
                    dest.mkdir(parents=True, exist_ok=True)
                    continue

                dest.parent.mkdir(parents=True, exist_ok=True)

                # Stream file to destination
                with zf.open(info, "r") as src_fp, open(dest, "wb") as dst_fp:
                    dst_fp.write(src_fp.read())

                # Process the entry with appropriate generic processor
                item = self._process_archive_file(
                    file_path=dest,
                    rel_path=norm_name,
                    size_bytes=info.file_size,
                    notebook_processor=notebook_processor,
                    vision_provider=vision_provider,
                )

                manifest.file_entries.append(item)
                manifest.category_counts[item.category] = manifest.category_counts.get(item.category, 0) + 1

                # Update counts
                if item.processing_status == "PROCESSED":
                    manifest.processed_count += 1
                    manifest.supported_count += 1
                elif item.processing_status == "PARTIAL":
                    manifest.processed_count += 1
                    manifest.supported_count += 1
                    manifest.truncated_count += 1
                elif item.processing_status == "UNSUPPORTED":
                    manifest.unsupported_count += 1
                elif item.processing_status == "FAILED":
                    manifest.failed_count += 1
                    manifest.supported_count += 1

                if item.vision_inspected:
                    manifest.vision_inspected_count += 1

                # Flags
                if item.category == "manifest" or Path(norm_name).name.lower() in CONFIG_MANIFEST_FILENAMES:
                    manifest.has_manifest = True
                if (item.category == "doc" or item.category == "document") and "readme" in norm_name.lower():
                    manifest.has_readme = True
                if item.is_test:
                    manifest.has_tests = True

            manifest.total_entries = len(manifest.file_entries)

        return manifest

    def _process_archive_file(
        self,
        file_path: Path,
        rel_path: str,
        size_bytes: int,
        notebook_processor: Any,
        vision_provider: Any = None,
    ) -> ArchiveFileInventoryItem:
        """Dispatches an extracted archive file to its corresponding generic processor."""
        ext = file_path.suffix.lower()
        filename = file_path.name
        lower_name = filename.lower()
        lower_path = rel_path.lower()

        # Check if test file
        is_test = (
            "test" in lower_path
            or lower_name.startswith("test_")
            or lower_name.endswith("_test.py")
            or lower_name.endswith(".test.js")
            or lower_name.endswith(".test.ts")
            or lower_name.endswith("spec.js")
            or lower_name.endswith("spec.ts")
        )

        detected_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

        # 1. Jupyter Notebooks
        if ext == ".ipynb":
            detected_type = "application/x-ipynb+json"
            try:
                parsed_nb = notebook_processor.parse_file(file_path, filename=rel_path)
                status = "PROCESSED"
                summary = (
                    f"Jupyter Notebook ({parsed_nb.audit.total_cells} cells: "
                    f"{parsed_nb.audit.code_cells} code [{parsed_nb.audit.executed_code_cells} executed], "
                    f"{parsed_nb.audit.markdown_cells} markdown). Execution status: {parsed_nb.audit.execution_status}."
                )
                return ArchiveFileInventoryItem(
                    rel_path=rel_path,
                    filename=filename,
                    extension=ext,
                    detected_content_type=detected_type,
                    category="notebook",
                    size_bytes=size_bytes,
                    processing_status=status,
                    useful_content_extracted=True,
                    summary=summary,
                    extracted_content=parsed_nb.text_representation,
                    is_test=is_test,
                )
            except Exception as exc:
                return ArchiveFileInventoryItem(
                    rel_path=rel_path,
                    filename=filename,
                    extension=ext,
                    detected_content_type=detected_type,
                    category="notebook",
                    size_bytes=size_bytes,
                    processing_status="FAILED",
                    useful_content_extracted=False,
                    summary=f"Notebook parsing error: {exc}",
                    error_or_omission_reason=str(exc),
                    is_test=is_test,
                )

        # 2. Dependency Manifests (requirements.txt, package.json, pom.xml, etc.)
        if lower_name in CONFIG_MANIFEST_FILENAMES:
            summary, content, useful, reason = self._process_config_data(file_path, ext)
            return ArchiveFileInventoryItem(
                rel_path=rel_path,
                filename=filename,
                extension=ext,
                detected_content_type="text/plain" if ext == ".txt" else detected_type,
                category="manifest",
                size_bytes=size_bytes,
                processing_status="PROCESSED" if useful else "FAILED",
                useful_content_extracted=useful,
                summary=summary,
                extracted_content=content,
                error_or_omission_reason=reason,
                is_test=is_test,
            )

        # 3. Tabular / CSV / TSV Data
        if ext in TABULAR_EXTENSIONS:
            detected_type = "text/csv" if ext == ".csv" else "text/tab-separated-values"
            summary, content, useful, reason = self._process_tabular_data(file_path)
            status = "PROCESSED" if useful else "FAILED"
            return ArchiveFileInventoryItem(
                rel_path=rel_path,
                filename=filename,
                extension=ext,
                detected_content_type=detected_type,
                category="data",
                size_bytes=size_bytes,
                processing_status=status,
                useful_content_extracted=useful,
                summary=summary,
                extracted_content=content,
                error_or_omission_reason=reason,
                is_test=is_test,
            )

        # 3. Documents (PDF, DOCX)
        if ext in (".pdf", ".docx", ".doc"):
            detected_type = "application/pdf" if ext == ".pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            summary, content, useful, reason = self._process_document_data(file_path, ext)
            status = "PROCESSED" if useful else "PARTIAL"
            return ArchiveFileInventoryItem(
                rel_path=rel_path,
                filename=filename,
                extension=ext,
                detected_content_type=detected_type,
                category="doc",
                size_bytes=size_bytes,
                processing_status=status,
                useful_content_extracted=useful,
                summary=summary,
                extracted_content=content,
                error_or_omission_reason=reason,
                is_test=is_test,
            )

        # 4. Markdown & Plain Text
        if ext in (".md", ".txt", ".rst"):
            detected_type = "text/markdown" if ext == ".md" else "text/plain"
            summary, content = self._process_text_data(file_path)
            return ArchiveFileInventoryItem(
                rel_path=rel_path,
                filename=filename,
                extension=ext,
                detected_content_type=detected_type,
                category="doc",
                size_bytes=size_bytes,
                processing_status="PROCESSED",
                useful_content_extracted=True,
                summary=summary,
                extracted_content=content,
                is_test=is_test,
            )

        # 5. Source Code
        if ext in SOURCE_CODE_EXTENSIONS:
            summary, content, useful, reason, truncated = self._process_source_code(file_path, ext)
            status = "PARTIAL" if truncated else "PROCESSED"
            cat = "test" if is_test else "source"
            return ArchiveFileInventoryItem(
                rel_path=rel_path,
                filename=filename,
                extension=ext,
                detected_content_type=detected_type,
                category=cat,
                size_bytes=size_bytes,
                processing_status=status,
                useful_content_extracted=useful,
                summary=summary,
                extracted_content=content,
                error_or_omission_reason=reason,
                is_test=is_test,
            )

        # 6. Structured Configurations & Manifests
        if ext in CONFIG_EXTENSIONS or lower_name in CONFIG_MANIFEST_FILENAMES:
            summary, content, useful, reason = self._process_config_data(file_path, ext)
            cat = "manifest" if lower_name in CONFIG_MANIFEST_FILENAMES else "config"
            return ArchiveFileInventoryItem(
                rel_path=rel_path,
                filename=filename,
                extension=ext,
                detected_content_type=detected_type,
                category=cat,
                size_bytes=size_bytes,
                processing_status="PROCESSED" if useful else "FAILED",
                useful_content_extracted=useful,
                summary=summary,
                extracted_content=content,
                error_or_omission_reason=reason,
                is_test=is_test,
            )

        # 7. Images (PNG, JPG, SVG, WebP, etc.)
        if ext in IMAGE_EXTENSIONS:
            summary, content, useful, vision_done, reason = self._process_image_data(
                file_path=file_path,
                rel_path=rel_path,
                ext=ext,
                vision_provider=vision_provider,
            )
            return ArchiveFileInventoryItem(
                rel_path=rel_path,
                filename=filename,
                extension=ext,
                detected_content_type=detected_type,
                category="data",
                size_bytes=size_bytes,
                processing_status="PROCESSED" if useful else "PARTIAL",
                useful_content_extracted=useful,
                summary=summary,
                extracted_content=content,
                vision_inspected=vision_done,
                error_or_omission_reason=reason,
                is_test=is_test,
            )

        # 8. Other / Unsupported Formats (Binary checkpoints, executables, compiled objects)
        return ArchiveFileInventoryItem(
            rel_path=rel_path,
            filename=filename,
            extension=ext,
            detected_content_type=detected_type,
            category="other",
            size_bytes=size_bytes,
            processing_status="UNSUPPORTED",
            useful_content_extracted=False,
            summary=f"Unsupported format '{ext or 'binary'}' ({size_bytes} bytes).",
            error_or_omission_reason="Binary file or unsupported format for direct static inspection.",
            is_test=is_test,
        )

    # -------------------------------------------------------------------------
    # GENERIC PROCESSOR IMPLEMENTATIONS
    # -------------------------------------------------------------------------

    def _process_tabular_data(
        self,
        file_path: Path,
        max_rows: int = 10000,
    ) -> tuple[str, str, bool, str | None]:
        """
        Generic, memory-safe tabular data processor.
        Extracts headers, dimensions, numeric metric summaries (min/max/mean/final),
        distinct experiment configurations, and representative rows without loading unbounded data into memory.
        """
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as fp:
                first_line = fp.readline()
                if not first_line.strip():
                    return "Empty tabular data file.", "Empty tabular data file.", False, "File is empty."

                delim = "\t" if "\t" in first_line else ","
                fp.seek(0)
                reader = csv.reader(fp, delimiter=delim)
                try:
                    header = next(reader)
                except StopIteration:
                    return "Empty tabular data file.", "Empty tabular data file.", False, "File is empty."

                headers = [h.strip() for h in header if h.strip()]
                num_cols = len(headers)

                row_count = 0
                sample_rows_head: list[list[str]] = []
                sample_rows_tail: list[list[str]] = []
                numeric_stats: dict[int, dict[str, float]] = {}
                categorical_vals: dict[int, set[str]] = {}

                # Initialize tracking structures
                for col_idx in range(num_cols):
                    numeric_stats[col_idx] = {"min": float("inf"), "max": float("-inf"), "sum": 0.0, "count": 0, "last": 0.0}
                    categorical_vals[col_idx] = set()

                for row in reader:
                    if not row or not any(row):
                        continue
                    row_count += 1
                    if len(sample_rows_head) < 3:
                        sample_rows_head.append(row[:num_cols])
                    else:
                        if len(sample_rows_tail) >= 2:
                            sample_rows_tail.pop(0)
                        sample_rows_tail.append(row[:num_cols])

                    if row_count <= max_rows:
                        for col_idx, val in enumerate(row[:num_cols]):
                            clean_v = val.strip()
                            try:
                                num_v = float(clean_v)
                                s = numeric_stats[col_idx]
                                if num_v < s["min"]:
                                    s["min"] = num_v
                                if num_v > s["max"]:
                                    s["max"] = num_v
                                s["sum"] += num_v
                                s["count"] += 1
                                s["last"] = num_v
                            except ValueError:
                                if clean_v and len(categorical_vals[col_idx]) < 12:
                                    categorical_vals[col_idx].add(clean_v)

            # Build summaries
            col_summaries: list[str] = []
            numeric_metrics: list[str] = []
            distinct_configs: list[str] = []

            for idx, col_name in enumerate(headers):
                stat = numeric_stats.get(idx)
                if stat and stat["count"] > 0:
                    mean_val = stat["sum"] / stat["count"]
                    min_str = f"{stat['min']:.4f}".rstrip("0").rstrip(".")
                    max_str = f"{stat['max']:.4f}".rstrip("0").rstrip(".")
                    mean_str = f"{mean_val:.4f}".rstrip("0").rstrip(".")
                    last_str = f"{stat['last']:.4f}".rstrip("0").rstrip(".")
                    metric_str = f"{col_name}: [min={min_str}, max={max_str}, mean={mean_str}, final={last_str}]"
                    numeric_metrics.append(metric_str)
                    col_summaries.append(f"{col_name} (numeric)")
                else:
                    cats = categorical_vals.get(idx, set())
                    if cats and len(cats) <= 10:
                        distinct_str = f"{col_name}: {{{', '.join(sorted(cats))}}}"
                        distinct_configs.append(distinct_str)
                        col_summaries.append(f"{col_name} (configs: {len(cats)})")
                    else:
                        col_summaries.append(f"{col_name} (text)")

            summary = (
                f"Tabular results ({row_count} rows, {num_cols} columns). "
                f"Columns: [{', '.join(headers[:6])}{'...' if len(headers) > 6 else ''}]."
            )

            # Build detailed text representation
            lines: list[str] = [
                f"Dimensions: {row_count} data rows x {num_cols} columns",
                f"Headers: {', '.join(headers)}",
            ]
            if numeric_metrics:
                lines.append("\nNumeric Metrics & Experimental Outcomes:")
                for m in numeric_metrics:
                    lines.append(f"  - {m}")
            if distinct_configs:
                lines.append("\nDistinct Configurations & Categorical Parameters:")
                for c in distinct_configs:
                    lines.append(f"  - {c}")

            lines.append("\nRepresentative Sample Data:")
            for i, r in enumerate(sample_rows_head, 1):
                lines.append(f"  Row {i}: {', '.join(r)}")
            if row_count > 5 and sample_rows_tail:
                lines.append("  ...")
                start_tail = max(len(sample_rows_head) + 1, row_count - len(sample_rows_tail) + 1)
                for j, r in enumerate(sample_rows_tail, start_tail):
                    lines.append(f"  Row {j}: {', '.join(r)}")

            return summary, "\n".join(lines), True, None
        except Exception as exc:
            return f"Tabular processing failed: {exc}", f"Could not parse tabular data: {exc}", False, str(exc)

    def _process_document_data(
        self,
        file_path: Path,
        ext: str,
    ) -> tuple[str, str, bool, str | None]:
        """
        Generic document processor for PDF and DOCX files.
        Detects headings, extracts structure, and detects scanned/low-text PDFs.
        """
        try:
            if ext == ".pdf":
                raw_text = extract_text_from_pdf(file_path)
            else:
                raw_text = extract_text_from_docx(file_path)

            clean_doc = raw_text.strip()
            if not clean_doc or len(clean_doc) < 50:
                summary = f"Document '{file_path.name}' has minimal or no extractable text ({len(clean_doc)} chars)."
                reason = "Scanned or image-only PDF with little/no extractable text."
                return summary, "(Document contains no extractable text or is image-scanned)", False, reason

            # Extract headings
            headings: list[str] = []
            for line in clean_doc.splitlines()[:60]:
                line_s = line.strip()
                if (
                    len(line_s) > 3
                    and len(line_s) < 80
                    and (
                        line_s.isupper()
                        or re.match(r"^(?:[0-9]+\.|[IVXLCDM]+\.)\s+[A-Z]", line_s)
                        or line_s.endswith(":")
                    )
                ):
                    headings.append(line_s)
                    if len(headings) >= 5:
                        break

            heading_preview = f" (Headings: {'; '.join(headings)})" if headings else ""
            summary = f"Document report ({len(clean_doc)} chars){heading_preview}."

            max_chars = min(self.max_code_file_chars, 4000)
            capped_content = clean_doc
            if len(clean_doc) > max_chars:
                capped_content = clean_doc[:max_chars] + f"\n... [Document text truncated at {max_chars} chars] ..."

            return summary, capped_content, True, None
        except Exception as exc:
            return f"Document extraction failed: {exc}", f"Error reading document: {exc}", False, str(exc)

    def _process_text_data(self, file_path: Path) -> tuple[str, str]:
        """Generic Markdown and plain text processor."""
        try:
            text = file_path.read_text(encoding="utf-8", errors="replace").strip()
            if not text:
                return "Empty text file.", "Empty text file."

            headings: list[str] = []
            for line in text.splitlines()[:50]:
                line_s = line.strip()
                if line_s.startswith("#") and len(line_s) > 2:
                    headings.append(line_s.lstrip("#").strip())
                    if len(headings) >= 4:
                        break

            heading_str = f" Sections: [{', '.join(headings)}]" if headings else ""
            summary = f"Text document ({len(text)} chars).{heading_str}"

            max_chars = min(self.max_code_file_chars, 4000)
            content = text if len(text) <= max_chars else text[:max_chars] + f"\n... [Truncated at {max_chars} chars] ..."
            return summary, content
        except Exception as exc:
            return f"Text reading failed: {exc}", f"Could not read text: {exc}"

    def _process_source_code(
        self,
        file_path: Path,
        ext: str,
    ) -> tuple[str, str, bool, str | None, bool]:
        """
        Generic, static source code processor.
        Preserves syntax context, functions, classes, and comments without executing code.
        """
        try:
            raw_bytes = file_path.read_bytes()
            limit = self.max_code_file_bytes
            truncated = len(raw_bytes) > limit
            content_bytes = raw_bytes[:limit]
            code = content_bytes.decode("utf-8", errors="replace")

            lines = code.splitlines()
            line_count = len(lines)

            # Discover function and class declarations across various project languages
            declaration_patterns = [
                r"^\s*(?:def|async\s+def|class)\s+([A-Za-z0-9_]+)",  # Python
                r"^\s*(?:export\s+)?(?:default\s+)?(?:function|class|interface|type)\s+([A-Za-z0-9_]+)",  # JS/TS
                r"^\s*(?:public|private|protected|static|\s)+[\w<>\[\]]+\s+([A-Za-z0-9_]+)\s*\(",  # Java/C++/C#
                r"^\s*(?:func)\s+(?:\([^)]+\)\s+)?([A-Za-z0-9_]+)",  # Go
            ]
            symbols: list[str] = []
            for line in lines[:200]:
                for pat in declaration_patterns:
                    m = re.match(pat, line)
                    if m:
                        sym = m.group(1)
                        if sym not in symbols:
                            symbols.append(sym)
                            break
                if len(symbols) >= 6:
                    break

            symbols_str = f" Defined symbols: [{', '.join(symbols)}]" if symbols else ""
            trunc_note = f" (Truncated from {len(raw_bytes)} bytes)" if truncated else ""
            summary = f"Source code ({line_count} lines, {ext}).{symbols_str}{trunc_note}"

            reason = f"File exceeded size limit of {limit} bytes." if truncated else None
            return summary, code, True, reason, truncated
        except Exception as exc:
            return f"Code reading failed: {exc}", f"Could not read code: {exc}", False, str(exc), False

    def _process_config_data(
        self,
        file_path: Path,
        ext: str,
    ) -> tuple[str, str, bool, str | None]:
        """Generic configuration and dependency manifest processor."""
        try:
            text = file_path.read_text(encoding="utf-8", errors="replace")
            summary_parts: list[str] = []

            if ext == ".json":
                try:
                    data = json.loads(text)
                    if isinstance(data, dict):
                        top_keys = list(data.keys())[:8]
                        summary_parts.append(f"JSON configuration with keys: {top_keys}")
                    elif isinstance(data, list):
                        summary_parts.append(f"JSON array with {len(data)} items")
                except Exception:
                    summary_parts.append("JSON text file")
            elif ext in (".yaml", ".yml"):
                summary_parts.append("YAML configuration")
            elif ext == ".xml":
                try:
                    root = ET.fromstring(text)
                    summary_parts.append(f"XML document with root tag <{root.tag}>")
                except Exception:
                    summary_parts.append("XML document")
            elif file_path.name.lower() in ("requirements.txt", "pipfile"):
                deps = [l.strip() for l in text.splitlines() if l.strip() and not l.strip().startswith("#")]
                summary_parts.append(f"Python dependencies list ({len(deps)} packages: {', '.join(deps[:5])})")
            elif file_path.name.lower() == "package.json":
                try:
                    pkg = json.loads(text)
                    deps = list(pkg.get("dependencies", {}).keys())
                    summary_parts.append(f"Node package dependencies ({len(deps)} packages: {', '.join(deps[:5])})")
                except Exception:
                    summary_parts.append("Package configuration")
            else:
                summary_parts.append(f"Project configuration ({ext})")

            summary = "; ".join(summary_parts)
            max_c = min(self.max_code_file_chars, 2000)
            content = text if len(text) <= max_c else text[:max_c] + "\n... [Config truncated] ..."
            return summary, content, True, None
        except Exception as exc:
            return f"Config reading failed: {exc}", f"Could not read config: {exc}", False, str(exc)

    def _process_image_data(
        self,
        file_path: Path,
        rel_path: str,
        ext: str,
        vision_provider: Any = None,
    ) -> tuple[str, str, bool, bool, str | None]:
        """
        Generic image processor.
        Detects dimensions and formats. If an active vision-capable model is available,
        it inspects the image. Otherwise, it honestly records that vision inspection is unavailable.
        """
        w, h = self._extract_image_dimensions(file_path, ext)
        dim_str = f"{w}x{h}" if w and h else "unknown dimensions"
        size = file_path.stat().st_size

        # Check if vision provider is available
        has_vision = getattr(vision_provider, "has_vision_capability", False)
        if has_vision and hasattr(vision_provider, "analyze_image"):
            try:
                import asyncio
                import concurrent.futures
                import inspect
                prompt = (
                    f"Analyze this submission image '{rel_path}'. "
                    "Describe the visual evidence, axes, charts, loss/accuracy curves, metrics, or diagrams present."
                )
                if inspect.iscoroutinefunction(vision_provider.analyze_image):
                    try:
                        loop = asyncio.get_running_loop()
                    except RuntimeError:
                        loop = None

                    if loop and loop.is_running():
                        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                            desc = pool.submit(asyncio.run, vision_provider.analyze_image(str(file_path), prompt=prompt)).result()
                    else:
                        desc = asyncio.run(vision_provider.analyze_image(str(file_path), prompt=prompt))
                else:
                    desc = vision_provider.analyze_image(str(file_path), prompt=prompt)

                summary = f"Visual plot/chart ({dim_str}, {size} bytes). Vision analysis: {desc}"
                content = f"[Visual Inspection: {rel_path} ({dim_str})]:\n{desc}"
                return summary, content, True, True, None
            except Exception as exc:
                logger.warning("Vision analysis failed for %s: %s", rel_path, exc)

        # Honest reporting when vision capability is not configured or unavailable
        summary = (
            f"Image artifact '{file_path.name}' ({dim_str}, {size} bytes). "
            "Visual inspection unavailable (no vision model configured)."
        )
        content = f"[Plot/Graphic File: {rel_path}]: {dim_str}, {size} bytes, format {ext}."
        reason = "Visual inspection unavailable (no vision model configured)."
        return summary, content, False, False, reason

    def _extract_image_dimensions(self, file_path: Path, ext: str) -> tuple[int | None, int | None]:
        """Pure-Python image header dimension extractor for PNG, JPEG, GIF, and SVG."""
        try:
            raw = file_path.read_bytes()
            # PNG
            if ext == ".png" and len(raw) >= 24 and raw.startswith(b"\x89PNG\r\n\x1a\n"):
                w, h = struct.unpack(">II", raw[16:24])
                return w, h
            # GIF
            if ext == ".gif" and len(raw) >= 10 and (raw.startswith(b"GIF87a") or raw.startswith(b"GIF89a")):
                w, h = struct.unpack("<HH", raw[6:10])
                return w, h
            # JPEG
            if ext in (".jpg", ".jpeg") and len(raw) >= 4 and raw.startswith(b"\xff\xd8"):
                idx = 2
                while idx < len(raw) - 8:
                    if raw[idx] != 0xFF:
                        idx += 1
                        continue
                    marker = raw[idx + 1]
                    if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                        h, w = struct.unpack(">HH", raw[idx + 5 : idx + 9])
                        return w, h
                    length = struct.unpack(">H", raw[idx + 2 : idx + 4])[0]
                    idx += 2 + length
            # SVG
            if ext == ".svg":
                text = raw[:1000].decode("utf-8", errors="ignore")
                wm = re.search(r'width=["\']([0-9]+)', text)
                hm = re.search(r'height=["\']([0-9]+)', text)
                if wm and hm:
                    return int(wm.group(1)), int(hm.group(1))
        except Exception:
            pass
        return None, None

    # -------------------------------------------------------------------------
    # STAGES 3, 4, & 5: DYNAMIC EVIDENCE INDEXING & TOKEN-BUDGETED ASSEMBLY
    # -------------------------------------------------------------------------

    def extract_project_evidence(
        self,
        manifest: ZipEvidenceInventory,
        archive_name: str = "project.zip",
        rubric_items: list[dict[str, Any]] | None = None,
        assignment_instructions: str | None = None,
        assignment_title: str | None = None,
    ) -> str:
        """Alias for build_evidence_package."""
        return self.build_evidence_package(
            manifest=manifest,
            archive_name=archive_name,
            rubric_items=rubric_items,
            assignment_instructions=assignment_instructions,
            assignment_title=assignment_title,
        )

    def build_evidence_package(
        self,
        manifest: ZipEvidenceInventory,
        archive_name: str = "project.zip",
        evidence_budget: int | None = None,
        max_sources: int | None = None,
        rubric_items: list[dict[str, Any]] | None = None,
        assignment_instructions: str | None = None,
        assignment_title: str | None = None,
    ) -> str:
        """
        Assembles a generic, criterion-aware, token-budgeted evaluation package.
        Relates evidence dynamically to assignment instructions and approved rubric criteria.
        """
        target_budget = evidence_budget or self.max_evidence_chars
        source_limit = max_sources or self.max_source_files

        # 1. Relate evidence to rubric criteria & compute dynamic relevance
        self._rank_inventory_relevance(
            inventory=manifest,
            rubric_items=rubric_items,
            assignment_instructions=assignment_instructions,
            assignment_title=assignment_title,
        )

        lines: list[str] = [
            f"=== MULTI-FILE PROJECT ARCHIVE EVIDENCE: {archive_name} ===",
            f"Total Valid Discovered Entries: {manifest.total_entries} | Decompressed Size: {manifest.total_size_bytes} bytes",
            f"Content Processing Breakdown: {manifest.category_counts}",
            (
                f"Inspection Audit: {manifest.processed_count} processed, "
                f"{manifest.truncated_count} truncated, {manifest.unsupported_count} unsupported, "
                f"{manifest.failed_count} failed, {manifest.vision_inspected_count} vision-inspected."
            ),
            (
                f"Project Structure: Readme: {manifest.has_readme} | "
                f"Dependencies: {manifest.has_manifest} | Tests: {manifest.has_tests} | "
                f"Notebooks: {len(manifest.notebooks)}"
            ),
            "\n--- COMPLETE ARCHIVE INVENTORY TREE ---",
        ]

        # Display entries in the inventory tree with status (bounded if budget is compact)
        sorted_entries = sorted(manifest.file_entries, key=lambda x: x.rel_path)
        tree_budget = min(1200, max(350, int(target_budget * 0.25)))
        tree_lines: list[str] = []
        omitted_tree_count = 0
        for entry in sorted_entries:
            test_flag = " [TEST]" if entry.is_test else ""
            status_flag = f" [{entry.processing_status}]"
            line = f"- {entry.rel_path} ({entry.size_bytes} bytes, {entry.category}){status_flag}{test_flag}"
            if sum(len(l) for l in tree_lines) + len(line) > tree_budget and len(tree_lines) >= 8:
                omitted_tree_count += 1
            else:
                tree_lines.append(line)
        lines.extend(tree_lines)
        if omitted_tree_count > 0:
            lines.append(
                f"- ... and {omitted_tree_count} more verified project files (see complete manifest in evidence report)."
            )

        # 2. Criterion-to-Evidence Mapping Table
        if manifest.criterion_evidence_mapping:
            lines.append("\n--- RUBRIC CRITERION EVIDENCE MAPPING ---")
            for crit_name, files in manifest.criterion_evidence_mapping.items():
                file_list = ", ".join(files) if files else "(No directly matched files; evaluate across general project files)"
                lines.append(f"* Criterion '{crit_name}': Substantive Evidence in [{file_list}]")

        def current_total() -> int:
            return sum(len(l) for l in lines)

        # 3. Notebook Evidence & Execution Output Preservation
        notebook_entries = [e for e in manifest.file_entries if e.category == "notebook"]
        if notebook_entries:
            lines.append("\n--- JUPYTER NOTEBOOKS & EXECUTION EVIDENCE ---")
            for nb_entry in notebook_entries:
                min_nb = min(300, max(150, int(target_budget * 0.2)))
                rem = max(min_nb, target_budget - current_total())
                nb_text = nb_entry.extracted_content
                if len(nb_text) > rem:
                    nb_text = nb_text[:rem] + f"\n... [Notebook {nb_entry.rel_path} bounded at {rem} chars; execution audit retained] ..."
                lines.append(f"[Notebook: {nb_entry.rel_path}]")
                lines.append(nb_text)
                lines.append("")

        # 4. Tabular & Numerical Results (Preserving Metrics and Configurations)
        tabular_entries = [e for e in manifest.file_entries if e.category == "tabular" and e.useful_content_extracted]
        if tabular_entries:
            lines.append("\n--- TABULAR DATA & EXPERIMENTAL RESULTS ---")
            for tab_entry in tabular_entries:
                min_tab = min(200, max(100, int(target_budget * 0.1)))
                rem = max(min_tab, target_budget - current_total())
                content = tab_entry.extracted_content
                if len(content) > rem:
                    content = content[:rem] + "\n... [Tabular metrics preview truncated] ..."
                lines.append(f"[CSV Data/Results: {tab_entry.rel_path}]")
                lines.append(content)
                lines.append("")

        # 5. Document Reports (PDF / DOCX / Markdown)
        doc_entries = [
            e for e in manifest.file_entries
            if e.category == "document" and e.useful_content_extracted and "readme" not in e.rel_path.lower()
        ]
        if doc_entries:
            lines.append("\n--- WRITTEN REPORTS & ACADEMIC DOCUMENTATION ---")
            for doc_entry in doc_entries:
                min_doc = min(200, max(100, int(target_budget * 0.1)))
                rem = max(min_doc, target_budget - current_total())
                if rem < min_doc:
                    break
                content = doc_entry.extracted_content
                if len(content) > rem:
                    content = content[:rem] + "\n... [Document preview truncated] ..."
                lines.append(f"[Document Report: {doc_entry.rel_path}]")
                lines.append(content)
                lines.append("")

        # 6. Source Code Deliverables (Ranked by Dynamic Rubric & Task Relevance)
        source_entries = [
            e for e in manifest.file_entries
            if e.category in ("source", "test") and e.useful_content_extracted
        ]
        lines.append("\n--- SOURCE CODE DELIVERABLES ---")
        if source_entries:
            ranked_sources = sorted(source_entries, key=lambda x: x.relevance_score, reverse=True)
            chosen_sources = ranked_sources[:source_limit]
            omitted_sources = ranked_sources[source_limit:]

            min_src = min(200, max(100, int(target_budget * 0.1)))
            for entry in chosen_sources:
                rem_budget = target_budget - current_total()
                if rem_budget < min_src:
                    omitted_sources.append(entry)
                    continue

                per_file_limit = min(self.max_code_file_bytes, self.max_code_file_chars, rem_budget)
                code_text = entry.extracted_content
                if len(code_text) > per_file_limit:
                    code_text = code_text[:per_file_limit] + f"\n... [Truncated at {per_file_limit} chars] ..."
                lines.append(f"\n[Source File: {entry.rel_path}] (Relevance Score: {entry.relevance_score:.1f})")
                lines.append(code_text)

            if omitted_sources:
                manifest.omitted_count += len(omitted_sources)
                omitted_names = [e.rel_path for e in omitted_sources]
                preview_omitted = ", ".join(omitted_names[:6])
                extra = f" and {len(omitted_names) - 6} more" if len(omitted_names) > 6 else ""
                lines.append(
                    f"\n[Notice: {len(omitted_sources)} secondary source file(s) omitted from prompt evidence "
                    f"to respect token budget ({preview_omitted}{extra}). All verified in ZIP manifest.]"
                )
        else:
            lines.append("(No standalone source code files outside notebooks)")

        # 7. Visual Artifacts (Charts, Plots, Screenshots)
        image_entries = [e for e in manifest.file_entries if e.category == "image"]
        if image_entries:
            lines.append("\n--- VISUAL ARTIFACTS & PLOTS ---")
            for img_entry in image_entries[:5]:
                lines.append(f"{img_entry.extracted_content}")

        # 8. Unreadable or Unsupported Formats Notice
        unreadable_entries = [e for e in manifest.file_entries if e.processing_status in ("UNSUPPORTED", "FAILED")]
        if unreadable_entries:
            lines.append("\n--- UNREADABLE / UNSUPPORTED ARCHIVE ENTRIES ---")
            for unreadable in unreadable_entries[:8]:
                reason = unreadable.error_or_omission_reason or "Unsupported format"
                lines.append(f"- {unreadable.rel_path}: {reason}")

        # 9. Faculty Review Flags for Unverified Evidence
        if manifest.criteria_requiring_human_review:
            lines.append("\n--- ATTENTION FACULTY: CRITERIA REQUIRING HUMAN REVIEW ---")
            for item in manifest.criteria_requiring_human_review:
                lines.append(f"* Criterion '{item['criterion']}': {item['reason']}")

        result_text = "\n".join(lines)
        if len(result_text) > target_budget:
            result_text = (
                result_text[:target_budget]
                + f"\n... [Project evidence package condensed to {target_budget} characters for safe token budget. Inventory and inspection diagnostics preserved.] ..."
            )
        return result_text

    # -------------------------------------------------------------------------
    # DYNAMIC RELEVANCE RANKING & CRITERION MAPPING (ZERO HARDCODING)
    # -------------------------------------------------------------------------

    def _rank_inventory_relevance(
        self,
        inventory: ZipEvidenceInventory,
        rubric_items: list[dict[str, Any]] | None,
        assignment_instructions: str | None,
        assignment_title: str | None,
    ) -> None:
        """
        Dynamically computes relevance score for each archive entry using:
          - Tokens from the approved rubric criteria names and descriptions.
          - Tokens from the assignment title and instructions.
          - Content-type suitability and directory depth.
        No assignment names, model names, or filenames are hardcoded.
        """
        general_terms = self._tokenize(f"{assignment_title or ''} {assignment_instructions or ''}")
        rubric_criteria = rubric_items or []

        criterion_tokens_map: dict[str, set[str]] = {}
        for r in rubric_criteria:
            crit_name = r.get("criterion", "")
            crit_desc = r.get("description", "")
            tokens = self._tokenize(f"{crit_name} {crit_desc}")
            criterion_tokens_map[crit_name] = tokens

        criterion_evidence: dict[str, list[str]] = {r.get("criterion", ""): [] for r in rubric_criteria}
        review_flags: list[dict[str, str]] = []

        for entry in inventory.file_entries:
            entry_tokens = self._tokenize(f"{entry.rel_path} {entry.filename} {entry.summary}")
            content_tokens = self._tokenize(entry.extracted_content[:1500])

            # Base category scoring
            score = 0.0
            if entry.category == "notebook":
                score += 35.0
            elif entry.category in ("source", "test"):
                score += 30.0
            elif entry.category == "data":
                score += 25.0
            elif entry.category == "doc":
                score += 20.0
            elif entry.category in ("config", "manifest"):
                score += 15.0

            all_entry_tokens = entry_tokens | content_tokens

            # General assignment match
            gen_matches = self._count_token_matches(all_entry_tokens, general_terms)
            score += min(gen_matches * 5.0, 30.0)

            # Match against each rubric criterion
            for crit_name, c_tokens in criterion_tokens_map.items():
                match_count = self._count_token_matches(all_entry_tokens, c_tokens)
                if match_count > 0:
                    score += min(match_count * 8.0, 40.0)
                    criterion_evidence[crit_name].append(entry.rel_path)

            # Directory depth penalty
            depth = entry.rel_path.count("/")
            score -= min(depth * 3.0, 15.0)

            entry.relevance_score = max(score, 0.0)

        # Populate criterion mapping & check for criteria with missing/unsupported evidence
        for crit_name, matched_files in criterion_evidence.items():
            # Sort matching files by relevance
            sorted_files = sorted(
                matched_files,
                key=lambda f: next((e.relevance_score for e in inventory.file_entries if e.rel_path == f), 0.0),
                reverse=True,
            )
            inventory.criterion_evidence_mapping[crit_name] = sorted_files[:4]

            # If no files matched or matching file was unreadable
            if not sorted_files:
                review_flags.append({
                    "criterion": crit_name,
                    "reason": "No directly matching evidence found across project files. Requires faculty review.",
                })
            else:
                top_entry = next((e for e in inventory.file_entries if e.rel_path == sorted_files[0]), None)
                if top_entry and top_entry.processing_status in ("UNSUPPORTED", "FAILED"):
                    review_flags.append({
                        "criterion": crit_name,
                        "reason": f"Primary evidence in '{top_entry.rel_path}' could not be parsed statically ({top_entry.error_or_omission_reason}).",
                    })

        inventory.criteria_requiring_human_review = review_flags

    def _tokenize(self, text: str) -> set[str]:
        """Extracts normalized alphanumeric words, filtering standard stopwords."""
        words = re.findall(r"[A-Za-z0-9_]{3,}", text.lower())
        return {w for w in words if w not in STOPWORDS}

    def _count_token_matches(self, tokens1: set[str], tokens2: set[str]) -> int:
        """Count exact matches or linguistic stem-prefix matches between two token sets."""
        count = 0
        for t1 in tokens1:
            for t2 in tokens2:
                if t1 == t2 or (len(t1) >= 4 and len(t2) >= 4 and (t1.startswith(t2[:4]) or t2.startswith(t1[:4]))):
                    count += 1
                    break
        return count

    # -------------------------------------------------------------------------
    # STAGE 6: DIAGNOSTICS & TRACEABILITY REPORT GENERATION
    # -------------------------------------------------------------------------

    def generate_evidence_report(
        self,
        submission_id: int,
        inventory: ZipEvidenceInventory,
        original_filename: str | None = None,
    ) -> dict[str, Any]:
        """
        Builds a comprehensive assessment evidence report for authorized faculty
        containing entry counts, per-file processing status, rubric mapping,
        and human review flags.
        """
        truncated_or_excluded: list[dict[str, str]] = []
        file_inventory_diag: list[dict[str, Any]] = []

        for entry in inventory.file_entries:
            file_inventory_diag.append({
                "rel_path": entry.rel_path,
                "filename": entry.filename,
                "extension": entry.extension,
                "detected_content_type": entry.detected_content_type,
                "category": entry.category,
                "size_bytes": entry.size_bytes,
                "processing_status": entry.processing_status,
                "useful_content_extracted": entry.useful_content_extracted,
                "summary": entry.summary,
                "error_or_omission_reason": entry.error_or_omission_reason,
                "vision_inspected": entry.vision_inspected,
                "is_test": entry.is_test,
                "relevance_score": round(entry.relevance_score, 2),
            })
            if entry.processing_status in ("PARTIAL", "UNSUPPORTED", "FAILED", "OMITTED"):
                truncated_or_excluded.append({
                    "rel_path": entry.rel_path,
                    "status": entry.processing_status,
                    "reason": entry.error_or_omission_reason or "Excluded or truncated due to processing boundaries.",
                })

        return {
            "submission_id": submission_id,
            "original_filename": original_filename or "submission.zip",
            "file_format": "zip",
            "total_archive_entries": inventory.total_entries,
            "supported_files_count": inventory.supported_count,
            "successfully_processed_count": inventory.processed_count,
            "failed_files_count": inventory.failed_count,
            "unsupported_files_count": inventory.unsupported_count,
            "truncated_files_count": inventory.truncated_count,
            "omitted_files_count": inventory.omitted_count,
            "vision_inspected": inventory.vision_inspected_count > 0,
            "vision_inspected_count": inventory.vision_inspected_count,
            "category_counts": inventory.category_counts,
            "file_inventory": file_inventory_diag,
            "criterion_evidence_mapping": inventory.criterion_evidence_mapping,
            "truncated_or_excluded_files": truncated_or_excluded,
            "criteria_requiring_human_review": inventory.criteria_requiring_human_review,
        }


_zip_processor: ZipProcessor | None = None


def get_zip_processor() -> ZipProcessor:
    global _zip_processor
    if _zip_processor is None:
        _zip_processor = ZipProcessor()
    return _zip_processor
