"""Application-level exceptions and the handlers that turn them into responses.

Every error response has the same JSON shape:

    {"detail": <message or list of validation problems>, "code": "<machine_code>"}

Internal details (stack traces, SQL, file paths, credentials) are logged on the
server and never sent to the client.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Base class for errors that map to a controlled HTTP response."""

    status_code: int = 500
    code: str = "internal_error"
    message: str = "An unexpected error occurred."

    def __init__(self, message: str | None = None) -> None:
        if message is not None:
            self.message = message
        super().__init__(self.message)


class InvalidURLError(AppError):
    status_code = 422
    code = "invalid_url"
    message = "The submitted URL is not valid."


class URLNotFoundError(AppError):
    status_code = 404
    code = "short_url_not_found"
    message = "Short URL not found."


class ShortCodeConflictError(AppError):
    """A generated short code already exists. Handled by retrying, never shown."""

    status_code = 409
    code = "short_code_conflict"
    message = "The generated short code is already in use."


class CodeGenerationError(AppError):
    status_code = 503
    code = "code_generation_failed"
    message = "Could not generate a unique short code. Please try again."


class DatabaseUnavailableError(AppError):
    status_code = 503
    code = "database_unavailable"
    message = "The service is temporarily unavailable. Please try again later."


class DatabaseError(AppError):
    status_code = 500
    code = "database_error"
    message = "A database error occurred. The request was not completed."


async def _handle_app_error(request: Request, exc: AppError) -> JSONResponse:
    if exc.status_code >= 500:
        logger.error(
            "%s while handling %s %s: %s",
            exc.code,
            request.method,
            request.url.path,
            exc.message,
        )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message, "code": exc.code},
    )


async def _handle_validation_error(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    # Only loc/msg/type are returned: the raw error objects can carry the
    # submitted input or Python exception instances that are not JSON safe.
    problems = [
        {
            "loc": list(error.get("loc", ())),
            "msg": str(error.get("msg", "")),
            "type": str(error.get("type", "")),
        }
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={"detail": problems, "code": "validation_error"},
    )


async def _handle_http_exception(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "code": "http_error"},
        headers=getattr(exc, "headers", None),
    )


async def _handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(
        "Unhandled error while handling %s %s", request.method, request.url.path
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error.", "code": "internal_error"},
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Attach all error handlers to the application."""
    app.add_exception_handler(AppError, _handle_app_error)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, _handle_http_exception)
    app.add_exception_handler(Exception, _handle_unexpected_error)
