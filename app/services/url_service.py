"""Business logic for creating, looking up and resolving short URLs."""

import logging

from app.core.config import Settings
from app.core.exceptions import (
    CodeGenerationError,
    InvalidURLError,
    ShortCodeConflictError,
    URLNotFoundError,
)
from app.models.url import URL
from app.repositories.url_repository import URLRepository
from app.services.code_generator import generate_short_code, is_valid_short_code
from app.services.url_validator import validate_original_url

logger = logging.getLogger(__name__)


class URLService:
    def __init__(self, repository: URLRepository, settings: Settings) -> None:
        self._repository = repository
        self._settings = settings

    def build_short_url(self, short_code: str) -> str:
        """Public short link for a code, built from the configured base URL."""
        return f"{self._settings.base_url}/{short_code}"

    def create_short_url(self, original_url: str) -> URL:
        """Validate the URL, generate a unique code and store the mapping."""
        try:
            cleaned_url = validate_original_url(
                original_url, max_length=self._settings.max_url_length
            )
        except ValueError as exc:
            raise InvalidURLError(str(exc)) from exc

        max_attempts = self._settings.max_code_retries
        for attempt in range(1, max_attempts + 1):
            short_code = generate_short_code(self._settings.short_code_length)

            if self._repository.short_code_exists(short_code):
                logger.warning(
                    "Short code collision (attempt %d of %d)", attempt, max_attempts
                )
                continue

            try:
                record = self._repository.create(cleaned_url, short_code)
            except ShortCodeConflictError:
                # Lost a race: another request took this code between our
                # existence check and the insert. The UNIQUE constraint caught it.
                logger.warning(
                    "Short code conflict on insert (attempt %d of %d)",
                    attempt,
                    max_attempts,
                )
                continue

            logger.info("Created short URL with code %s", record.short_code)
            return record

        logger.error("No unique short code found after %d attempts", max_attempts)
        raise CodeGenerationError()

    def get_url(self, short_code: str) -> URL:
        """Return the stored record or raise URLNotFoundError."""
        if not is_valid_short_code(short_code):
            # Cannot exist in the database, so skip the query.
            raise URLNotFoundError()
        record = self._repository.get_by_short_code(short_code)
        if record is None:
            raise URLNotFoundError()
        return record

    def resolve_original_url(self, short_code: str) -> str:
        """Return the destination for a short code, or raise URLNotFoundError."""
        return self.get_url(short_code).original_url
