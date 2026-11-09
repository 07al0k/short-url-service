"""Pure URL validation (no framework or database dependencies).

A URL that passes validation is only *well formed* and uses http or https.
That does not make it safe: this service never fetches the URLs it stores, and
users should still treat shortened links with the same caution as any other.
"""

import ipaddress
import re
from urllib.parse import urlsplit

ALLOWED_SCHEMES = frozenset({"http", "https"})
DEFAULT_MAX_URL_LENGTH = 2048

_FORBIDDEN_CHARS = re.compile(r"[\s\x00-\x1f\x7f]")
_HOST_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", re.IGNORECASE)
_ALL_DIGITS_AND_DOTS = re.compile(r"[0-9.]+")


def validate_original_url(value: object, max_length: int = DEFAULT_MAX_URL_LENGTH) -> str:
    """Return the cleaned URL, or raise ValueError with a client-safe message."""
    if not isinstance(value, str):
        raise ValueError("URL must be a string.")

    url = value.strip()
    if not url:
        raise ValueError("URL must not be empty.")
    if len(url) > max_length:
        raise ValueError(f"URL is too long (maximum {max_length} characters).")
    if _FORBIDDEN_CHARS.search(url):
        raise ValueError("URL must not contain spaces or control characters.")

    try:
        parts = urlsplit(url)
        host = parts.hostname
        port = parts.port
    except ValueError as exc:
        raise ValueError("Invalid URL format.") from exc

    scheme = parts.scheme.lower()
    if not scheme:
        raise ValueError("URL must start with http:// or https://.")
    if scheme not in ALLOWED_SCHEMES:
        raise ValueError("Unsupported URL scheme. Only http and https are allowed.")
    if parts.username is not None or parts.password is not None:
        raise ValueError("URLs containing credentials are not allowed.")
    if not host:
        raise ValueError("URL must include a host name.")
    if not _is_valid_host(host):
        raise ValueError("URL contains an invalid host name.")
    if port == 0:
        raise ValueError("URL contains an invalid port.")

    return url


def _is_valid_host(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        pass

    candidate = host[:-1] if host.endswith(".") else host
    try:
        ascii_host = candidate.encode("idna").decode("ascii")
    except UnicodeError:
        return False

    if not ascii_host or len(ascii_host) > 253:
        return False
    if _ALL_DIGITS_AND_DOTS.fullmatch(ascii_host):
        # Looks like an IPv4 address but was rejected above (e.g. 999.1.1.1).
        return False
    return all(_HOST_LABEL.fullmatch(label) for label in ascii_host.split("."))
