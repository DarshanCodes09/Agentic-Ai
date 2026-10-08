"""
Local file storage service.

Handles secure file uploads (PDF and DOCX) for submissions.
Files are stored under backend/uploads/submissions/ with randomized unique filenames.
"""

import os
import uuid
from pathlib import Path

from fastapi import UploadFile

from app.core.exceptions import FileTooLargeError, InvalidFileTypeError

# Allowed extensions and MIME types
ALLOWED_EXTENSIONS = {".pdf", ".docx"}
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    # Some browsers / clients send octet-stream or docx variants
    "application/octet-stream",
    "application/msword",
}

# Max file size: 20 MB
MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024


class FileStorageService:
    """Service for validating and persisting submitted student files and course materials."""

    def __init__(self, base_upload_dir: str | None = None) -> None:
        project_root = Path(__file__).resolve().parent.parent.parent.parent
        if base_upload_dir is None:
            self.upload_dir = project_root / "uploads" / "submissions"
            self.materials_dir = project_root / "uploads" / "materials"
        else:
            self.upload_dir = Path(base_upload_dir)
            self.materials_dir = Path(base_upload_dir) / "materials"

        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.materials_dir.mkdir(parents=True, exist_ok=True)

    def validate_file(self, file: UploadFile) -> str:
        """
        Validate file extension and content type.

        Returns:
            The normalized lower-case extension (e.g., '.pdf').
        Raises:
            InvalidFileTypeError: If the file type is not permitted.
        """
        filename = file.filename or ""
        ext = Path(filename).suffix.lower()

        if ext not in ALLOWED_EXTENSIONS:
            raise InvalidFileTypeError()

        if file.content_type and file.content_type not in ALLOWED_CONTENT_TYPES:
            # Allow fallback if extension is explicitly .pdf or .docx
            if ext not in ALLOWED_EXTENSIONS:
                raise InvalidFileTypeError()

        return ext

    async def save_file(self, file: UploadFile) -> tuple[str, str]:
        """
        Validate, stream to disk for submissions, and return (stored_file_path, original_filename).

        Raises:
            InvalidFileTypeError: If file extension or MIME type is rejected.
            FileTooLargeError: If file exceeds MAX_FILE_SIZE_BYTES.
        """
        ext = self.validate_file(file)
        original_filename = Path(file.filename or "upload").name

        # Unique random filename prevents path traversal and collisions
        unique_filename = f"{uuid.uuid4().hex}{ext}"
        destination_path = self.upload_dir / unique_filename

        bytes_written = 0
        chunk_size = 1024 * 1024  # 1 MB chunks

        try:
            with open(destination_path, "wb") as out_file:
                while chunk := await file.read(chunk_size):
                    bytes_written += len(chunk)
                    if bytes_written > MAX_FILE_SIZE_BYTES:
                        out_file.close()
                        if destination_path.exists():
                            destination_path.unlink()
                        raise FileTooLargeError(max_mb=20)
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
        ext = self.validate_file(file)
        original_filename = Path(file.filename or "material").name
        unique_filename = f"{uuid.uuid4().hex}{ext}"
        destination_path = self.materials_dir / unique_filename

        bytes_written = 0
        chunk_size = 1024 * 1024  # 1 MB chunks

        try:
            with open(destination_path, "wb") as out_file:
                while chunk := await file.read(chunk_size):
                    bytes_written += len(chunk)
                    if bytes_written > MAX_FILE_SIZE_BYTES:
                        out_file.close()
                        if destination_path.exists():
                            destination_path.unlink()
                        raise FileTooLargeError(max_mb=20)
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
        """Delete file if it exists."""
        try:
            path = Path(file_path)
            if path.exists() and path.is_file():
                path.unlink()
                return True
        except OSError:
            pass
        return False


_file_storage_instance: FileStorageService | None = None


def get_file_storage_service() -> FileStorageService:
    """Dependency / accessor for the singleton storage service."""
    global _file_storage_instance
    if _file_storage_instance is None:
        _file_storage_instance = FileStorageService()
    return _file_storage_instance
