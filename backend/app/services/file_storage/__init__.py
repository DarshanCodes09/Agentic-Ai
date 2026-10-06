"""
File storage package.
"""

from app.services.file_storage.storage import FileStorageService, get_file_storage_service

__all__ = ["FileStorageService", "get_file_storage_service"]
