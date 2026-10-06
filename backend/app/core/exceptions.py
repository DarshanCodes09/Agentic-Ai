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
