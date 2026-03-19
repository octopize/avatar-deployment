"""Tests for TargetEnvironmentStep."""

import pytest

from octopize_avatar_deploy.steps.target_environment import TargetEnvironmentStep


class TestTargetEnvironmentStep:
    @pytest.fixture
    def defaults(self):
        return {}

    @pytest.fixture
    def step(self, tmp_path, defaults):
        config = {}
        return TargetEnvironmentStep(tmp_path, defaults, config, interactive=False)

    def test_defaults(self, step):
        """Non-interactive with no config uses localhost defaults."""
        config = step.collect_config()
        assert config["AVATAR_API_URL"] == "http://localhost:8000"
        assert config["AVATAR_STORAGE_ENDPOINT_PUBLIC_URL"] == "http://localhost:8333"
        assert config["AVATAR_STORAGE_ENDPOINT_INTERNAL_URL"] == "http://localhost:8333"
        assert config["SSO_PROVIDER_URL"] == "http://localhost:9000/sso"
        assert config["DB_HOST"] == "localhost"

    def test_config_override(self, tmp_path, defaults):
        """Pre-loaded config values take precedence."""
        config = {
            "AVATAR_API_URL": "https://prod.example.com/api",
            "SSO_PROVIDER_URL": "https://prod.example.com/sso",
        }
        step = TargetEnvironmentStep(tmp_path, defaults, config, interactive=False)
        result = step.collect_config()
        assert result["AVATAR_API_URL"] == "https://prod.example.com/api"
        assert result["SSO_PROVIDER_URL"] == "https://prod.example.com/sso"
        # Others should be defaults
        assert result["DB_HOST"] == "localhost"

    def test_named_environment_preset(self, tmp_path, defaults):
        """Named environment preset loads lower-snake-case values."""
        config = {
            "_target_environment": "staging",
            "_environments_config": {
                "staging": {
                    "api_url": "https://staging.example.com/api",
                    "storage_public_url": "https://staging.example.com/storage",
                    "sso_url": "https://staging.example.com/sso",
                    "db_host": "staging-db.example.com",
                }
            },
        }
        step = TargetEnvironmentStep(tmp_path, defaults, config, interactive=False)
        result = step.collect_config()
        assert result["AVATAR_API_URL"] == "https://staging.example.com/api"
        assert result["DB_HOST"] == "staging-db.example.com"

    def test_explicit_override_beats_named_preset(self, tmp_path, defaults):
        """Direct config values should win over target presets."""
        config = {
            "_target_environment": "staging",
            "_environments_config": {
                "staging": {
                    "api_url": "https://staging.example.com/api",
                    "sso_url": "https://staging.example.com/sso",
                }
            },
            "AVATAR_API_URL": "https://override.example.com/api",
        }
        step = TargetEnvironmentStep(tmp_path, defaults, config, interactive=False)

        result = step.collect_config()

        assert result["AVATAR_API_URL"] == "https://override.example.com/api"
        assert result["SSO_PROVIDER_URL"] == "https://staging.example.com/sso"

    def test_unknown_target_raises(self, tmp_path, defaults):
        """Unknown target environment raises ValueError."""
        config = {
            "_target_environment": "nonexistent",
            "_environments_config": {"prod": {}},
        }
        step = TargetEnvironmentStep(tmp_path, defaults, config, interactive=False)
        with pytest.raises(ValueError, match="Unknown target environment"):
            step.collect_config()

    def test_generate_secrets_empty(self, step):
        """No secrets needed."""
        assert step.generate_secrets() == {}

    def test_step_metadata(self, step):
        assert step.name == "target_environment"
