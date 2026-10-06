"""
Custom application exceptions and FastAPI exception handlers.
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse


# ---------------------------------------------------------------------------
# Domain exceptions
# ---------------------------------------------------------------------------

class AppException(Exception):
    """Base class for all application-specific exceptions."""

    def __init__(self, detail: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


class DuplicateEmailError(AppException):
    def __init__(self) -> None:
        super().__init__(
            detail="An account with this email address already exists.",
            status_code=status.HTTP_409_CONFLICT,
        )


class InvalidCredentialsError(AppException):
    def __init__(self) -> None:
        super().__init__(
            detail="Incorrect email or password.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class UserNotFoundError(AppException):
    def __init__(self) -> None:
        super().__init__(
            detail="User not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )


class InactiveUserError(AppException):
    def __init__(self) -> None:
        super().__init__(
            detail="This account has been deactivated. Please contact an administrator.",
            status_code=status.HTTP_403_FORBIDDEN,
        )


class InvalidTokenError(AppException):
    def __init__(self) -> None:
        super().__init__(
            detail="Could not validate credentials.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class InsufficientPermissionsError(AppException):
    def __init__(self) -> None:
        super().__init__(
            detail="You do not have permission to access this resource.",
            status_code=status.HTTP_403_FORBIDDEN,
        )


# ---------------------------------------------------------------------------
# Phase 2 domain exceptions
# ---------------------------------------------------------------------------

class ResourceNotFoundError(AppException):
    """Generic 404 with a custom message (e.g. 'Subject not found.')."""
    def __init__(self, detail: str = "Resource not found.") -> None:
        super().__init__(detail=detail, status_code=status.HTTP_404_NOT_FOUND)


class DuplicateResourceError(AppException):
    """Generic 409 for duplicate-key / unique-constraint violations."""
    def __init__(self, detail: str = "Resource already exists.") -> None:
        super().__init__(detail=detail, status_code=status.HTTP_409_CONFLICT)


class NotEnrolledError(AppException):
    def __init__(self) -> None:
        super().__init__(
            detail="You are not enrolled in this subject.",
            status_code=status.HTTP_403_FORBIDDEN,
        )


class InvalidFileTypeError(AppException):
    def __init__(self) -> None:
        super().__init__(
            detail="Invalid file type. Only PDF and DOCX files are accepted.",
            status_code=getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422),
        )


class FileTooLargeError(AppException):
    def __init__(self, max_mb: int = 20) -> None:
        super().__init__(
            detail=f"File exceeds the maximum allowed size of {max_mb} MB.",
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        )


# ---------------------------------------------------------------------------
# FastAPI exception handlers
# ---------------------------------------------------------------------------

def register_exception_handlers(app: FastAPI) -> None:
    """Register all custom exception handlers on the FastAPI app."""

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )
