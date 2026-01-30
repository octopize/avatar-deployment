#!/usr/bin/env python3
"""Tests for authentik configuration step."""

import pytest

from octopize_avatar_deploy.steps import AuthentikStep


class TestAuthentikStep:
    """Test the AuthentikStep."""

    @pytest.fixture
    def step(self, tmp_path):
        """Create an AuthentikStep instance."""
        defaults = {}
        config = {}
        return AuthentikStep(tmp_path, defaults, config, interactive=False)

    def test_collect_config(self, step):
        """Test authentik configuration collection."""
        config = step.collect_config()

        assert "AUTHENTIK_DATABASE_NAME" in config
        assert "AUTHENTIK_DATABASE_USER" in config

    def test_collect_config_values(self, step):
        """Test authentik configuration has expected values."""
        config = step.collect_config()

        assert config["AUTHENTIK_DATABASE_NAME"] == "authentik"
        assert config["AUTHENTIK_DATABASE_USER"] == "authentik"

    def test_collect_config_custom_values(self, tmp_path):
        """Test authentik configuration with custom values."""
        defaults = {}
        config = {
            "AUTHENTIK_DATABASE_NAME": "custom_authentik",
            "AUTHENTIK_DATABASE_USER": "custom_user",
        }
        step = AuthentikStep(tmp_path, defaults, config, interactive=False)

        result = step.collect_config()

        assert result["AUTHENTIK_DATABASE_NAME"] == "custom_authentik"
        assert result["AUTHENTIK_DATABASE_USER"] == "custom_user"

    def test_generate_secrets(self, step):
        """Test authentik secret generation."""
        # Call collect_config first to populate self.config
        step.collect_config()
        secrets_dict = step.generate_secrets()

        assert "authentik_database_name" in secrets_dict
        assert "authentik_database_user" in secrets_dict
        assert "authentik_database_password" in secrets_dict
        assert "authentik_secret_key" in secrets_dict
        assert len(secrets_dict["authentik_database_password"]) > 0
        assert len(secrets_dict["authentik_secret_key"]) > 0

    def test_generate_secrets_unique(self, step):
        """Test that generated secrets are unique."""
        # Call collect_config first to populate self.config
        step.collect_config()
        secrets1 = step.generate_secrets()
        secrets2 = step.generate_secrets()

        # Each call should generate different passwords
        assert (
            secrets1["authentik_database_password"]
            != secrets2["authentik_database_password"]
        )
        assert secrets1["authentik_secret_key"] != secrets2["authentik_secret_key"]

    def test_step_metadata(self, step):
        """Test step metadata."""
        assert step.name == "authentik"
        assert step.required is True
        assert "authentik" in step.description.lower()
