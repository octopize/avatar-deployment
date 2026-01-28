#!/usr/bin/env python3
"""Tests for database configuration step."""

import pytest

from octopize_avatar_deploy.steps import DatabaseStep


class TestDatabaseStep:
    """Test the DatabaseStep."""

    @pytest.fixture
    def step(self, tmp_path):
        """Create a DatabaseStep instance."""
        defaults = {}
        config = {}
        return DatabaseStep(tmp_path, defaults, config, interactive=False)

    def test_collect_config(self, step):
        """Test database configuration collection."""
        config = step.collect_config()

        assert "AUTHENTIK_DB_NAME" in config
        assert "AVATAR_DB_NAME" in config
        assert "POSTGRES_DB" in config
        assert "POSTGRES_USER" in config

    def test_collect_config_values(self, step):
        """Test database configuration has expected values."""
        config = step.collect_config()

        assert config["AUTHENTIK_DB_NAME"] == "authentik"
        assert config["AVATAR_DB_NAME"] == "avatar"
        assert config["POSTGRES_DB"] == "postgres"
        assert config["POSTGRES_USER"] == "avatar"

    def test_generate_secrets(self, step):
        """Test database secret generation."""
        secrets_dict = step.generate_secrets()

        assert "db_password" in secrets_dict
        assert "authentik_db_password" in secrets_dict
        assert len(secrets_dict["db_password"]) > 0
        assert len(secrets_dict["authentik_db_password"]) > 0

    def test_generate_secrets_unique(self, step):
        """Test that generated secrets are unique."""
        secrets1 = step.generate_secrets()
        secrets2 = step.generate_secrets()

        # Each call should generate different passwords
        assert secrets1["db_password"] != secrets2["db_password"]
        assert secrets1["authentik_db_password"] != secrets2["authentik_db_password"]

    def test_step_metadata(self, step):
        """Test step metadata."""
        assert step.name == "database"
        assert step.required is True
        assert "database" in step.description.lower()
