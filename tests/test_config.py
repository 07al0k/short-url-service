"""Tests for environment-based configuration."""

import pytest

from app.core.config import load_settings

ENV_VARS = [
    "DATABASE_URL",
    "BASE_URL",
    "SHORT_CODE_LENGTH",
    "MAX_CODE_RETRIES",
    "MAX_URL_LENGTH",
    "LOG_LEVEL",
]


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)


def test_defaults():
    settings = load_settings()
    assert settings.database_url == "sqlite:///./short_url.db"
    assert settings.base_url == "http://localhost:8000"
    assert settings.short_code_length == 7
    assert settings.max_code_retries == 5
    assert settings.max_url_length == 2048
    assert settings.log_level == "INFO"


def test_environment_overrides(monkeypatch):
    monkeypatch.setenv("BASE_URL", "https://sho.rt")
    monkeypatch.setenv("SHORT_CODE_LENGTH", "8")
    monkeypatch.setenv("MAX_CODE_RETRIES", "10")
    monkeypatch.setenv("LOG_LEVEL", "debug")
    settings = load_settings()
    assert settings.base_url == "https://sho.rt"
    assert settings.short_code_length == 8
    assert settings.max_code_retries == 10
    assert settings.log_level == "DEBUG"


def test_trailing_slash_is_removed_from_base_url(monkeypatch):
    monkeypatch.setenv("BASE_URL", "https://sho.rt/")
    assert load_settings().base_url == "https://sho.rt"


def test_blank_values_fall_back_to_defaults(monkeypatch):
    monkeypatch.setenv("SHORT_CODE_LENGTH", "  ")
    monkeypatch.setenv("BASE_URL", "")
    settings = load_settings()
    assert settings.short_code_length == 7
    assert settings.base_url == "http://localhost:8000"


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("SHORT_CODE_LENGTH", "abc"),
        ("SHORT_CODE_LENGTH", "2"),
        ("SHORT_CODE_LENGTH", "99"),
        ("MAX_CODE_RETRIES", "0"),
        ("MAX_URL_LENGTH", "5"),
        ("BASE_URL", "ftp://sho.rt"),
        ("BASE_URL", "sho.rt"),
        ("BASE_URL", "https://user:pass@sho.rt"),
        ("BASE_URL", "https://sho.rt/path"),
        ("BASE_URL", "https://sho.rt?query=1"),
        ("BASE_URL", "https://sho.rt:0"),
        ("LOG_LEVEL", "LOUD"),
    ],
)
def test_invalid_values_raise_a_clear_error(monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError):
        load_settings()


def test_database_url_is_not_shown_in_repr(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:s3cret@db.internal/app")
    assert "s3cret" not in repr(load_settings())
