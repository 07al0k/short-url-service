"""Unit tests for short code generation."""

import pytest

from app.services import code_generator
from app.services.code_generator import (
    ALPHABET,
    MAX_CODE_LENGTH,
    MIN_CODE_LENGTH,
    generate_short_code,
    is_valid_short_code,
)


@pytest.mark.parametrize("length", [7, 8, MIN_CODE_LENGTH, MAX_CODE_LENGTH])
def test_generated_code_has_requested_length(length):
    assert len(generate_short_code(length)) == length


def test_default_length_is_seven():
    assert len(generate_short_code()) == 7


def test_generated_code_uses_only_alphanumeric_characters():
    for _ in range(200):
        assert set(generate_short_code()) <= set(ALPHABET)


def test_generated_codes_are_not_repeated_in_a_large_sample():
    codes = {generate_short_code() for _ in range(2000)}
    assert len(codes) == 2000


@pytest.mark.parametrize("length", [0, 1, MIN_CODE_LENGTH - 1, MAX_CODE_LENGTH + 1, -5])
def test_invalid_length_is_rejected(length):
    with pytest.raises(ValueError):
        generate_short_code(length)


def test_reserved_codes_are_never_returned(monkeypatch):
    # First draw spells "health" (a fixed route), the second is acceptable.
    characters = iter("health" + "abcdef")
    monkeypatch.setattr(code_generator.secrets, "choice", lambda _alphabet: next(characters))
    assert generate_short_code(6) == "abcdef"


@pytest.mark.parametrize("code", ["aB91xYz", "K8pQ2mR", "x7N4bL9", "abcd", "A" * 16])
def test_valid_short_codes(code):
    assert is_valid_short_code(code)


@pytest.mark.parametrize(
    "code", ["", "favicon.ico", "has space", "bad-code", "a" * 17, "é", "abc\n"]
)
def test_invalid_short_codes(code):
    assert not is_valid_short_code(code)
