"""Shared helpers for validating and normalizing public URL inputs."""

import ipaddress
import re
from typing import Any
from urllib.parse import urlsplit

from octopize_avatar_deploy.steps.base import ValidationError, ValidationResult, ValidationSuccess

_VALID_SCHEMES = {"http", "https"}
_HOST_LABEL_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$")


def _is_valid_hostname(hostname: str) -> bool:
    """Return whether the hostname is acceptable for PUBLIC_URL."""
    if not hostname or hostname.endswith("."):
        return False

    if hostname == "localhost":
        return True

    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        pass
    else:
        return True

    labels = hostname.split(".")
    if len(labels) < 2:
        return False

    return all(_HOST_LABEL_RE.fullmatch(label) for label in labels)


def _format_host(hostname: str, port: int | None) -> str:
    """Return the normalized host or host:port string."""
    normalized_host = f"[{hostname}]" if ":" in hostname else hostname
    if port is None:
        return normalized_host
    return f"{normalized_host}:{port}"


def normalize_public_url(value: Any) -> ValidationResult[str]:
    """Normalize PUBLIC_URL to the stored host[:port] format."""
    raw_value = str(value).strip()
    if not raw_value:
        return ValidationError("PUBLIC_URL is required and cannot be empty.")

    parsed = urlsplit(raw_value if "://" in raw_value else f"https://{raw_value}")

    if parsed.scheme and parsed.scheme not in _VALID_SCHEMES:
        return ValidationError("PUBLIC_URL must use http:// or https:// when a scheme is provided.")

    if parsed.username or parsed.password:
        return ValidationError("PUBLIC_URL must not include credentials.")

    if parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        return ValidationError("PUBLIC_URL must not include a path, query string, or fragment.")

    hostname = parsed.hostname
    if not hostname or not _is_valid_hostname(hostname):
        return ValidationError(
            "PUBLIC_URL must include a valid host or domain, such as avatar.example.com."
        )

    try:
        port = parsed.port
    except ValueError:
        return ValidationError("PUBLIC_URL contains an invalid port.")

    return ValidationSuccess(_format_host(hostname, port))


def normalize_public_base_url(value: Any) -> ValidationResult[str]:
    """Normalize a shared public base URL to scheme://host[:port]."""
    raw_value = str(value).strip()
    if not raw_value:
        return ValidationError("Public base URL is required and cannot be empty.")
    if "://" not in raw_value:
        return ValidationError("Public base URL must include http:// or https://.")

    parsed = urlsplit(raw_value)

    if parsed.scheme not in _VALID_SCHEMES:
        return ValidationError("Public base URL must use http:// or https://.")

    if parsed.username or parsed.password:
        return ValidationError("Public base URL must not include credentials.")

    if parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        return ValidationError(
            "Public base URL must not include a path, query string, or fragment."
        )

    hostname = parsed.hostname
    if not hostname or not _is_valid_hostname(hostname):
        return ValidationError(
            "Public base URL must include a valid host or domain, such as https://avatar.example.com."
        )

    try:
        port = parsed.port
    except ValueError:
        return ValidationError("Public base URL contains an invalid port.")

    return ValidationSuccess(f"{parsed.scheme.lower()}://{_format_host(hostname, port)}")


def extract_public_url_domain(value: Any) -> ValidationResult[str]:
    """Extract the normalized PUBLIC_URL host/domain portion."""
    return normalize_public_url(value)


def extract_public_url_domain_or_raise(value: Any, *, config_key: str = "PUBLIC_URL") -> str:
    """Extract the normalized PUBLIC_URL host/domain or raise a ValueError."""
    result = extract_public_url_domain(value)
    if isinstance(result, ValidationError):
        raise ValueError(f"{config_key} {value!r} is not set or invalid: {result.message}")
    return result.value
