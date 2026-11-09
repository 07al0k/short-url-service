"""GET /api/v1/urls/{short_code}"""

ENDPOINT = "/api/v1/urls"


def _create(client, url="https://www.example.com/products/mobile"):
    return client.post(ENDPOINT, json={"original_url": url}).json()


def test_returns_details_for_existing_code(client):
    created = _create(client)

    response = client.get(f"{ENDPOINT}/{created['short_code']}")

    assert response.status_code == 200
    assert response.json() == created


def test_response_has_the_expected_fields(client):
    created = _create(client)

    body = client.get(f"{ENDPOINT}/{created['short_code']}").json()

    assert set(body) == {"original_url", "short_code", "short_url", "created_at"}
    assert body["short_url"] == f"http://localhost:8000/{created['short_code']}"


def test_does_not_redirect(client):
    created = _create(client)

    response = client.get(f"{ENDPOINT}/{created['short_code']}", follow_redirects=False)

    assert response.status_code == 200
    assert "location" not in response.headers


def test_unknown_code_returns_404(client):
    response = client.get(f"{ENDPOINT}/doesNotExist")

    assert response.status_code == 404
    assert response.json() == {"detail": "Short URL not found.", "code": "short_url_not_found"}


def test_malformed_codes_return_404(client):
    for code in ["bad.code", "bad-code", "a" * 40]:
        assert client.get(f"{ENDPOINT}/{code}").status_code == 404


def test_codes_are_case_sensitive(client):
    created = _create(client)
    swapped = created["short_code"].swapcase()

    if swapped != created["short_code"]:
        assert client.get(f"{ENDPOINT}/{swapped}").status_code == 404
