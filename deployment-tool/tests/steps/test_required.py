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
            "ORGANIZATION_NAME": "TestOrg",
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
        config = {
            "PUBLIC_URL": "test.example.com",
            "ENV_NAME": "test-env",
            "ORGANIZATION_NAME": "TestOrg",
        }
        step = RequiredConfigStep(tmp_path, defaults, config, interactive=False)

        result = step.collect_config()

        assert result["AVATAR_API_VERSION"] == "1.0.0"
        assert result["AVATAR_WEB_VERSION"] == "1.0.0"

    def test_collect_config_overrides_defaults(self, tmp_path, defaults):
        """Test that provided values override defaults."""
        config = {
            "PUBLIC_URL": "custom.example.com",
            "ENV_NAME": "custom-env",
            "ORGANIZATION_NAME": "TestOrg",
            "AVATAR_API_VERSION": "2.0.0",
        }
        step = RequiredConfigStep(tmp_path, defaults, config, interactive=False)

        result = step.collect_config()

        assert result["PUBLIC_URL"] == "custom.example.com"
        assert result["ENV_NAME"] == "custom-env"
        assert result["AVATAR_API_VERSION"] == "2.0.0"

    def test_collect_config_normalizes_public_url(self, tmp_path, defaults):
        """Test that PUBLIC_URL is normalized to host[:port] format."""
        config = {
            "PUBLIC_URL": "https://Avatar.Example.com:8443/",
            "ENV_NAME": "test-env",
            "ORGANIZATION_NAME": "TestOrg",
        }
        step = RequiredConfigStep(tmp_path, defaults, config, interactive=False)

        result = step.collect_config()

        assert result["PUBLIC_URL"] == "avatar.example.com:8443"
        assert result["AVATAR_API_URL"] == "https://avatar.example.com:8443/api"
        assert (
            result["AVATAR_STORAGE_ENDPOINT_PUBLIC_URL"]
            == "https://avatar.example.com:8443/storage"
        )

    def test_collect_config_rejects_invalid_public_url(self, tmp_path, defaults):
        """Test that malformed PUBLIC_URL values are rejected."""
        config = {
            "PUBLIC_URL": "avatar",
            "ENV_NAME": "test-env",
            "ORGANIZATION_NAME": "TestOrg",
        }
        step = RequiredConfigStep(tmp_path, defaults, config, interactive=False)

        with pytest.raises(ValueError, match="PUBLIC_URL must include a valid host or domain"):
            step.collect_config()

    def test_collect_config_reprompts_invalid_public_url(self, tmp_path, defaults, monkeypatch):
        """Test that invalid interactive PUBLIC_URL input is rejected until valid."""
        responses = [
            "avatar",
            "https://avatar.example.com/",
            "test-env",
            "TestOrg",
        ]
        monkeypatch.setattr("builtins.input", lambda _: responses.pop(0))

        step = RequiredConfigStep(tmp_path, defaults, interactive=True)

        result = step.collect_config()

        assert result["PUBLIC_URL"] == "avatar.example.com"
        assert len(responses) == 0

    def test_generate_env_does_not_require_public_url(self, tmp_path, defaults):
        """generate-env mode can defer PUBLIC_URL derivation to later steps."""
        config = {
            "_generate_env_mode": True,
            "ENV_NAME": "test-env",
            "ORGANIZATION_NAME": "TestOrg",
        }
        step = RequiredConfigStep(tmp_path, defaults, config, interactive=False)

        result = step.collect_config()

        assert "PUBLIC_URL" not in result
        assert result["ENV_NAME"] == "test-env"

    def test_generate_secrets(self, step):
        """Test that required config step generates API secrets."""
        # Call collect_config first to populate self.config
        step.collect_config()
        secrets_dict = step.generate_secrets()

        assert "pepper" in secrets_dict
        assert "authjwt_secret_key" in secrets_dict
        assert "organization_name" in secrets_dict
        assert "clevercloud_sso_salt" in secrets_dict
        assert len(secrets_dict["pepper"]) > 0
        assert len(secrets_dict["authjwt_secret_key"]) > 0
        assert len(secrets_dict["clevercloud_sso_salt"]) > 0

    def test_step_metadata(self, step):
        """Test step metadata."""
        assert step.name == "required_config"
        assert step.required is True
        assert "required" in step.description.lower()
