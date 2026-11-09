"""Database access for URL records.

This is the only layer that talks to SQLAlchemy. Low-level database errors are
logged here and translated into application exceptions, so nothing above this
layer (or in an API response) ever sees SQL or driver details.
"""

import logging

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.exceptions import (
    AppError,
    DatabaseError,
    DatabaseUnavailableError,
    ShortCodeConflictError,
)
from app.models.url import URL, utcnow

logger = logging.getLogger(__name__)


def _translate(exc: SQLAlchemyError) -> AppError:
    if isinstance(exc, OperationalError):
        return DatabaseUnavailableError()
    return DatabaseError()


class URLRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_short_code(self, short_code: str) -> URL | None:
        try:
            statement = select(URL).where(URL.short_code == short_code)
            return self._db.execute(statement).scalar_one_or_none()
        except SQLAlchemyError as exc:
            logger.exception("Database error while looking up a short code")
            raise _translate(exc) from exc

    def short_code_exists(self, short_code: str) -> bool:
        try:
            statement = select(URL.id).where(URL.short_code == short_code).limit(1)
            return self._db.execute(statement).first() is not None
        except SQLAlchemyError as exc:
            logger.exception("Database error while checking a short code")
            raise _translate(exc) from exc

    def create(self, original_url: str, short_code: str) -> URL:
        """Insert a new record and commit.

        Raises ShortCodeConflictError if the UNIQUE constraint rejects the code
        (another request may have inserted it after our existence check).
        Any other failure rolls the transaction back and raises a controlled
        application error.
        """
        record = URL(
            original_url=original_url,
            short_code=short_code,
            created_at=utcnow(),
        )
        try:
            self._db.add(record)
            self._db.commit()
        except IntegrityError as exc:
            self._db.rollback()
            raise ShortCodeConflictError() from exc
        except SQLAlchemyError as exc:
            self._db.rollback()
            logger.exception("Database error while saving a URL record")
            raise _translate(exc) from exc
        return record
