"""Short code generation using a cryptographically secure random source."""

import re
import secrets
import string

ALPHABET = string.ascii_letters + string.digits
MIN_CODE_LENGTH = 4
MAX_CODE_LENGTH = 16  # matches the VARCHAR(16) column

# Codes that would collide with fixed routes such as /health or /docs.
RESERVED_CODES = frozenset({"api", "docs", "redoc", "health"})

_VALID_CODE = re.compile(r"[A-Za-z0-9]{4,16}")


def generate_short_code(length: int = 7) -> str:
    """Return a random alphanumeric code of the requested length.

    Randomness alone does not guarantee uniqueness. The caller must still check
    the database, and the UNIQUE constraint on the column is the final guard.
    """
    if not MIN_CODE_LENGTH <= length <= MAX_CODE_LENGTH:
        raise ValueError(
            f"length must be between {MIN_CODE_LENGTH} and {MAX_CODE_LENGTH}."
        )
    while True:
        code = "".join(secrets.choice(ALPHABET) for _ in range(length))
        if code not in RESERVED_CODES:
            return code


def is_valid_short_code(code: str) -> bool:
    """True if ``code`` could have been produced by this service.

    Used to answer obviously malformed lookups (``favicon.ico``, very long
    strings) with a 404 without touching the database.
    """
    return _VALID_CODE.fullmatch(code) is not None
