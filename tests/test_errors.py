"""Controlled error handling: database failures and unexpected exceptions."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.database.connection import build_engine, get_db
from app.models.url import URL
from app.services import url_service
from app.services.url_service import URLService

ENDPOINT = "/api/v1/urls"
INTERNAL_TERMS = ("sqlite", "sqlalchemy", "no such table", "traceback", "secret")


def _assert_no_internal_details(text):
    lowered = text.lower()
    for term in INTERNAL_TERMS:
        assert term not in lowered


@pytest.fixture()
def broken_database_app(fastapi_app):
    """An app whose database has no tables, so every query fails."""
    empty_engine = build_engine("sqlite:///:memory:")
    factory = sessionmaker(bind=empty_engine, autoflush=False, expire_on_commit=False)

    def override_get_db():
        session = factory()
        try:
            yield session
        finally:
            session.close()

    fastapi_app.dependency_overrides[get_db] = override_get_db
    yield fastapi_app
    empty_engine.dispose()


def test_database_unavailable_on_create_returns_controlled_503(broken_database_app):
    client = TestClient(broken_database_app)

    response = client.post(ENDPOINT, json={"original_url": "https://example.com"})

    assert response.status_code == 503
    assert response.json()["code"] == "database_unavailable"
    _assert_no_internal_details(response.text)


def test_database_unavailable_on_redirect_returns_controlled_503(broken_database_app):
    client = TestClient(broken_database_app)

    response = client.get("/abc1234", follow_redirects=False)

    assert response.status_code == 503
    _assert_no_internal_details(response.text)


def test_database_unavailable_on_details_returns_controlled_503(broken_database_app):
    client = TestClient(broken_database_app)

    response = client.get(f"{ENDPOINT}/abc1234")

    assert response.status_code == 503
    _assert_no_internal_details(response.text)


def test_write_failure_rolls_back_and_returns_controlled_500(client, db_session, monkeypatch):
    rollbacks = []
    original_rollback = Session.rollback

    def failing_commit(self):
        raise SQLAlchemyError("secret internal detail")

    def tracking_rollback(self):
        rollbacks.append(True)
        return original_rollback(self)

    with monkeypatch.context() as patch:
        patch.setattr(Session, "commit", failing_commit)
        patch.setattr(Session, "rollback", tracking_rollback)
        response = client.post(ENDPOINT, json={"original_url": "https://example.com"})

    assert response.status_code == 500
    assert response.json()["code"] == "database_error"
    _assert_no_internal_details(response.text)
    assert rollbacks, "the failed transaction must be rolled back"
    assert db_session.execute(select(func.count()).select_from(URL)).scalar_one() == 0


def test_service_still_works_after_a_failed_write(client, monkeypatch):
    def failing_commit(self):
        raise SQLAlchemyError("simulated write failure")

    with monkeypatch.context() as patch:
        patch.setattr(Session, "commit", failing_commit)
        assert client.post(ENDPOINT, json={"original_url": "https://example.com/1"}).status_code == 500

    assert client.post(ENDPOINT, json={"original_url": "https://example.com/2"}).status_code == 201


def test_exhausted_code_generation_returns_503(client, monkeypatch):
    # Pre-existing record whose code the generator keeps returning.
    created = client.post(ENDPOINT, json={"original_url": "https://example.com"}).json()
    monkeypatch.setattr(url_service, "generate_short_code", lambda length: created["short_code"])

    response = client.post(ENDPOINT, json={"original_url": "https://example.com/other"})

    assert response.status_code == 503
    assert response.json()["code"] == "code_generation_failed"


def test_unexpected_exception_returns_generic_500(fastapi_app, monkeypatch):
    def explode(self, original_url):
        raise RuntimeError("secret stack detail")

    monkeypatch.setattr(URLService, "create_short_url", explode)
    client = TestClient(fastapi_app, raise_server_exceptions=False)

    response = client.post(ENDPOINT, json={"original_url": "https://example.com"})

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error.", "code": "internal_error"}
    _assert_no_internal_details(response.text)


def test_unknown_route_returns_json_404(client):
    response = client.get("/api/v1/nothing/here")

    assert response.status_code == 404
    assert response.json()["code"] == "http_error"


def test_wrong_method_returns_json_405(client):
    response = client.delete(ENDPOINT)

    assert response.status_code == 405
    assert response.json()["code"] == "http_error"
