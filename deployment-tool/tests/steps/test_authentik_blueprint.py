#!/usr/bin/env python3
"""Tests for authentik blueprint configuration step."""

import pytest

from octopize_avatar_deploy.steps import AuthentikBlueprintStep


class TestAuthentikBlueprintStep:
    """Test the AuthentikBlueprintStep."""

    @pytest.fixture
    def step(self, tmp_path):
        """Create an AuthentikBlueprintStep instance with a valid PUBLIC_URL."""
        defaults = {}
        config = {"PUBLIC_URL": "https://avatar.example.com"}
        return AuthentikBlueprintStep(tmp_path, defaults, config, interactive=False)

    def test_collect_config(self, step):
        """Test blueprint configuration collection."""
        config = step.collect_config()

        assert "BLUEPRINT_DOMAIN" in config
        assert "BLUEPRINT_CLIENT_ID" in config
        assert "BLUEPRINT_CLIENT_SECRET" in config
        assert "BLUEPRINT_API_REDIRECT_URI" in config
        assert "BLUEPRINT_SELF_SERVICE_LICENSE" in config

    def test_collect_config_values(self, step):
        """Test blueprint configuration has expected values."""
        config = step.collect_config()

        # Domain should be derived from PUBLIC_URL
        assert config["BLUEPRINT_DOMAIN"] == "avatar.example.com"

        # Client ID and secret should be generated (64 hex chars)
        assert len(config["BLUEPRINT_CLIENT_ID"]) == 64
        assert len(config["BLUEPRINT_CLIENT_SECRET"]) == 64

        # Redirect URI should be built from domain
        assert (
            config["BLUEPRINT_API_REDIRECT_URI"] == "https://avatar.example.com/api/login/sso/auth"
        )

        # License type should default to demo
        assert config["BLUEPRINT_SELF_SERVICE_LICENSE"] == "demo"

    def test_collect_config_domain_extraction(self, tmp_path):
        """Test domain extraction from various PUBLIC_URL formats."""
        test_cases = [
            ("https://avatar.example.com", "avatar.example.com"),
            ("https://avatar.example.com/", "avatar.example.com"),
            ("http://staging.octopize.tech", "staging.octopize.tech"),
            ("http://staging.octopize.tech/", "staging.octopize.tech"),
        ]

        for public_url, expected_domain in test_cases:
            config = {"PUBLIC_URL": public_url}
            step = AuthentikBlueprintStep(tmp_path, {}, config, interactive=False)
            result = step.collect_config()
            assert result["BLUEPRINT_DOMAIN"] == expected_domain

    def test_collect_config_empty_public_url(self, tmp_path):
        """Test that empty PUBLIC_URL raises ValueError."""
        config = {"PUBLIC_URL": ""}
        step = AuthentikBlueprintStep(tmp_path, {}, config, interactive=False)

        with pytest.raises(ValueError, match="PUBLIC_URL .* is not set or invalid"):
            step.collect_config()

    def test_collect_config_missing_public_url(self, tmp_path):
        """Test that missing PUBLIC_URL raises ValueError."""
        config = {}
        step = AuthentikBlueprintStep(tmp_path, {}, config, interactive=False)

        with pytest.raises(ValueError, match="PUBLIC_URL .* is not set or invalid"):
            step.collect_config()

    def test_collect_config_custom_values(self, tmp_path):
        """Test blueprint configuration with custom values."""
        config = {
            "PUBLIC_URL": "https://avatar.example.com",
            "BLUEPRINT_CLIENT_ID": "custom-client-id",
            "BLUEPRINT_CLIENT_SECRET": "custom-secret",
            "BLUEPRINT_API_REDIRECT_URI": "https://custom.example.com/auth",
            "BLUEPRINT_SELF_SERVICE_LICENSE": "trial",
        }
        step = AuthentikBlueprintStep(tmp_path, {}, config, interactive=False)

        result = step.collect_config()

        # Custom values should be preserved
        assert result["BLUEPRINT_CLIENT_ID"] == "custom-client-id"
        assert result["BLUEPRINT_CLIENT_SECRET"] == "custom-secret"
        assert result["BLUEPRINT_API_REDIRECT_URI"] == "https://custom.example.com/auth"
        assert result["BLUEPRINT_SELF_SERVICE_LICENSE"] == "trial"

    def test_generate_secrets(self, step):
        """Test blueprint secret generation."""
        # Call collect_config first to populate self.config
        step.collect_config()
        secrets_dict = step.generate_secrets()

        # Blueprint step doesn't generate any docker secrets
        assert secrets_dict == {}

    def test_collect_config_unique_ids(self, tmp_path):
        """Test that generated client IDs and secrets are unique."""
        config = {"PUBLIC_URL": "https://avatar.example.com"}

        step1 = AuthentikBlueprintStep(tmp_path, {}, config.copy(), interactive=False)
        result1 = step1.collect_config()

        step2 = AuthentikBlueprintStep(tmp_path, {}, config.copy(), interactive=False)
        result2 = step2.collect_config()

        # Each call should generate different IDs and secrets
        assert result1["BLUEPRINT_CLIENT_ID"] != result2["BLUEPRINT_CLIENT_ID"]
        assert result1["BLUEPRINT_CLIENT_SECRET"] != result2["BLUEPRINT_CLIENT_SECRET"]

    def test_collect_config_updates_self_config(self, step):
        """Test that collect_config updates self.config."""
        config = step.collect_config()

        # Verify all values are also in self.config
        assert step.config["BLUEPRINT_DOMAIN"] == config["BLUEPRINT_DOMAIN"]
        assert step.config["BLUEPRINT_CLIENT_ID"] == config["BLUEPRINT_CLIENT_ID"]
        assert step.config["BLUEPRINT_CLIENT_SECRET"] == config["BLUEPRINT_CLIENT_SECRET"]
        assert step.config["BLUEPRINT_API_REDIRECT_URI"] == config["BLUEPRINT_API_REDIRECT_URI"]
        assert (
            step.config["BLUEPRINT_SELF_SERVICE_LICENSE"]
            == config["BLUEPRINT_SELF_SERVICE_LICENSE"]
        )

    def test_step_metadata(self, step):
        """Test step metadata."""
        assert step.name == "authentik-blueprint"
        assert step.required is True
        assert "blueprint" in step.description.lower()
        assert "sso" in step.description.lower()
