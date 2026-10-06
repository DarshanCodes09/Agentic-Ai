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
    """Service for validating and persisting submitted student files."""

    def __init__(self, base_upload_dir: str | None = None) -> None:
        if base_upload_dir is None:
            # Default to backend/uploads/submissions
            project_root = Path(__file__).resolve().parent.parent.parent.parent
            self.upload_dir = project_root / "uploads" / "submissions"
        else:
            self.upload_dir = Path(base_upload_dir)

        self.upload_dir.mkdir(parents=True, exist_ok=True)

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
        Validate, stream to disk, and return (stored_file_path, original_filename).

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
                        # Clean up partial file before raising
                        out_file.close()
                        if destination_path.exists():
                            destination_path.unlink()
                        raise FileTooLargeError(max_mb=20)
                    out_file.write(chunk)
        finally:
            await file.seek(0)

        # Store path relative to project root or normalized string
        return str(destination_path), original_filename

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
