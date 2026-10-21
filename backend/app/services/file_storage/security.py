"""
Security utilities for file access, path traversal prevention, and safe downloads.
"""

import mimetypes
from pathlib import Path
import re
from fastapi.responses import FileResponse

from app.core.exceptions import AppException, ResourceNotFoundError

MIME_TYPE_MAPPING = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc": "application/msword",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".txt": "text/plain",
}

INLINE_PREVIEW_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".txt"}


def sanitize_download_filename(filename: str | None, default_name: str = "download") -> str:
    """
    Sanitize filename to prevent header injection or directory traversal artifacts.
    Keeps alphanumeric characters, dots, hyphens, and underscores.
    """
    if not filename:
        return default_name
    basename = Path(filename).name
    # Strip illegal characters and replace with underscore
    sanitized = re.sub(r"[^a-zA-Z0-9_.-]", "_", basename).strip("._ ")
    return sanitized or default_name


def validate_file_path_safe(raw_path: str, allowed_base_dir: Path) -> Path:
    """
    Validate that raw_path points to an existing file strictly located within allowed_base_dir.

    Raises:
        AppException(403): If path traversal outside allowed_base_dir is attempted.
        ResourceNotFoundError(404): If the file does not exist on disk.
    """
    try:
        resolved_path = Path(raw_path).resolve()
        resolved_base = allowed_base_dir.resolve()
        resolved_path.relative_to(resolved_base)
    except (ValueError, RuntimeError):
        raise AppException(
            detail="Access denied: Invalid file path traversal attempt.",
            status_code=403,
        )

    if not resolved_path.exists() or not resolved_path.is_file():
        raise ResourceNotFoundError("Requested file was not found on disk.")

    return resolved_path


def build_secure_file_response(
    file_path: Path,
    original_filename: str | None,
    inline: bool = False,
) -> FileResponse:
    """
    Construct a secure FileResponse with appropriate MIME type and Content-Disposition header.
    """
    ext = file_path.suffix.lower()
    media_type = MIME_TYPE_MAPPING.get(ext) or mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
    safe_filename = sanitize_download_filename(original_filename, default_name=file_path.name)

    if inline and ext in INLINE_PREVIEW_EXTENSIONS:
        disposition = f'inline; filename="{safe_filename}"'
    else:
        disposition = f'attachment; filename="{safe_filename}"'

    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=safe_filename if not inline else None,
        headers={
            "Content-Disposition": disposition,
            "X-Content-Type-Options": "nosniff",
        },
    )
