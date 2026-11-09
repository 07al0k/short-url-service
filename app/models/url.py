"""The ``urls`` table: one row per shortened URL."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from app.database.base import Base


def utcnow() -> datetime:
    """Current time as a timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator):
    """Stores datetimes as naive UTC and always returns aware UTC datetimes.

    SQLite has no timezone support and silently drops tzinfo, which would make
    timestamps ambiguous after a round trip. This type makes the rule explicit:
    only aware datetimes go in, and aware UTC datetimes come out.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("Naive datetimes are not allowed; use aware UTC datetimes.")
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc)


class URL(Base):
    __tablename__ = "urls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    original_url: Mapped[str] = mapped_column(Text, nullable=False)
    # unique=True + index=True creates a UNIQUE index, which both enforces
    # uniqueness and speeds up the lookups done on every redirect.
    short_code: Mapped[str] = mapped_column(
        String(16), nullable=False, unique=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, nullable=False, default=utcnow
    )
    # Reserved for future update support; stays NULL until a record is modified.
    updated_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime, nullable=True, default=None, onupdate=utcnow
    )

    def __repr__(self) -> str:
        return f"URL(id={self.id!r}, short_code={self.short_code!r})"
