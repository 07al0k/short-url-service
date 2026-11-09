"""Service-layer tests: validation, collision handling and lookups."""

from dataclasses import replace

import pytest

from app.core.exceptions import CodeGenerationError, InvalidURLError, URLNotFoundError
from app.repositories.url_repository import URLRepository
from app.services.url_service import URLService

GENERATOR = "app.services.url_service.generate_short_code"


@pytest.fixture()
def repository(db_session):
    return URLRepository(db_session)


@pytest.fixture()
def service(repository, settings):
    return URLService(repository, settings)


def test_create_returns_a_stored_record(service, repository):
    record = service.create_short_url("https://example.com/page")

    assert repository.get_by_short_code(record.short_code).original_url == "https://example.com/page"


def test_invalid_url_raises_invalid_url_error(service):
    with pytest.raises(InvalidURLError):
        service.create_short_url("javascript:alert(1)")


def test_build_short_url_uses_the_base_url(service):
    assert service.build_short_url("aB91xYz") == "http://localhost:8000/aB91xYz"


def test_collision_is_retried_with_a_new_code(service, repository, monkeypatch):
    repository.create("https://existing.example", "AAAAAAA")
    codes = iter(["AAAAAAA", "AAAAAAA", "BBBBBBB"])
    monkeypatch.setattr(GENERATOR, lambda length: next(codes))

    record = service.create_short_url("https://new.example")

    assert record.short_code == "BBBBBBB"
    assert repository.get_by_short_code("AAAAAAA").original_url == "https://existing.example"


def test_conflict_detected_only_by_the_database_is_also_retried(service, repository, monkeypatch):
    # Simulates a race: the existence check says "free" but the insert hits the
    # UNIQUE constraint because another request took the code in between.
    repository.create("https://existing.example", "AAAAAAA")
    monkeypatch.setattr(repository, "short_code_exists", lambda code: False)
    codes = iter(["AAAAAAA", "BBBBBBB"])
    monkeypatch.setattr(GENERATOR, lambda length: next(codes))

    record = service.create_short_url("https://new.example")

    assert record.short_code == "BBBBBBB"


def test_gives_up_after_the_maximum_number_of_retries(repository, settings, monkeypatch):
    repository.create("https://existing.example", "AAAAAAA")
    calls = []

    def always_taken(length):
        calls.append(length)
        return "AAAAAAA"

    monkeypatch.setattr(GENERATOR, always_taken)
    service = URLService(repository, replace(settings, max_code_retries=3))

    with pytest.raises(CodeGenerationError):
        service.create_short_url("https://new.example")

    assert len(calls) == 3


def test_configured_code_length_is_used(repository, settings):
    service = URLService(repository, replace(settings, short_code_length=8))

    assert len(service.create_short_url("https://example.com").short_code) == 8


def test_get_url_returns_the_record(service):
    created = service.create_short_url("https://example.com/x")

    assert service.get_url(created.short_code).original_url == "https://example.com/x"


def test_get_url_raises_for_unknown_code(service):
    with pytest.raises(URLNotFoundError):
        service.get_url("unknown1")


@pytest.mark.parametrize("code", ["", "a", "abc", "favicon.ico", "has space", "a" * 40])
def test_malformed_codes_are_not_found_without_a_query(service, repository, monkeypatch, code):
    def must_not_be_called(_code):
        raise AssertionError("the database should not be queried")

    monkeypatch.setattr(repository, "get_by_short_code", must_not_be_called)

    with pytest.raises(URLNotFoundError):
        service.get_url(code)


def test_resolve_original_url(service):
    created = service.create_short_url("https://example.com/target")

    assert service.resolve_original_url(created.short_code) == "https://example.com/target"
