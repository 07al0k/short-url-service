"""Engine, session factory and FastAPI session dependency."""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.database.base import Base


def build_engine(database_url: str) -> Engine:
    """Create an engine with sensible defaults for the given database URL."""
    options: dict = {}
    url = make_url(database_url)
    if url.get_backend_name() == "sqlite":
        # FastAPI runs sync endpoints in a thread pool, so SQLite connections
        # must be usable from threads other than the one that created them.
        options["connect_args"] = {"check_same_thread": False}
        if url.database in (None, "", ":memory:"):
            # One shared connection, otherwise every connection would get its
            # own empty in-memory database (used by the test suite).
            options["poolclass"] = StaticPool
    return create_engine(database_url, **options)


engine = build_engine(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request, always closed afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create tables that do not exist yet. Existing data is left untouched."""
    from app import models  # noqa: F401  (registers models on Base.metadata)

    Base.metadata.create_all(bind=engine)
