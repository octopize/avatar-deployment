#!/usr/bin/env python3
"""Tests for storage configuration step."""

import base64

import pytest

from octopize_avatar_deploy.steps import StorageStep


class TestStorageStep:
    """Test the StorageStep."""

    @pytest.fixture
    def defaults(self):
        """Provide storage defaults."""
        return {
            "application": {
                "dataset_expiration": "30d",
                "email_authentication": True,
            }
        }

    @pytest.fixture
    def step(self, tmp_path, defaults):
        """Create a StorageStep instance."""
        config = {}
        return StorageStep(tmp_path, defaults, config, interactive=False)

    def test_collect_config(self, step):
        """Test storage configuration collection."""
        config = step.collect_config()

        assert "DATASET_EXPIRATION_DAYS" in config
        assert "USE_EMAIL_AUTHENTICATION" in config

    def test_collect_config_values(self, step):
        """Test storage configuration has expected values."""
        config = step.collect_config()

        assert config["DATASET_EXPIRATION_DAYS"] == "30d"
        assert config["USE_EMAIL_AUTHENTICATION"] is True

    def test_collect_config_custom_values(self, tmp_path, defaults):
        """Test that custom values override defaults."""
        config = {
            "DATASET_EXPIRATION_DAYS": "60d",
            "USE_EMAIL_AUTHENTICATION": False,
        }
        step = StorageStep(tmp_path, defaults, config, interactive=False)

        result = step.collect_config()

        assert result["DATASET_EXPIRATION_DAYS"] == "60d"
        assert result["USE_EMAIL_AUTHENTICATION"] is False

    def test_generate_secrets(self, step):
        """Test storage secret generation."""
        secrets_dict = step.generate_secrets()

        assert "avatar_api_encryption_key" in secrets_dict
        assert "authentik_secret_key" in secrets_dict
        assert "seaweedfs_s3_key_id" in secrets_dict
        assert "seaweedfs_s3_key_secret" in secrets_dict

    def test_generate_secrets_valid_base64(self, step):
        """Test that encryption keys are valid base64."""
        secrets_dict = step.generate_secrets()

        # Verify avatar_api_encryption_key is valid base64
        try:
            decoded = base64.b64decode(secrets_dict["avatar_api_encryption_key"])
            assert len(decoded) == 32
        except Exception:
            pytest.fail("avatar_api_encryption_key is not valid base64")

    def test_generate_secrets_unique(self, step):
        """Test that generated secrets are unique."""
        secrets1 = step.generate_secrets()
        secrets2 = step.generate_secrets()

        # Each call should generate different secrets
        assert (
            secrets1["avatar_api_encryption_key"]
            != secrets2["avatar_api_encryption_key"]
        )
        assert secrets1["authentik_secret_key"] != secrets2["authentik_secret_key"]
        assert secrets1["seaweedfs_s3_key_id"] != secrets2["seaweedfs_s3_key_id"]
        assert (
            secrets1["seaweedfs_s3_key_secret"] != secrets2["seaweedfs_s3_key_secret"]
        )

    def test_step_metadata(self, step):
        """Test step metadata."""
        assert step.name == "storage"
        assert step.required is True
        assert "storage" in step.description.lower()
