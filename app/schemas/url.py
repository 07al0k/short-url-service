"""Request and response schemas."""

from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_serializer, field_validator

from app.core.config import get_settings
from app.services.url_validator import validate_original_url


class URLCreate(BaseModel):
    """Body of POST /api/v1/urls."""

    original_url: str = Field(
        ...,
        description="The long http:// or https:// URL to shorten.",
        examples=["https://www.example.com/products/mobile"],
    )

    @field_validator("original_url")
    @classmethod
    def _check_url(cls, value: str) -> str:
        return validate_original_url(value, max_length=get_settings().max_url_length)


class URLResponse(BaseModel):
    """A stored URL mapping."""

    original_url: str
    short_code: str
    short_url: str
    created_at: datetime

    @field_serializer("created_at")
    def _serialize_created_at(self, value: datetime) -> str:
        """Serialize UTC timestamps with a trailing Z."""
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class HealthResponse(BaseModel):
    status: str


class ValidationIssue(BaseModel):
    """One sanitized Pydantic validation issue."""

    loc: list[str | int]
    msg: str
    type: str


class ErrorResponse(BaseModel):
    """Consistent application error response, including validation failures."""

    detail: str | list[ValidationIssue]
    code: str
