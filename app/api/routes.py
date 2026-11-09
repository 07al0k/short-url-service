"""HTTP endpoints.

Routes only translate between HTTP and the service layer: no business logic and
no database code lives here.

The redirect route (``/{short_code}``) matches any single path segment, so it
must be registered after every other fixed route. ``app/main.py`` does this.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.database.connection import get_db
from app.models.url import URL
from app.repositories.url_repository import URLRepository
from app.schemas.url import ErrorResponse, HealthResponse, URLCreate, URLResponse
from app.services.url_service import URLService

DbSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


def get_url_service(db: DbSession, settings: AppSettings) -> URLService:
    return URLService(URLRepository(db), settings)


ServiceDep = Annotated[URLService, Depends(get_url_service)]

NOT_FOUND = {404: {"model": ErrorResponse, "description": "Short URL not found."}}
VALIDATION_ERROR = {
    422: {"model": ErrorResponse, "description": "Request validation failed."}
}
SERVER_ERRORS = {
    500: {"model": ErrorResponse, "description": "Unexpected server or database error."},
    503: {"model": ErrorResponse, "description": "Service temporarily unavailable."},
}


def _to_response(record: URL, service: URLService) -> URLResponse:
    return URLResponse(
        original_url=record.original_url,
        short_code=record.short_code,
        short_url=service.build_short_url(record.short_code),
        created_at=record.created_at,
    )


health_router = APIRouter(tags=["health"])
api_router = APIRouter(prefix="/api/v1", tags=["urls"])
redirect_router = APIRouter(tags=["redirect"])


@health_router.get("/health", response_model=HealthResponse, summary="Health check")
async def health_check() -> HealthResponse:
    """Liveness probe. Reveals nothing about the database or configuration."""
    return HealthResponse(status="healthy")


@api_router.post(
    "/urls",
    response_model=URLResponse,
    status_code=status.HTTP_201_CREATED,
    responses={**VALIDATION_ERROR, **SERVER_ERRORS},
    summary="Create a short URL",
)
def create_short_url(payload: URLCreate, service: ServiceDep) -> URLResponse:
    """Validate a long URL, generate a unique short code and store the mapping.

    Invalid input (empty, missing, wrong type, bad format, or a scheme other
    than http/https) is rejected with **422**.
    """
    record = service.create_short_url(payload.original_url)
    return _to_response(record, service)


@api_router.get(
    "/urls/{short_code}",
    response_model=URLResponse,
    responses={**NOT_FOUND, **SERVER_ERRORS},
    summary="Get URL details",
)
def get_url_details(short_code: str, service: ServiceDep) -> URLResponse:
    """Return the stored mapping for a short code without redirecting."""
    record = service.get_url(short_code)
    return _to_response(record, service)


@redirect_router.get(
    "/{short_code}",
    response_class=RedirectResponse,
    response_model=None,
    status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    responses={**NOT_FOUND, **SERVER_ERRORS},
    summary="Redirect to the original URL",
)
def redirect_to_original(short_code: str, service: ServiceDep) -> RedirectResponse:
    """Redirect (HTTP 307) to the original URL, or return 404 if unknown."""
    original_url = service.resolve_original_url(short_code)
    return RedirectResponse(
        url=original_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT
    )
