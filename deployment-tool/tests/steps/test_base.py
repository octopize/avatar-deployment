#!/usr/bin/env python3
"""Tests for base deployment step class."""

import base64

import pytest

from octopize_avatar_deploy.steps.base import DeploymentStep


class TestDeploymentStepBase:
    """Test the base DeploymentStep class."""

    def test_generate_secret_token(self):
        """Test secret token generation."""
        token1 = DeploymentStep.generate_secret_token()
        token2 = DeploymentStep.generate_secret_token()

        assert isinstance(token1, str)
        assert len(token1) > 0
        assert token1 != token2

    def test_generate_secret_urlsafe(self):
        """Test URL-safe secret generation."""
        token = DeploymentStep.generate_secret_urlsafe(32)

        assert isinstance(token, str)
        assert len(token) > 0

    def test_generate_encryption_key(self):
        """Test encryption key generation."""
        key1 = DeploymentStep.generate_encryption_key()
        key2 = DeploymentStep.generate_encryption_key()

        assert isinstance(key1, str)
        assert len(key1) > 0
        assert key1 != key2

        # Verify it's valid base64
        try:
            decoded = base64.urlsafe_b64decode(key1)
            assert len(decoded) == 32
        except Exception:
            pytest.fail("Generated key is not valid URL-safe base64")

    def test_generate_base64_key(self):
        """Test base64 key generation."""
        key = DeploymentStep.generate_base64_key(32)

        assert isinstance(key, str)
        assert len(key) > 0

        # Verify it's valid base64
        try:
            decoded = base64.b64decode(key)
            assert len(decoded) == 32
        except Exception:
            pytest.fail("Generated key is not valid base64")

    def test_generate_base64_key_different_sizes(self):
        """Test base64 key generation with different byte sizes."""
        key16 = DeploymentStep.generate_base64_key(16)
        key64 = DeploymentStep.generate_base64_key(64)

        decoded16 = base64.b64decode(key16)
        decoded64 = base64.b64decode(key64)

        assert len(decoded16) == 16
        assert len(decoded64) == 64
