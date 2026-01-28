#!/usr/bin/env python3
"""Tests for required configuration step."""

import pytest

from octopize_avatar_deploy.steps import RequiredConfigStep


class TestRequiredConfigStep:
    """Test the RequiredConfigStep."""

    @pytest.fixture
    def defaults(self):
        """Provide default configuration."""
        return {
            "application": {"home_directory": "/opt/avatar"},
            "images": {
                "api": "1.0.0",
                "web": "1.0.0",
                "pdfgenerator": "1.0.0",
                "seaweedfs": "1.0.0",
                "authentik": "1.0.0",
            },
        }

    @pytest.fixture
    def step(self, tmp_path, defaults):
        """Create a RequiredConfigStep instance."""
        config = {
            "PUBLIC_URL": "test.example.com",
            "ENV_NAME": "test-env",
        }
        return RequiredConfigStep(tmp_path, defaults, config, interactive=False)

    def test_collect_config(self, step):
        """Test configuration collection."""
        config = step.collect_config()

        assert config["PUBLIC_URL"] == "test.example.com"
        assert config["ENV_NAME"] == "test-env"
        assert "AVATAR_API_VERSION" in config
        assert "AVATAR_WEB_VERSION" in config
        assert "AVATAR_PDFGENERATOR_VERSION" in config
        assert "AVATAR_SEAWEEDFS_VERSION" in config
        assert "AVATAR_AUTHENTIK_VERSION" in config

    def test_collect_config_uses_defaults(self, tmp_path, defaults):
        """Test that default values are used when not provided."""
        config = {}
        step = RequiredConfigStep(tmp_path, defaults, config, interactive=False)

        result = step.collect_config()

        assert result["AVATAR_API_VERSION"] == "1.0.0"
        assert result["AVATAR_WEB_VERSION"] == "1.0.0"
        assert result["AVATAR_HOME"] == "/opt/avatar"

    def test_collect_config_overrides_defaults(self, tmp_path, defaults):
        """Test that provided values override defaults."""
        config = {
            "PUBLIC_URL": "custom.example.com",
            "ENV_NAME": "custom-env",
            "AVATAR_API_VERSION": "2.0.0",
            "AVATAR_HOME": "/custom/path",
        }
        step = RequiredConfigStep(tmp_path, defaults, config, interactive=False)

        result = step.collect_config()

        assert result["PUBLIC_URL"] == "custom.example.com"
        assert result["ENV_NAME"] == "custom-env"
        assert result["AVATAR_API_VERSION"] == "2.0.0"
        assert result["AVATAR_HOME"] == "/custom/path"

    def test_generate_secrets(self, step):
        """Test that required config step generates no secrets."""
        secrets_dict = step.generate_secrets()
        assert secrets_dict == {}

    def test_step_metadata(self, step):
        """Test step metadata."""
        assert step.name == "required_config"
        assert step.required is True
        assert "required" in step.description.lower()
