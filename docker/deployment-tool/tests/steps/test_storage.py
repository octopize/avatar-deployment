#!/usr/bin/env python3
"""Tests for storage configuration step."""

import pytest

from octopize_avatar_deploy.steps import StorageStep


class TestStorageStep:
    """Test the StorageStep."""

    @pytest.fixture
    def step(self, tmp_path):
        """Create a StorageStep instance."""
        defaults = {}
        config = {}
        return StorageStep(tmp_path, defaults, config, interactive=False)

    def test_collect_config(self, step):
        """Test storage configuration collection."""
        config = step.collect_config()

        # Storage step doesn't collect config, only generates secrets
        assert isinstance(config, dict)

    def test_generate_secrets(self, step):
        """Test storage secret generation."""
        secrets_dict = step.generate_secrets()

        assert "file_jwt_secret_key" in secrets_dict
        assert "file_encryption_key" in secrets_dict
        assert "storage_admin_access_key_id" in secrets_dict
        assert "storage_admin_secret_access_key" in secrets_dict
        assert len(secrets_dict["file_jwt_secret_key"]) > 0
        assert len(secrets_dict["file_encryption_key"]) > 0
        assert len(secrets_dict["storage_admin_access_key_id"]) > 0
        assert len(secrets_dict["storage_admin_secret_access_key"]) > 0

    def test_generate_secrets_unique(self, step):
        """Test that generated secrets are unique."""
        secrets1 = step.generate_secrets()
        secrets2 = step.generate_secrets()

        # Each call should generate different secrets
        assert secrets1["file_jwt_secret_key"] != secrets2["file_jwt_secret_key"]
        assert secrets1["file_encryption_key"] != secrets2["file_encryption_key"]
        assert (
            secrets1["storage_admin_access_key_id"]
            != secrets2["storage_admin_access_key_id"]
        )
        assert (
            secrets1["storage_admin_secret_access_key"]
            != secrets2["storage_admin_secret_access_key"]
        )

    def test_step_metadata(self, step):
        """Test step metadata."""
        assert step.name == "storage"
        assert step.required is True
        assert "storage" in step.description.lower()
