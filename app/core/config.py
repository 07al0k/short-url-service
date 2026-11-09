"""Application configuration loaded from environment variables.

Values come from the process environment first and fall back to a ``.env``
file in the project root (see ``.env.example``). Nothing secret is hard-coded.
"""

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv

from app.services.url_validator import validate_original_url

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Variables that are already set in the real environment always win over .env.
load_dotenv(PROJECT_ROOT / ".env", override=False)

VALID_LOG_LEVELS = frozenset({"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"})

DEFAULT_DATABASE_URL = "sqlite:///./short_url.db"
DEFAULT_BASE_URL = "http://localhost:8000"


@dataclass(frozen=True)
class Settings:
    """Immutable application settings."""

    # repr=False keeps credentials (e.g. a future PostgreSQL URL) out of logs.
    database_url: str = field(repr=False)
    base_url: str
    short_code_length: int
    max_code_retries: int
    max_url_length: int
    log_level: str


def _read_str(name: str, default: str) -> str:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip()


def _read_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw!r}.") from exc
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}, got {value}.")
    return value


def load_settings() -> Settings:
    """Read and validate settings from the environment.

    Raises ValueError with a clear message when a value is invalid, so a bad
    configuration fails at start-up instead of at request time.
    """
    base_url = _read_str("BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    try:
        validate_original_url(base_url)
        base_parts = urlsplit(base_url)
    except ValueError as exc:
        raise ValueError("BASE_URL must be a valid absolute http(s) URL.") from exc

    if base_parts.path or base_parts.query or base_parts.fragment:
        raise ValueError("BASE_URL must contain only the scheme, host and optional port.")

    log_level = _read_str("LOG_LEVEL", "INFO").upper()
    if log_level not in VALID_LOG_LEVELS:
        allowed = ", ".join(sorted(VALID_LOG_LEVELS))
        raise ValueError(f"LOG_LEVEL must be one of: {allowed}.")

    return Settings(
        database_url=_read_str("DATABASE_URL", DEFAULT_DATABASE_URL),
        base_url=base_url,
        short_code_length=_read_int("SHORT_CODE_LENGTH", 7, 4, 16),
        max_code_retries=_read_int("MAX_CODE_RETRIES", 5, 1, 100),
        max_url_length=_read_int("MAX_URL_LENGTH", 2048, 16, 8192),
        log_level=log_level,
    )


@lru_cache
def get_settings() -> Settings:
    """Cached settings, usable as a FastAPI dependency."""
    return load_settings()
