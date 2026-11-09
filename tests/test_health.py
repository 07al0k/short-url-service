"""Health check and API documentation routes."""


def test_health_check(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_health_is_not_treated_as_a_short_code(client):
    # /health is registered before the catch-all /{short_code} route.
    response = client.get("/health", follow_redirects=False)

    assert response.status_code == 200


def test_health_does_not_expose_configuration(client):
    text = client.get("/health").text.lower()

    assert "sqlite" not in text
    assert "database" not in text
    assert "localhost" not in text


def test_interactive_docs_are_served(client):
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200


def test_openapi_documents_every_endpoint(client):
    paths = client.get("/openapi.json").json()["paths"]

    assert "post" in paths["/api/v1/urls"]
    assert "get" in paths["/api/v1/urls/{short_code}"]
    assert "get" in paths["/{short_code}"]
    assert "get" in paths["/health"]


def test_openapi_documents_the_custom_validation_error_schema(client):
    schema = client.get("/openapi.json").json()
    response_schema = schema["paths"]["/api/v1/urls"]["post"]["responses"]["422"]

    assert response_schema["content"]["application/json"]["schema"]["$ref"] == (
        "#/components/schemas/ErrorResponse"
    )
