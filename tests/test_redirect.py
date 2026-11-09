"""GET /{short_code}"""


def _create(client, url):
    response = client.post("/api/v1/urls", json={"original_url": url})
    return response.json()["short_code"]


def test_existing_code_redirects_to_original_url(client):
    code = _create(client, "https://www.example.com/products/mobile")

    response = client.get(f"/{code}", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "https://www.example.com/products/mobile"


def test_redirect_preserves_query_string(client):
    url = "https://example.com/search?q=python&page=2"
    code = _create(client, url)

    response = client.get(f"/{code}", follow_redirects=False)

    assert response.headers["location"] == url


def test_redirect_uses_temporary_redirect_status(client):
    code = _create(client, "https://example.com")

    assert client.get(f"/{code}", follow_redirects=False).status_code == 307


def test_unknown_code_returns_404_with_meaningful_error(client):
    response = client.get("/doesNotExist", follow_redirects=False)

    assert response.status_code == 404
    assert response.json() == {"detail": "Short URL not found.", "code": "short_url_not_found"}


def test_malformed_code_returns_404(client):
    assert client.get("/favicon.ico", follow_redirects=False).status_code == 404


def test_redirect_survives_multiple_requests(client):
    code = _create(client, "https://example.com/again")

    for _ in range(3):
        response = client.get(f"/{code}", follow_redirects=False)
        assert response.status_code == 307
