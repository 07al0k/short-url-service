"""Input validation through the API. All validation failures return 422."""

import pytest
from sqlalchemy import func, select

from app.models.url import URL

ENDPOINT = "/api/v1/urls"


def _row_count(db_session):
    return db_session.execute(select(func.count()).select_from(URL)).scalar_one()


@pytest.mark.parametrize(
    "url",
    [
        "",
        "   ",
        "not a url",
        "example.com",
        "ftp://example.com/file",
        "javascript:alert(1)",
        "file:///etc/passwd",
        "data:text/html,hello",
        "http://",
        "https://user:pass@example.com",
        "http://example.com:99999",
        "http://999.999.999.999",
        "https://example.com/" + "a" * 10000,
    ],
)
def test_invalid_url_is_rejected_with_422(client, db_session, url):
    response = client.post(ENDPOINT, json={"original_url": url})

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "validation_error"
    assert body["detail"][0]["loc"] == ["body", "original_url"]
    assert _row_count(db_session) == 0


def test_missing_field_is_rejected(client):
    response = client.post(ENDPOINT, json={})

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


@pytest.mark.parametrize("value", [None, 123, 1.5, True, ["https://example.com"], {"a": 1}])
def test_wrong_data_type_is_rejected(client, value):
    response = client.post(ENDPOINT, json={"original_url": value})

    assert response.status_code == 422


@pytest.mark.parametrize("body", [[], "https://example.com", 42])
def test_wrong_body_structure_is_rejected(client, body):
    response = client.post(ENDPOINT, json=body)

    assert response.status_code == 422


def test_malformed_json_is_rejected(client):
    response = client.post(
        ENDPOINT, content="{not json", headers={"content-type": "application/json"}
    )

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_empty_body_is_rejected(client):
    assert client.post(ENDPOINT).status_code == 422


def test_error_response_does_not_leak_internals(client):
    response = client.post(ENDPOINT, json={"original_url": "javascript:alert(1)"})

    text = response.text.lower()
    assert "traceback" not in text
    assert "sqlalchemy" not in text


def test_uppercase_scheme_is_accepted(client):
    response = client.post(ENDPOINT, json={"original_url": "HTTPS://EXAMPLE.COM/Path"})

    assert response.status_code == 201
