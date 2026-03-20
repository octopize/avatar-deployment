"""Tests for shared public URL validation helpers."""

import pytest

from octopize_avatar_deploy.public_url import (
    extract_public_url_domain_or_raise,
    normalize_public_base_url,
    normalize_public_url,
)
from octopize_avatar_deploy.steps.base import ValidationError, ValidationSuccess


class TestNormalizePublicUrl:
    """Test shared PUBLIC_URL validation and normalization."""

    @pytest.mark.parametrize(
        ("raw_value", "expected"),
        [
            ("avatar.example.com", "avatar.example.com"),
            ("https://avatar.example.com", "avatar.example.com"),
            ("https://avatar.example.com/", "avatar.example.com"),
            ("http://staging.octopize.tech", "staging.octopize.tech"),
            ("https://Avatar.Example.com:8443/", "avatar.example.com:8443"),
            ("https://127.0.0.1:9443/", "127.0.0.1:9443"),
        ],
    )
    def test_valid_values(self, raw_value, expected):
        """Test valid PUBLIC_URL values normalize to host[:port]."""
        result = normalize_public_url(raw_value)

        assert isinstance(result, ValidationSuccess)
        assert result.value == expected

    @pytest.mark.parametrize(
        ("raw_value", "message"),
        [
            ("", "PUBLIC_URL is required"),
            ("avatar", "PUBLIC_URL must include a valid host or domain"),
            ("https://avatar.example.com/app", "PUBLIC_URL must not include a path"),
            ("ftp://avatar.example.com", "PUBLIC_URL must use http:// or https://"),
            ("https://user:pass@avatar.example.com", "PUBLIC_URL must not include credentials"),
        ],
    )
    def test_invalid_values(self, raw_value, message):
        """Test malformed PUBLIC_URL values are rejected."""
        result = normalize_public_url(raw_value)

        assert isinstance(result, ValidationError)
        assert message in result.message

    def test_extract_public_url_domain_or_raise(self):
        """Test extracting the normalized PUBLIC_URL host/domain."""
        assert extract_public_url_domain_or_raise("https://avatar.example.com:8443/") == (
            "avatar.example.com:8443"
        )

    def test_extract_public_url_domain_or_raise_rejects_invalid_values(self):
        """Test extraction raises on malformed PUBLIC_URL input."""
        with pytest.raises(
            ValueError, match="PUBLIC_URL .* is not set or invalid: PUBLIC_URL must include"
        ):
            extract_public_url_domain_or_raise("avatar")


class TestNormalizePublicBaseUrl:
    """Test shared public-base URL validation for generate-env topology prompts."""

    @pytest.mark.parametrize(
        ("raw_value", "expected"),
        [
            ("https://avatar.example.com", "https://avatar.example.com"),
            ("https://avatar.example.com/", "https://avatar.example.com"),
            ("http://avatar.example.com:8080/", "http://avatar.example.com:8080"),
        ],
    )
    def test_valid_values(self, raw_value, expected):
        result = normalize_public_base_url(raw_value)

        assert isinstance(result, ValidationSuccess)
        assert result.value == expected

    @pytest.mark.parametrize(
        ("raw_value", "message"),
        [
            ("", "Public base URL is required"),
            ("avatar.example.com", "Public base URL must include http:// or https://"),
            ("https://avatar.example.com/app", "Public base URL must not include a path"),
        ],
    )
    def test_invalid_values(self, raw_value, message):
        result = normalize_public_base_url(raw_value)

        assert isinstance(result, ValidationError)
        assert message in result.message
