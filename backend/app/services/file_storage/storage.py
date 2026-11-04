"""
Local file storage service.

Handles secure file uploads (PDF and DOCX) for submissions.
Files are stored under backend/uploads/submissions/ with randomized unique filenames.
"""

import os
import uuid
from pathlib import Path

from fastapi import UploadFile

from app.core.config import get_settings
from app.core.exceptions import FileTooLargeError, InvalidFileTypeError

# Supported extensions for multi-format code, notebook, zip, and academic document uploads
ALLOWED_EXTENSIONS = {
    # Documents
    ".pdf",
    ".docx",
    ".doc",
    ".txt",
    ".md",
    # Notebooks
    ".ipynb",
    # Source Code
    ".py",
    ".java",
    ".cpp",
    ".c",
    ".h",
    ".cs",
    ".js",
    ".ts",
    ".html",
    ".css",
    ".r",
    ".sql",
    ".sh",
    # Project Archives
    ".zip",
    # Data & Results / Plots
    ".csv",
    ".json",
    ".png",
    ".jpg",
    ".jpeg",
}

# Permitted extensions for course materials (RAG documents)
ALLOWED_COURSE_MATERIAL_EXTENSIONS = {".pdf", ".docx"}

# Permitted extensions for assignment files (instructions, specifications, rubrics)
ALLOWED_ASSIGNMENT_FILE_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}

ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "application/octet-stream",
    "application/zip",
    "application/x-zip-compressed",
    "application/json",
    "application/x-ipynb+json",
    "text/plain",
    "text/markdown",
    "text/csv",
    "text/x-python",
    "text/javascript",
    "text/html",
    "text/css",
    "image/png",
    "image/jpeg",
}


