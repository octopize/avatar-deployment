"""Target environment configuration step for component .env generation."""

from typing import Any

from .base import DeploymentStep


class TargetEnvironmentStep(DeploymentStep):
    """Collects target service URLs for generating per-component .env files.

    Used by the generate-env subcommand. Supports loading from:
    - Named environment presets (via --target and --config)
    - Interactive prompts
    - Default values (localhost URLs)
    """

    name = "target_environment"
    description = "Configure target service URLs for component .env generation"

    DEFAULTS = {
        "AVATAR_API_URL": "http://localhost:8000",
        "AVATAR_STORAGE_ENDPOINT_PUBLIC_URL": "http://localhost:8333",
        "AVATAR_STORAGE_ENDPOINT_INTERNAL_URL": "http://localhost:8333",
        "SSO_PROVIDER_URL": "http://localhost:9000/sso",
        "DB_HOST": "localhost",
    }

    PRESET_KEYS = {
        "AVATAR_API_URL": "api_url",
        "AVATAR_STORAGE_ENDPOINT_PUBLIC_URL": "storage_public_url",
        "AVATAR_STORAGE_ENDPOINT_INTERNAL_URL": "storage_internal_url",
        "SSO_PROVIDER_URL": "sso_url",
        "DB_HOST": "db_host",
    }

    PROMPTS = {
        "AVATAR_API_URL": "API URL",
        "AVATAR_STORAGE_ENDPOINT_PUBLIC_URL": "Public storage URL",
        "AVATAR_STORAGE_ENDPOINT_INTERNAL_URL": "Internal storage URL",
        "SSO_PROVIDER_URL": "SSO provider URL",
        "DB_HOST": "Database host",
    }

    def collect_config(self) -> dict[str, Any]:
        config: dict[str, Any] = {}

        # Check for named environment preset
        target_name = self.config.get("_target_environment")
        environments = self.config.get("_environments_config", {})

        preset: dict[str, Any] = {}
        if target_name and environments:
            if target_name not in environments:
                available = ", ".join(environments.keys())
                raise ValueError(
                    f"Unknown target environment '{target_name}'. "
                    f"Available environments: {available}"
                )
            preset = environments[target_name]

        for key, default_value in self.DEFAULTS.items():
            preset_key = self.PRESET_KEYS[key]
            preset_value = preset.get(preset_key, preset.get(key))
            effective_default = default_value if preset_value is None else preset_value

            if key in self.config:
                config[key] = self.config[key]
            elif preset_value is not None:
                config[key] = preset_value
            elif self.interactive:
                config[key] = self.get_config_or_prompt(
                    key,
                    self.PROMPTS[key],
                    effective_default,
                    prompt_key=f"target_env.{preset_key}",
                )
            else:
                config[key] = effective_default

        self.config.update(config)
        return config

    def generate_secrets(self) -> dict[str, str]:
        return {}
