"""Shared fixtures.

Every test gets its own in-memory SQLite database, so tests are isolated from
each other and never touch a real ``short_url.db`` file.
"""

import os

# Must be set before the app modules are imported.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app import models as _models  # noqa: E402, F401  (registers tables)
from app.core.config import Settings, get_settings  # noqa: E402
from app.database.base import Base  # noqa: E402
from app.database.connection import build_engine, get_db  # noqa: E402
from app.main import create_app  # noqa: E402

TEST_BASE_URL = "http://localhost:8000"


@pytest.fixture()
def settings() -> Settings:
    return Settings(
        database_url="sqlite:///:memory:",
        base_url=TEST_BASE_URL,
        short_code_length=7,
        max_code_retries=5,
        max_url_length=2048,
        log_level="WARNING",
    )


@pytest.fixture()
def engine():
    test_engine = build_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=test_engine)
    yield test_engine
    test_engine.dispose()


@pytest.fixture()
def session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture()
def db_session(session_factory):
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def fastapi_app(session_factory, settings):
    application = create_app()

    def override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    application.dependency_overrides[get_db] = override_get_db
    application.dependency_overrides[get_settings] = lambda: settings
    return application


@pytest.fixture()
def client(fastapi_app):
    return TestClient(fastapi_app)
