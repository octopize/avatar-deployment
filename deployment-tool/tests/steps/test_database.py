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
        config = {
            "DB_NAME": "avatar",
            "DB_USER": "avatar",
            "DB_ADMIN_USER": "avatar_dba",
        }
        return DatabaseStep(tmp_path, defaults, config, interactive=False)

    def test_collect_config(self, step):
        """Test database configuration collection."""
        config = step.collect_config()

        assert "DB_NAME" in config
        assert "DB_USER" in config
        assert "DB_ADMIN_USER" in config

    def test_collect_config_values(self, step):
        """Test database configuration has expected values."""
        config = step.collect_config()

        assert config["DB_NAME"] == "avatar"
        assert config["DB_USER"] == "avatar"
        assert config["DB_ADMIN_USER"] == "avatar_dba"

    def test_generate_secrets(self, step):
        """Test database secret generation."""
        step.collect_config()
        secrets_dict = step.generate_secrets()

        assert "db_password" in secrets_dict
        assert "db_admin_password" in secrets_dict
        assert "db_user" in secrets_dict
        assert "db_admin_user" in secrets_dict
        assert "db_name" in secrets_dict
        assert len(secrets_dict["db_password"]) > 0
        assert len(secrets_dict["db_admin_password"]) > 0

    def test_generate_secrets_unique(self, step):
        """Test that generated secrets are unique."""
        secrets1 = step.generate_secrets()
        secrets2 = step.generate_secrets()

        # Each call should generate different passwords
        assert secrets1["db_password"] != secrets2["db_password"]
        assert secrets1["db_admin_password"] != secrets2["db_admin_password"]

    def test_step_metadata(self, step):
        """Test step metadata."""
        assert step.name == "database"
        assert step.required is True
        assert "database" in step.description.lower()
