from typing import Any, Dict, Optional
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.app.core.logging import get_logger

logger = get_logger("forensic.errors")


class ForensicAppException(Exception):
    """Base exception for all application-specific forensic errors."""
    def __init__(
        self,
        message: str,
        code: str = "APPLICATION_ERROR",
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}


class EntityNotFoundException(ForensicAppException):
    def __init__(self, message: str = "Requested resource not found"):
        super().__init__(
            message=message,
            code="NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )


class CaseNotFoundException(EntityNotFoundException):
    def __init__(self, message: str = "Requested forensic case not found"):
        super().__init__(message=message)


class PermissionDeniedException(ForensicAppException):
    def __init__(self, message: str = "Access denied"):
        super().__init__(
            message=message,
            code="PERMISSION_DENIED",
            status_code=status.HTTP_403_FORBIDDEN,
        )


class EvidenceIntegrityException(ForensicAppException):
    def __init__(self, message: str = "Evidence integrity validation failed"):
        super().__init__(
            message=message,
            code="EVIDENCE_INTEGRITY_VIOLATION",
            status_code=status.HTTP_400_BAD_REQUEST,
        )


def create_error_response(status_code: int, code: str, message: str) -> JSONResponse:
    """Builds standard JSON error response envelope."""
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
            }
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Registers centralized exception handlers on the FastAPI application."""

    @app.exception_handler(ForensicAppException)
    async def forensic_exception_handler(request: Request, exc: ForensicAppException):
        logger.warning(
            f"Domain Exception: {exc.code} - {exc.message} on path {request.url.path}"
        )
        return create_error_response(
            status_code=exc.status_code,
            code=exc.code,
            message=exc.message,
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        code_map = {
            status.HTTP_404_NOT_FOUND: "NOT_FOUND",
            status.HTTP_403_FORBIDDEN: "FORBIDDEN",
            status.HTTP_401_UNAUTHORIZED: "UNAUTHORIZED",
            status.HTTP_405_METHOD_NOT_ALLOWED: "METHOD_NOT_ALLOWED",
        }
        code = code_map.get(exc.status_code, "HTTP_ERROR")
        return create_error_response(
            status_code=exc.status_code,
            code=code,
            message=str(exc.detail),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        logger.info(f"Validation error on {request.url.path}: {exc.errors()}")
        # Provide clean, non-leaking validation summary
        return create_error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="VALIDATION_ERROR",
            message="Request parameters or body failed schema validation.",
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.error(
            f"Unhandled server error on {request.url.path}: {str(exc)}",
            exc_info=True,
        )
        # Never expose internal tracebacks, paths, or secrets to client
        return create_error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected server error occurred. Please contact the administrator.",
        )
