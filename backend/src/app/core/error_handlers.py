import logging
from collections.abc import Mapping
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.common.exceptions import (
    AppError,
    AuthenticationFailedError,
    ConflictError,
    NotFoundError,
    RateLimitExceededError,
)
from app.core.config import settings
from app.core.security import EncryptionError

logger = logging.getLogger(__name__)


def _build_error_response(
    status_code: int,
    error_code: str,
    message: str,
    details: Any = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    """Standardizes the JSON error payload across all API endpoints."""
    payload: dict[str, Any] = {
        "error": error_code,
        "detail": message,
    }
    if details is not None:
        payload["details"] = details

    return JSONResponse(
        status_code=status_code,
        content=payload,
        headers=headers,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Registers all global exception handlers on the FastAPI application instance."""

    # =========================================================================
    # 1. Domain Exceptions (Method Resolution Order matches subclasses too)
    # =========================================================================

    @app.exception_handler(NotFoundError)
    async def not_found_handler(request: Request, exc: NotFoundError) -> JSONResponse:
        logger.warning(
            "Resource not found [%s %s]: %s",
            request.method,
            request.url.path,
            exc.message,
        )
        return _build_error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="NOT_FOUND",
            message=exc.message,
        )

    @app.exception_handler(ConflictError)
    async def conflict_handler(request: Request, exc: ConflictError) -> JSONResponse:
        logger.warning(
            "Resource conflict [%s %s]: %s",
            request.method,
            request.url.path,
            exc.message,
        )
        return _build_error_response(
            status_code=status.HTTP_409_CONFLICT,
            error_code="CONFLICT",
            message=exc.message,
        )

    @app.exception_handler(RateLimitExceededError)
    async def rate_limit_handler(
        request: Request, exc: RateLimitExceededError
    ) -> JSONResponse:
        logger.warning(
            "Rate limit exceeded [%s %s]: %s",
            request.method,
            request.url.path,
            exc.message,
        )
        return _build_error_response(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            error_code="RATE_LIMIT_EXCEEDED",
            message=exc.message,
        )

    @app.exception_handler(AuthenticationFailedError)
    async def authentication_failed_handler(
        request: Request, exc: AuthenticationFailedError
    ) -> JSONResponse:
        logger.warning(
            "Authentication failed [%s %s]: %s",
            request.method,
            request.url.path,
            exc.message,
        )
        return _build_error_response(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="UNAUTHORIZED",
            message=exc.message,
        )

    @app.exception_handler(AppError)
    async def generic_app_error_handler(
        request: Request, exc: AppError
    ) -> JSONResponse:
        """Fallback catcher for any other custom domain error inheriting from AppError."""
        logger.error(
            "Unhandled domain error [%s %s]: %s",
            request.method,
            request.url.path,
            exc.message,
        )
        return _build_error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="BAD_REQUEST",
            message=exc.message,
        )

    # =========================================================================
    # 2. Cryptographic Security Exceptions
    # =========================================================================

    @app.exception_handler(EncryptionError)
    async def encryption_error_handler(
        request: Request, exc: EncryptionError
    ) -> JSONResponse:
        logger.critical(
            "Cryptographic failure on request [%s %s]: %s",
            request.method,
            request.url.path,
            exc,
            exc_info=True,
        )
        return _build_error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="CRYPTOGRAPHY_ERROR",
            message="A cryptographic token operation failed. Please verify master keys.",
        )

    # =========================================================================
    # 3. HTTP & Validation Exceptions
    # =========================================================================

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Formats Pydantic schema validation failures into clean field maps."""
        formatted_errors: list[dict[str, Any]] = []
        for error in exc.errors():
            loc = list(error.get("loc", []))
            if loc and loc[0] in ("body", "query", "path"):
                loc.pop(0)
            field = ".".join(str(part) for part in loc) if loc else "__root__"

            formatted_errors.append(
                {
                    "field": field,
                    "message": error.get("msg", "Invalid input value."),
                    "type": error.get("type", "value_error"),
                }
            )

        logger.debug(
            "Input validation failed [%s %s]: %s",
            request.method,
            request.url.path,
            formatted_errors,
        )

        return _build_error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            error_code="VALIDATION_ERROR",
            message="Request input validation failed.",
            details=formatted_errors,
        )

    @app.exception_handler(StarletteHTTPException)
    async def starlette_http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        """Preserves standard FastAPI HTTPException status codes and details."""
        logger.warning(
            "HTTP %d error [%s %s]: %s",
            exc.status_code,
            request.method,
            request.url.path,
            exc.detail,
        )
        return _build_error_response(
            status_code=exc.status_code,
            error_code=f"HTTP_{exc.status_code}",
            message=str(exc.detail),
            headers=exc.headers,
        )

    # =========================================================================
    # 4. Global Catch-All: Unhandled Server Exceptions (500)
    # =========================================================================

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """
        Catches any unexpected Python crash.
        Logs the full stack trace internally and ensures zero secrets/paths
        are leaked to the client in production.
        """
        logger.critical(
            "CRITICAL: Unhandled internal error on [%s %s]: %s",
            request.method,
            request.url.path,
            exc,
            exc_info=True,
        )

        detail_message = (
            str(exc)
            if getattr(settings, "DEBUG", False)
            else "An unexpected internal server error occurred."
        )

        return _build_error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="INTERNAL_SERVER_ERROR",
            message=detail_message,
        )