class FileStorageService:
    """Service for validating and persisting submitted student files, course materials, and assignment files."""

    def __init__(self, base_upload_dir: str | None = None) -> None:
        project_root = Path(__file__).resolve().parent.parent.parent.parent
        if base_upload_dir is None:
            self.upload_dir = project_root / "uploads" / "submissions"
            self.materials_dir = project_root / "uploads" / "materials"
            self.assignments_dir = project_root / "uploads" / "assignments"
        else:
            self.upload_dir = Path(base_upload_dir)
            self.materials_dir = Path(base_upload_dir) / "materials"
            self.assignments_dir = Path(base_upload_dir) / "assignments"

        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.materials_dir.mkdir(parents=True, exist_ok=True)
        self.assignments_dir.mkdir(parents=True, exist_ok=True)

    @property
    def max_file_size_bytes(self) -> int:
        return get_settings().max_upload_size_mb * 1024 * 1024

    def validate_file(self, file: UploadFile, allowed_extensions: set[str] | None = None) -> str:
        """
        Validate file extension and content type.

        Returns:
            The normalized lower-case extension (e.g., '.pdf', '.ipynb', '.zip').
        Raises:
            InvalidFileTypeError: If the file type is not permitted.
        """
        filename = file.filename or ""
        ext = Path(filename).suffix.lower()
        allowed = allowed_extensions or ALLOWED_EXTENSIONS

        if ext not in allowed:
            raise InvalidFileTypeError()

        return ext

    async def save_file(self, file: UploadFile) -> tuple[str, str]:
        """
        Validate, stream to disk for submissions, and return (stored_file_path, original_filename).

        Raises:
            InvalidFileTypeError: If file extension is rejected.
            FileTooLargeError: If file exceeds max_upload_size_mb.
        """
        ext = self.validate_file(file, allowed_extensions=ALLOWED_EXTENSIONS)
        original_filename = Path(file.filename or "upload").name

        # Unique random filename prevents path traversal and collisions
        unique_filename = f"{uuid.uuid4().hex}{ext}"
        destination_path = self.upload_dir / unique_filename

        bytes_written = 0
        chunk_size = 1024 * 1024  # 1 MB chunks
        max_bytes = self.max_file_size_bytes
        max_mb = get_settings().max_upload_size_mb

        try:
            with open(destination_path, "wb") as out_file:
                while chunk := await file.read(chunk_size):
                    bytes_written += len(chunk)
                    if bytes_written > max_bytes:
                        out_file.close()
                        if destination_path.exists():
                            destination_path.unlink()
                        raise FileTooLargeError(max_mb=max_mb)
                    out_file.write(chunk)
        finally:
            await file.seek(0)

        return str(destination_path), original_filename

    async def save_course_material(self, file: UploadFile) -> dict[str, str | int]:
        """
        Validate and stream course materials into uploads/materials/.

        Returns:
            dict containing: file_path, original_filename, stored_filename, file_type, file_size
        """
        ext = self.validate_file(file, allowed_extensions=ALLOWED_COURSE_MATERIAL_EXTENSIONS)
        original_filename = Path(file.filename or "material").name
        unique_filename = f"{uuid.uuid4().hex}{ext}"
        destination_path = self.materials_dir / unique_filename

        bytes_written = 0
        chunk_size = 1024 * 1024  # 1 MB chunks
        max_bytes = self.max_file_size_bytes
        max_mb = get_settings().max_upload_size_mb

        try:
            with open(destination_path, "wb") as out_file:
                while chunk := await file.read(chunk_size):
                    bytes_written += len(chunk)
                    if bytes_written > max_bytes:
                        out_file.close()
                        if destination_path.exists():
                            destination_path.unlink()
                        raise FileTooLargeError(max_mb=max_mb)
                    out_file.write(chunk)
        finally:
            await file.seek(0)

        return {
            "file_path": str(destination_path),
            "original_filename": original_filename,
            "stored_filename": unique_filename,
            "file_type": ext.lstrip("."),
            "file_size": bytes_written,
        }

    async def save_assignment_file(self, file: UploadFile) -> dict[str, str | int]:
        """
        Validate and stream assignment files into uploads/assignments/.

        Returns:
            dict containing: file_path, original_filename, stored_filename, file_type, file_size
        """
        ext = self.validate_file(file, allowed_extensions=ALLOWED_ASSIGNMENT_FILE_EXTENSIONS)
        original_filename = Path(file.filename or "assignment_file").name
        unique_filename = f"{uuid.uuid4().hex}{ext}"
        destination_path = self.assignments_dir / unique_filename

        bytes_written = 0
        chunk_size = 1024 * 1024  # 1 MB chunks
        max_bytes = self.max_file_size_bytes
        max_mb = get_settings().max_upload_size_mb

        try:
            with open(destination_path, "wb") as out_file:
                while chunk := await file.read(chunk_size):
                    bytes_written += len(chunk)
                    if bytes_written > max_bytes:
                        out_file.close()
                        if destination_path.exists():
                            destination_path.unlink()
                        raise FileTooLargeError(max_mb=max_mb)
                    out_file.write(chunk)
        finally:
            await file.seek(0)

        return {
            "file_path": str(destination_path),
            "original_filename": original_filename,
            "stored_filename": unique_filename,
            "file_type": ext.lstrip("."),
            "file_size": bytes_written,
        }

    def delete_file(self, file_path: str) -> bool:
        """Delete file and any unpacked archive directories if they exist."""
        try:
            path = Path(file_path)
            deleted = False
            if path.exists() and path.is_file():
                path.unlink()
                deleted = True

            # Clean up both dot-prefixed and legacy unpacked extraction directories
            dot_unpacked = path.parent / f".{path.stem}_unpacked"
            legacy_unpacked = path.parent / f"{path.stem}_unpacked"
            import shutil
            for d in (dot_unpacked, legacy_unpacked):
                if d.exists() and d.is_dir():
                    shutil.rmtree(d, ignore_errors=True)

            return deleted
        except OSError:
            pass
        return False


def get_archive_unpacked_dir(archive_path: Path | str) -> Path:
    """
    Return the deterministic extracted folder for a ZIP archive.
    Uses a dot prefix ('.<stem>_unpacked') so development reload watchers (WatchFiles)
    ignore changes to extracted student source code.
    """
    p = Path(archive_path)
    dot_dir = p.parent / f".{p.stem}_unpacked"
    legacy_dir = p.parent / f"{p.stem}_unpacked"
    if legacy_dir.exists() and not dot_dir.exists():
        return legacy_dir
    return dot_dir


_file_storage_instance: FileStorageService | None = None


def get_file_storage_service() -> FileStorageService:
    """Dependency / accessor for the singleton storage service."""
    global _file_storage_instance
    if _file_storage_instance is None:
        _file_storage_instance = FileStorageService()
    return _file_storage_instance
