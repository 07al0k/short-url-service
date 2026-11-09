"""Unit tests for the pure URL validation function."""

import pytest

from app.services.url_validator import validate_original_url

VALID_URLS = [
    "http://example.com",
    "https://www.example.com/products/electronics/mobile-phones/model-123",
    "https://example.com/search?q=python&page=2#results",
    "HTTP://EXAMPLE.COM/Path",
    "http://localhost:8000/docs",
    "http://127.0.0.1:5000/",
    "http://[::1]:8080/path",
    "https://sub.domain.example.co.in/a/b",
    "https://bücher.example/straße",
    "https://example.com/a%20b",
]

INVALID_URLS = [
    "",
    "   ",
    "example.com",
    "www.example.com/path",
    "//example.com/path",
    "ftp://example.com/file",
    "javascript:alert(1)",
    "JAVASCRIPT:alert(1)",
    "file:///etc/passwd",
    "data:text/html,<script>alert(1)</script>",
    "http://",
    "https:///path",
    "http:example.com",
    "http://exa mple.com",
    "http://example.com/a b",
    "http://example.com/a\nb",
    "https://user:pass@example.com",
    "https://user@example.com",
    "http://example.com:99999",
    "http://example.com:abc",
    "http://example.com:0",
    "http://[::1",
    "http://999.999.999.999",
    "http://-bad-.example",
    "http://bad_.example",
    "http://_bad.example",
    "http://exa..mple.com",
    "http://" + "a" * 64 + ".com",
]


@pytest.mark.parametrize("url", VALID_URLS)
def test_valid_urls_are_accepted_unchanged(url):
    assert validate_original_url(url) == url


@pytest.mark.parametrize("url", INVALID_URLS)
def test_invalid_urls_are_rejected(url):
    with pytest.raises(ValueError):
        validate_original_url(url)


def test_surrounding_whitespace_is_stripped():
    assert validate_original_url("  https://example.com/x \n") == "https://example.com/x"


def test_url_longer_than_limit_is_rejected():
    url = "https://example.com/" + "a" * 100
    with pytest.raises(ValueError, match="too long"):
        validate_original_url(url, max_length=50)


@pytest.mark.parametrize("value", [None, 123, 1.5, True, ["https://example.com"]])
def test_non_string_values_are_rejected(value):
    with pytest.raises(ValueError, match="must be a string"):
        validate_original_url(value)


def test_unsupported_scheme_message_mentions_http_and_https():
    with pytest.raises(ValueError, match="http and https"):
        validate_original_url("ftp://example.com/file")
