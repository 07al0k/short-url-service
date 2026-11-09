"""POST /api/v1/urls"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.models.url import URL
from app.services.code_generator import ALPHABET

ENDPOINT = "/api/v1/urls"


def _stored(db_session, short_code):
    return db_session.execute(select(URL).where(URL.short_code == short_code)).scalar_one()


def test_create_with_http_url(client):
    response = client.post(ENDPOINT, json={"original_url": "http://example.com/page"})

    assert response.status_code == 201
    body = response.json()
    assert body["original_url"] == "http://example.com/page"
    assert set(body) == {"original_url", "short_code", "short_url", "created_at"}


def test_create_with_https_url(client):
    url = "https://www.example.com/products/mobile"
    response = client.post(ENDPOINT, json={"original_url": url})

    assert response.status_code == 201
    assert response.json()["original_url"] == url


def test_short_code_format(client):
    body = client.post(ENDPOINT, json={"original_url": "https://example.com"}).json()

    assert len(body["short_code"]) == 7
    assert set(body["short_code"]) <= set(ALPHABET)


def test_short_url_is_built_from_the_configured_base_url(client):
    body = client.post(ENDPOINT, json={"original_url": "https://example.com"}).json()

    assert body["short_url"] == f"http://localhost:8000/{body['short_code']}"


def test_original_url_is_returned_without_modification(client):
    # No normalisation such as a trailing slash being added.
    response = client.post(ENDPOINT, json={"original_url": "https://www.example.com"})

    assert response.json()["original_url"] == "https://www.example.com"


def test_surrounding_whitespace_is_trimmed(client):
    response = client.post(ENDPOINT, json={"original_url": "  https://example.com/x  "})

    assert response.status_code == 201
    assert response.json()["original_url"] == "https://example.com/x"


def test_record_is_persisted(client, db_session):
    body = client.post(ENDPOINT, json={"original_url": "https://example.com/saved"}).json()

    record = _stored(db_session, body["short_code"])
    assert record.original_url == "https://example.com/saved"
    assert record.created_at is not None


def test_created_at_is_utc_iso_8601_and_recent(client, db_session):
    before = datetime.now(timezone.utc) - timedelta(seconds=2)
    body = client.post(ENDPOINT, json={"original_url": "https://example.com"}).json()
    after = datetime.now(timezone.utc) + timedelta(seconds=2)

    assert body["created_at"].endswith("Z")
    created_at = datetime.fromisoformat(body["created_at"])
    assert created_at.utcoffset() == timedelta(0)
    assert before <= created_at <= after

    stored = _stored(db_session, body["short_code"]).created_at
    assert stored.tzinfo is not None
    assert stored.utcoffset() == timedelta(0)


def test_same_url_submitted_twice_creates_two_distinct_codes(client, db_session):
    payload = {"original_url": "https://example.com/same"}

    first = client.post(ENDPOINT, json=payload).json()
    second = client.post(ENDPOINT, json=payload).json()

    assert first["short_code"] != second["short_code"]
    assert db_session.execute(select(func.count()).select_from(URL)).scalar_one() == 2


def test_many_creations_all_get_unique_codes(client):
    codes = {
        client.post(ENDPOINT, json={"original_url": f"https://example.com/{i}"}).json()[
            "short_code"
        ]
        for i in range(50)
    }

    assert len(codes) == 50
