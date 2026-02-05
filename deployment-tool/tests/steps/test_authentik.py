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
        assert "AUTHENTIK_BOOTSTRAP_EMAIL" in config

    def test_collect_config_values(self, step):
        """Test authentik configuration has expected values."""
        config = step.collect_config()

        assert config["AUTHENTIK_DATABASE_NAME"] == "authentik"
        assert config["AUTHENTIK_DATABASE_USER"] == "authentik"
        assert config["AUTHENTIK_BOOTSTRAP_EMAIL"] == "admin@example.com"
        assert "AUTHENTIK_BOOTSTRAP_PASSWORD" in config
        assert "AUTHENTIK_BOOTSTRAP_TOKEN" in config
        assert len(config["AUTHENTIK_BOOTSTRAP_PASSWORD"]) > 0
        assert len(config["AUTHENTIK_BOOTSTRAP_TOKEN"]) > 0

    def test_collect_config_custom_values(self, tmp_path):
        """Test authentik configuration with custom values."""
        defaults = {}
        config = {
            "AUTHENTIK_DATABASE_NAME": "custom_authentik",
            "AUTHENTIK_DATABASE_USER": "custom_user",
            "AUTHENTIK_BOOTSTRAP_EMAIL": "custom@example.com",
        }
        step = AuthentikStep(tmp_path, defaults, config, interactive=False)

        result = step.collect_config()

        assert result["AUTHENTIK_DATABASE_NAME"] == "custom_authentik"
        assert result["AUTHENTIK_DATABASE_USER"] == "custom_user"
        assert result["AUTHENTIK_BOOTSTRAP_EMAIL"] == "custom@example.com"

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
        # Bootstrap variables should NOT be in secrets
        assert "authentik_bootstrap_password" not in secrets_dict
        assert "authentik_bootstrap_token" not in secrets_dict
        assert "authentik_bootstrap_email" not in secrets_dict

    def test_generate_secrets_unique(self, step):
        """Test that generated secrets are unique."""
        # Call collect_config first to populate self.config
        step.collect_config()
        secrets1 = step.generate_secrets()
        secrets2 = step.generate_secrets()

        # Each call should generate different passwords and keys
        assert secrets1["authentik_database_password"] != secrets2["authentik_database_password"]
        assert secrets1["authentik_secret_key"] != secrets2["authentik_secret_key"]
        # Database name and user should stay the same
        assert secrets1["authentik_database_name"] == secrets2["authentik_database_name"]
        assert secrets1["authentik_database_user"] == secrets2["authentik_database_user"]

    def test_collect_config_bootstrap_unique(self, tmp_path):
        """Test that bootstrap credentials are unique across instances."""
        defaults = {}
        config = {}
        step1 = AuthentikStep(tmp_path, defaults, config, interactive=False)
        step2 = AuthentikStep(tmp_path, defaults, {}, interactive=False)

        config1 = step1.collect_config()
        config2 = step2.collect_config()

        # Each call should generate different passwords and tokens
        assert config1["AUTHENTIK_BOOTSTRAP_PASSWORD"] != config2["AUTHENTIK_BOOTSTRAP_PASSWORD"]
        assert config1["AUTHENTIK_BOOTSTRAP_TOKEN"] != config2["AUTHENTIK_BOOTSTRAP_TOKEN"]
        # But email should stay the same
        assert config1["AUTHENTIK_BOOTSTRAP_EMAIL"] == config2["AUTHENTIK_BOOTSTRAP_EMAIL"]

    def test_step_metadata(self, step):
        """Test step metadata."""
        assert step.name == "authentik"
        assert step.required is True
        assert "authentik" in step.description.lower()
