"""Tests for TargetEnvironmentStep."""

import pytest

from octopize_avatar_deploy.input_gatherer import MockInputGatherer
from octopize_avatar_deploy.steps.target_environment import TargetEnvironmentStep


class TestTargetEnvironmentStep:
    @pytest.fixture
    def defaults(self):
        return {}

    def test_local_topology_defaults(self, tmp_path, defaults):
        """Non-interactive mode derives local defaults, including host-web localhost."""
        config = {"_generate_env_components": ["api", "web"]}
        step = TargetEnvironmentStep(tmp_path, defaults, config, interactive=False)

        result = step.collect_config()

        assert result["AVATAR_API_URL"] == "http://localhost:8080/api"
        assert result["AVATAR_API_PUBLIC_URL"] == "http://localhost:8080/api"
        assert result["AVATAR_API_INTERNAL_URL"] == "http://localhost:8080/api"
        assert result["AVATAR_STORAGE_ENDPOINT_PUBLIC_URL"] == "http://localhost:8333"
        assert result["AVATAR_STORAGE_ENDPOINT_INTERNAL_URL"] == "http://localhost:8333"
        assert result["SSO_PROVIDER_URL"] == "http://localhost:8080/sso"
        assert result["AVATAR_AUTHENTIK_URL"] == "http://localhost:8080/sso"
        assert result["AVATAR_WEB_CLIENT_URL"] == "http://localhost:3000"
        assert result["AVATAR_SSO_URL"] == "http://localhost:8080/api/login/sso"
        assert result["AVATAR_SSO_ENABLED"] == "true"
        assert result["PUBLIC_URL"] == "localhost:8080"
        assert result["DB_HOST"] == "localhost"

    def test_host_web_with_docker_dependencies_keeps_local_dev_entrypoint(self, tmp_path, defaults):
        """Host web keeps its localhost dev URL when dependencies sit behind the gateway."""
        config = {
            "_generate_env_components": ["web"],
            "web_runtime": "host",
            "api_location": "docker",
            "storage_location": "docker",
            "sso_location": "docker",
        }
        step = TargetEnvironmentStep(tmp_path, defaults, config, interactive=False)

        result = step.collect_config()

        assert result["AVATAR_API_URL"] == "http://localhost:8080/api"
        assert result["AVATAR_STORAGE_ENDPOINT_PUBLIC_URL"] == "http://localhost:8080/storage"
        assert result["AVATAR_STORAGE_ENDPOINT_INTERNAL_URL"] == "http://localhost:8080/storage"
        assert result["AVATAR_WEB_CLIENT_URL"] == "http://localhost:3000"

    def test_web_same_network_docker_derives_internal_api_url(self, tmp_path, defaults):
        """Web-in-docker uses the Docker-network API URL while keeping public URLs stable."""
        config = {
            "_generate_env_components": ["web"],
            "web_runtime": "docker",
            "api_location": "docker",
            "storage_location": "host",
            "sso_location": "host",
        }
        step = TargetEnvironmentStep(tmp_path, defaults, config, interactive=False)

        result = step.collect_config()

        assert result["AVATAR_API_URL"] == "http://localhost:8080/api"
        assert result["AVATAR_API_INTERNAL_URL"] == "http://api:8000"
        assert result["AVATAR_SSO_URL"] == "http://localhost:8080/api/login/sso"
        assert result["SSO_PROVIDER_URL"] == "http://localhost:8080/sso"
        assert result["AVATAR_AUTHENTIK_URL"] == "http://localhost:8080/sso"

    def test_api_same_network_docker_derives_internal_storage_url(self, tmp_path, defaults):
        """API-in-docker uses the Docker-network storage URL for the API env contract."""
        config = {
            "_generate_env_components": ["api"],
            "api_runtime": "docker",
            "storage_location": "docker",
            "sso_location": "host",
        }
        step = TargetEnvironmentStep(tmp_path, defaults, config, interactive=False)

        result = step.collect_config()

        assert result["AVATAR_STORAGE_ENDPOINT_PUBLIC_URL"] == "http://localhost:8080/storage"
        assert result["AVATAR_STORAGE_ENDPOINT_INTERNAL_URL"] == "http://s3:8333"

    def test_python_client_defaults_to_host_storage_when_api_runs_on_host(self, tmp_path, defaults):
        """Python client env should point straight at SeaweedFS for host-local API."""
        config = {"_generate_env_components": ["python_client"]}
        step = TargetEnvironmentStep(tmp_path, defaults, config, interactive=False)

        result = step.collect_config()

        assert result["AVATAR_BASE_API_URL"] == "http://localhost:8080/api"
        assert result["AVATAR_STORAGE_ENDPOINT_URL"] == "http://localhost:8333"

    def test_python_client_uses_gateway_storage_when_api_runs_in_docker(self, tmp_path, defaults):
        """Python client env should use the gateway storage URL for docker-backed API."""
        config = {
            "_generate_env_components": ["python_client"],
            "api_runtime": "docker",
        }
        step = TargetEnvironmentStep(tmp_path, defaults, config, interactive=False)

        result = step.collect_config()

        assert result["AVATAR_BASE_API_URL"] == "http://localhost:8080/api"
        assert result["AVATAR_STORAGE_ENDPOINT_URL"] == "http://localhost:8080/storage"

    def test_external_topology_prompts_for_shared_public_base_url(self, tmp_path, defaults):
        """External/public dependencies ask once for a shared public base URL."""
        input_gatherer = MockInputGatherer(
            {
                "target_env.web_runtime": "host",
                "target_env.api_location": "external",
                "target_env.storage_location": "external",
                "target_env.sso_location": "external",
                "target_env.public_base_url": "https://avatar.example.com",
                "target_env.customize_urls": False,
                "target_env.db_host": "localhost",
            }
        )
        config = {"_generate_env_components": ["web"]}
        step = TargetEnvironmentStep(
            tmp_path,
            defaults,
            config,
            interactive=True,
            input_gatherer=input_gatherer,
        )

        result = step.collect_config()

        assert result["AVATAR_API_URL"] == "https://avatar.example.com/api"
        assert result["AVATAR_STORAGE_ENDPOINT_PUBLIC_URL"] == "https://avatar.example.com/storage"
        assert result["SSO_PROVIDER_URL"] == "https://avatar.example.com/sso"
        assert result["AVATAR_AUTHENTIK_URL"] == "https://avatar.example.com/sso"
        assert result["AVATAR_SSO_URL"] == "https://avatar.example.com/api/login/sso"
        assert result["AVATAR_SSO_ENABLED"] == "true"
        assert result["RESOLVED_PUBLIC_BASE_URL"] == "https://avatar.example.com"
        assert "target_env.public_base_url" in input_gatherer.used_keys

    def test_local_topology_does_not_prompt_for_public_base_url(self, tmp_path, defaults):
        """Local topology skips the shared public-base prompt entirely."""
        input_gatherer = MockInputGatherer(
            {
                "target_env.web_runtime": "host",
                "target_env.api_location": "host",
                "target_env.storage_location": "host",
                "target_env.sso_location": "host",
                "target_env.customize_urls": False,
                "target_env.db_host": "localhost",
            }
        )
        config = {"_generate_env_components": ["web"]}
        step = TargetEnvironmentStep(
            tmp_path,
            defaults,
            config,
            interactive=True,
            input_gatherer=input_gatherer,
        )

        step.collect_config()

        assert "target_env.public_base_url" not in input_gatherer.used_keys

    def test_named_environment_preset(self, tmp_path, defaults):
        """Named environment presets still override derived defaults."""
        config = {
            "_generate_env_components": ["web"],
            "_target_environment": "staging",
            "_environments_config": {
                "staging": {
                    "api_url": "https://staging.example.com/api",
                    "storage_public_url": "https://staging.example.com/storage",
                    "sso_url": "https://staging.example.com/sso",
                }
            },
        }
        step = TargetEnvironmentStep(tmp_path, defaults, config, interactive=False)

        result = step.collect_config()

        assert result["AVATAR_API_URL"] == "https://staging.example.com/api"
        assert result["AVATAR_STORAGE_ENDPOINT_PUBLIC_URL"] == "https://staging.example.com/storage"
        assert result["SSO_PROVIDER_URL"] == "https://staging.example.com/sso"
        assert result["AVATAR_AUTHENTIK_URL"] == "https://staging.example.com/sso"
        assert result["AVATAR_SSO_URL"] == "https://staging.example.com/api/login/sso"

    def test_explicit_override_beats_named_preset(self, tmp_path, defaults):
        """Direct config values still win over target presets."""
        config = {
            "_generate_env_components": ["web"],
            "_target_environment": "staging",
            "_environments_config": {
                "staging": {
                    "api_url": "https://staging.example.com/api",
                    "storage_public_url": "https://staging.example.com/storage",
                    "sso_url": "https://staging.example.com/sso",
                }
            },
            "AVATAR_API_URL": "https://override.example.com/api",
        }
        step = TargetEnvironmentStep(tmp_path, defaults, config, interactive=False)

        result = step.collect_config()

        assert result["AVATAR_API_URL"] == "https://override.example.com/api"
        assert result["AVATAR_SSO_URL"] == "https://override.example.com/api/login/sso"
        assert result["SSO_PROVIDER_URL"] == "https://staging.example.com/sso"
        assert result["AVATAR_AUTHENTIK_URL"] == "https://staging.example.com/sso"

    def test_explicit_web_client_url_override_beats_host_default(self, tmp_path, defaults):
        """Explicit web-client overrides still win over the host-local default."""
        config = {
            "_generate_env_components": ["web"],
            "AVATAR_WEB_CLIENT_URL": "https://web.example.com",
        }
        step = TargetEnvironmentStep(tmp_path, defaults, config, interactive=False)

        result = step.collect_config()

        assert result["AVATAR_WEB_CLIENT_URL"] == "https://web.example.com"

    def test_unknown_target_raises(self, tmp_path, defaults):
        """Unknown target environment raises ValueError."""
        config = {
            "_generate_env_components": ["web"],
            "_target_environment": "nonexistent",
            "_environments_config": {"prod": {}},
        }
        step = TargetEnvironmentStep(tmp_path, defaults, config, interactive=False)

        with pytest.raises(ValueError, match="Unknown target environment"):
            step.collect_config()

    def test_generate_secrets_empty(self, tmp_path, defaults):
        step = TargetEnvironmentStep(
            tmp_path,
            defaults,
            {"_generate_env_components": ["web"]},
            interactive=False,
        )
        assert step.generate_secrets() == {}

    def test_step_metadata(self, tmp_path, defaults):
        step = TargetEnvironmentStep(
            tmp_path,
            defaults,
            {"_generate_env_components": ["web"]},
            interactive=False,
        )
        assert step.name == "target_environment"
