"""Target environment configuration step for component .env generation."""

from __future__ import annotations

from typing import Any

from octopize_avatar_deploy.public_url import normalize_public_base_url
from octopize_avatar_deploy.topology_urls import (
    DOCKER_STORAGE_URL,
    GenerateEnvTopology,
    ResolvedTopologyUrls,
    ServiceLocation,
    join_base_url,
    parse_service_location,
    public_base_url_from_service_url,
    public_domain_from_url,
    resolve_host_client_storage_url,
    resolve_generate_env_urls,
)

from .base import DeploymentStep


class TargetEnvironmentStep(DeploymentStep):
    """Collect topology answers and derive target URLs for generate-env."""

    name = "target_environment"
    description = "Configure target service URLs for component .env generation"

    LOCATION_CHOICES = [location.value for location in ServiceLocation]
    RUNTIME_CHOICES = [ServiceLocation.HOST.value, ServiceLocation.DOCKER.value]

    def collect_config(self) -> dict[str, Any]:
        preset = self._load_preset()
        components = set(self.config.get("_generate_env_components", []))

        topology = self._collect_topology(preset, components)
        resolved = resolve_generate_env_urls(topology)
        customize_urls = self._should_customize_urls(preset)

        api_public_url = self._resolve_url_value(
            preset=preset,
            explicit_keys=["AVATAR_API_URL", "AVATAR_API_PUBLIC_URL", "api_url"],
            preset_keys=["api_url", "avatar_api_url", "avatar_api_public_url"],
            default=resolved.api_public_url,
            prompt_message="API public URL",
            prompt_key="target_env.api_url",
            customize=customize_urls,
        )
        storage_public_default = self._resolve_default_storage_public_url(
            topology=topology,
            resolved=resolved,
            components=components,
        )
        storage_public_url = self._resolve_url_value(
            preset=preset,
            explicit_keys=[
                "AVATAR_STORAGE_ENDPOINT_PUBLIC_URL",
                "AVATAR_STORAGE_PUBLIC_URL",
                "storage_public_url",
            ],
            preset_keys=["storage_public_url", "avatar_storage_endpoint_public_url"],
            default=storage_public_default,
            prompt_message="Storage public URL",
            prompt_key="target_env.storage_public_url",
            customize=customize_urls,
        )
        storage_internal_default = self._resolve_default_storage_internal_url(
            topology=topology,
            resolved=resolved,
            components=components,
        )
        storage_internal_url = self._resolve_url_value(
            preset=preset,
            explicit_keys=["AVATAR_STORAGE_ENDPOINT_INTERNAL_URL", "storage_internal_url"],
            preset_keys=["storage_internal_url", "avatar_storage_endpoint_internal_url"],
            default=storage_internal_default,
            prompt_message="Storage internal URL",
            prompt_key="target_env.storage_internal_url",
            customize=customize_urls,
        )
        sso_provider_url = self._resolve_url_value(
            preset=preset,
            explicit_keys=["SSO_PROVIDER_URL", "AVATAR_AUTHENTIK_URL", "sso_url"],
            preset_keys=["sso_url", "avatar_authentik_url"],
            default=resolved.sso_provider_url,
            prompt_message="SSO provider URL",
            prompt_key="target_env.sso_url",
            customize=customize_urls,
        )
        api_internal_url = self._resolve_url_value(
            preset=preset,
            explicit_keys=["AVATAR_API_INTERNAL_URL", "api_internal_url"],
            preset_keys=["api_internal_url", "avatar_api_internal_url"],
            default=resolved.api_internal_url
            if self._web_uses_same_docker_network(topology)
            else api_public_url,
        )
        public_base_url = self._resolve_public_base_url(
            preset=preset,
            topology=topology,
            fallback=public_base_url_from_service_url(api_public_url) or resolved.public_base_url,
        )
        web_client_url = self._resolve_url_value(
            preset=preset,
            explicit_keys=["AVATAR_WEB_CLIENT_URL", "web_client_url"],
            preset_keys=["web_client_url", "avatar_web_client_url"],
            default=self._resolve_default_web_client_url(
                topology=topology,
                resolved=resolved,
                public_base_url=public_base_url,
                api_public_url=api_public_url,
            ),
        )
        authentik_url = self._resolve_url_value(
            preset=preset,
            explicit_keys=["AVATAR_AUTHENTIK_URL", "SSO_PROVIDER_URL", "sso_url"],
            preset_keys=["avatar_authentik_url", "sso_url"],
            default=resolved.authentik_url,
        )
        public_domain = self._resolve_public_domain(public_base_url, api_public_url, preset)
        python_client_storage_url = self._resolve_python_client_storage_url(
            preset=preset,
            topology=topology,
            resolved=resolved,
            storage_public_url=storage_public_url,
            customize=customize_urls,
        )

        config = {
            "api_runtime": topology.api_runtime.value,
            "web_runtime": topology.web_runtime.value,
            "api_location": topology.api_location.value,
            "storage_location": topology.storage_location.value,
            "sso_location": topology.sso_location.value,
            "RESOLVED_PUBLIC_BASE_URL": public_base_url,
            "PUBLIC_URL": str(self.config.get("PUBLIC_URL", public_domain)),
            "AVATAR_API_URL": api_public_url,
            "AVATAR_API_PUBLIC_URL": api_public_url,
            "AVATAR_API_INTERNAL_URL": api_internal_url,
            "AVATAR_BASE_API_URL": api_public_url,
            "AVATAR_STORAGE_ENDPOINT_PUBLIC_URL": storage_public_url,
            "AVATAR_STORAGE_ENDPOINT_INTERNAL_URL": storage_internal_url,
            "AVATAR_STORAGE_ENDPOINT_URL": python_client_storage_url,
            "SSO_PROVIDER_URL": sso_provider_url,
            "AVATAR_AUTHENTIK_URL": authentik_url,
            "AVATAR_SSO_URL": f"{api_public_url.rstrip('/')}/login/sso",
            "AVATAR_SSO_ENABLED": "true",
            "AVATAR_WEB_CLIENT_URL": web_client_url,
            "DB_HOST": self._resolve_db_host(preset),
        }

        if topology.public_base_url:
            config["public_base_url"] = topology.public_base_url

        self.config.update(config)
        return config

    def generate_secrets(self) -> dict[str, str]:
        return {}

    def _load_preset(self) -> dict[str, Any]:
        """Load the selected named target preset, if any."""
        target_name = self.config.get("_target_environment")
        environments = self.config.get("_environments_config", {})

        if not target_name:
            return {}

        if target_name not in environments:
            available = ", ".join(environments.keys())
            raise ValueError(
                f"Unknown target environment '{target_name}'. Available environments: {available}"
            )

        preset = environments[target_name]
        if not isinstance(preset, dict):
            raise ValueError(f"Target environment '{target_name}' must be a mapping.")
        return preset

    def _collect_topology(
        self, preset: dict[str, Any], components: set[str]
    ) -> GenerateEnvTopology:
        """Collect topology answers from config, presets, prompts, or defaults."""
        api_runtime = (
            self._resolve_runtime_location(
                preset=preset,
                config_key="api_runtime",
                prompt_message="Where will the API run?",
                prompt_key="target_env.api_runtime",
            )
            if {"api", "python_client"} & components
            else ServiceLocation.HOST
        )
        web_runtime = (
            self._resolve_runtime_location(
                preset=preset,
                config_key="web_runtime",
                prompt_message="Where will the web app run?",
                prompt_key="target_env.web_runtime",
            )
            if "web" in components
            else ServiceLocation.HOST
        )
        if "api" in components:
            api_location = api_runtime
        elif {"web", "python_client"} & components:
            api_location = self._resolve_dependency_location(
                preset=preset,
                config_key="api_location",
                prompt_message="Where is the API reachable from the generated component(s)?",
                prompt_key="target_env.api_location",
            )
        else:
            api_location = ServiceLocation.HOST
        storage_location = self._resolve_dependency_location(
            preset=preset,
            config_key="storage_location",
            prompt_message="Where is storage reachable from the generated component(s)?",
            prompt_key="target_env.storage_location",
        )
        sso_location = self._resolve_dependency_location(
            preset=preset,
            config_key="sso_location",
            prompt_message="Where is SSO reachable from the generated component(s)?",
            prompt_key="target_env.sso_location",
        )

        topology = GenerateEnvTopology(
            api_runtime=api_runtime,
            web_runtime=web_runtime,
            api_location=api_location,
            storage_location=storage_location,
            sso_location=sso_location,
        )

        public_base_url = self._resolve_public_base_url_question(topology, preset)
        return GenerateEnvTopology(
            api_runtime=api_runtime,
            web_runtime=web_runtime,
            api_location=api_location,
            storage_location=storage_location,
            sso_location=sso_location,
            public_base_url=public_base_url,
        )

    def _resolve_runtime_location(
        self,
        *,
        preset: dict[str, Any],
        config_key: str,
        prompt_message: str,
        prompt_key: str,
    ) -> ServiceLocation:
        return self._resolve_location(
            preset=preset,
            config_key=config_key,
            prompt_message=prompt_message,
            prompt_key=prompt_key,
            choices=self.RUNTIME_CHOICES,
        )

    def _resolve_dependency_location(
        self,
        *,
        preset: dict[str, Any],
        config_key: str,
        prompt_message: str,
        prompt_key: str,
    ) -> ServiceLocation:
        return self._resolve_location(
            preset=preset,
            config_key=config_key,
            prompt_message=prompt_message,
            prompt_key=prompt_key,
            choices=self.LOCATION_CHOICES,
        )

    def _resolve_location(
        self,
        *,
        preset: dict[str, Any],
        config_key: str,
        prompt_message: str,
        prompt_key: str,
        choices: list[str],
    ) -> ServiceLocation:
        explicit_value = self._lookup_config_value([config_key])
        if explicit_value is not None:
            return parse_service_location(explicit_value)

        preset_value = self._lookup_preset_value(preset, [config_key])
        if preset_value is not None:
            return parse_service_location(preset_value)

        if self.interactive and not self._has_complete_direct_values(preset):
            selected = self.prompt_choice(
                prompt_message,
                choices=choices,
                default=ServiceLocation.HOST.value,
                key=prompt_key,
            )
            return parse_service_location(selected)

        return ServiceLocation.HOST

    def _resolve_public_base_url_question(
        self, topology: GenerateEnvTopology, preset: dict[str, Any]
    ) -> str | None:
        explicit_value = self._lookup_config_value(
            ["public_base_url", "TARGET_ENV_PUBLIC_BASE_URL"]
        )
        if explicit_value is not None:
            return str(explicit_value).rstrip("/")

        preset_value = self._lookup_preset_value(
            preset, ["public_base_url", "target_env_public_base_url"]
        )
        if preset_value is not None:
            return str(preset_value).rstrip("/")

        if not topology.requires_public_base_url():
            return None

        if self.interactive and not self._has_complete_direct_values(preset):
            return self.get_config_or_prompt(
                "TARGET_ENV_PUBLIC_BASE_URL",
                "Shared public base URL",
                "",
                prompt_key="target_env.public_base_url",
                parse_and_validate=normalize_public_base_url,
            )

        return None

    def _should_customize_urls(self, preset: dict[str, Any]) -> bool:
        """Offer a secondary override branch only when derived values are in play."""
        if not self.interactive or self._has_complete_direct_values(preset):
            return False

        explicit_value = self._lookup_config_value(["customize_urls"])
        if explicit_value is not None:
            return self._coerce_bool(explicit_value)

        preset_value = self._lookup_preset_value(preset, ["customize_urls"])
        if preset_value is not None:
            return self._coerce_bool(preset_value)

        return self.prompt_yes_no(
            "Customize the derived URLs?", default=False, key="target_env.customize_urls"
        )

    def _resolve_url_value(
        self,
        *,
        preset: dict[str, Any],
        explicit_keys: list[str],
        preset_keys: list[str],
        default: str,
        prompt_message: str | None = None,
        prompt_key: str | None = None,
        customize: bool = False,
    ) -> str:
        explicit_value = self._lookup_config_value(explicit_keys)
        if explicit_value is not None:
            return str(explicit_value)

        preset_value = self._lookup_preset_value(preset, preset_keys)
        if preset_value is not None:
            return str(preset_value)

        if customize and prompt_message and prompt_key:
            return self.prompt(prompt_message, default=default, key=prompt_key)

        return default

    def _resolve_public_base_url(
        self,
        *,
        preset: dict[str, Any],
        topology: GenerateEnvTopology,
        fallback: str,
    ) -> str:
        explicit_value = self._lookup_config_value(
            ["TARGET_ENV_PUBLIC_BASE_URL", "public_base_url", "RESOLVED_PUBLIC_BASE_URL"]
        )
        if explicit_value is not None:
            return str(explicit_value).rstrip("/")

        preset_value = self._lookup_preset_value(
            preset,
            ["public_base_url", "target_env_public_base_url", "resolved_public_base_url"],
        )
        if preset_value is not None:
            return str(preset_value).rstrip("/")

        if topology.public_base_url:
            return topology.public_base_url.rstrip("/")

        return fallback.rstrip("/")

    def _resolve_public_domain(
        self, public_base_url: str, api_public_url: str, preset: dict[str, Any]
    ) -> str:
        explicit_value = self._lookup_config_value(["PUBLIC_URL"])
        if explicit_value is not None:
            return str(explicit_value)

        preset_value = self._lookup_preset_value(preset, ["PUBLIC_URL", "public_url"])
        if preset_value is not None:
            return str(preset_value)

        public_domain = public_domain_from_url(public_base_url)
        if public_domain is not None:
            return public_domain

        api_public_domain = public_domain_from_url(api_public_url)
        if api_public_domain is None:
            raise ValueError(
                f"Could not derive PUBLIC_URL from '{public_base_url}' or '{api_public_url}'."
            )
        return api_public_domain

    @staticmethod
    def _resolve_default_web_client_url(
        *,
        topology: GenerateEnvTopology,
        resolved: ResolvedTopologyUrls,
        public_base_url: str,
        api_public_url: str,
    ) -> str:
        if (
            topology.web_runtime is ServiceLocation.HOST
            and topology.public_base_url is None
            and not topology.requires_public_base_url()
            and api_public_url == resolved.api_public_url
        ):
            return resolved.web_client_url
        return join_base_url(public_base_url, "/web")

    @classmethod
    def _resolve_default_storage_public_url(
        cls,
        *,
        topology: GenerateEnvTopology,
        resolved: ResolvedTopologyUrls,
        components: set[str],
    ) -> str:
        if cls._host_side_web_selected(components, topology):
            return resolve_host_client_storage_url(topology, resolved.storage_public_url)
        return resolved.storage_public_url

    @classmethod
    def _resolve_default_storage_internal_url(
        cls,
        *,
        topology: GenerateEnvTopology,
        resolved: ResolvedTopologyUrls,
        components: set[str],
    ) -> str:
        if cls._host_side_web_selected(components, topology):
            return resolve_host_client_storage_url(topology, resolved.storage_public_url)
        if cls._web_uses_same_docker_storage(topology):
            return DOCKER_STORAGE_URL
        return resolved.storage_internal_url

    def _resolve_python_client_storage_url(
        self,
        *,
        preset: dict[str, Any],
        topology: GenerateEnvTopology,
        resolved: ResolvedTopologyUrls,
        storage_public_url: str,
        customize: bool,
    ) -> str:
        default = resolve_host_client_storage_url(topology, resolved.storage_public_url)

        explicit_value = self._lookup_config_value(
            [
                "AVATAR_STORAGE_ENDPOINT_URL",
                "AVATAR_STORAGE_ENDPOINT_PUBLIC_URL",
                "AVATAR_STORAGE_PUBLIC_URL",
                "storage_url",
                "storage_public_url",
            ]
        )
        if explicit_value is not None:
            return str(explicit_value)

        preset_value = self._lookup_preset_value(
            preset,
            [
                "storage_url",
                "storage_public_url",
                "avatar_storage_endpoint_url",
                "avatar_storage_endpoint_public_url",
            ],
        )
        if preset_value is not None:
            return str(preset_value)

        if customize:
            return storage_public_url

        return default

    @staticmethod
    def _host_side_web_selected(components: set[str], topology: GenerateEnvTopology) -> bool:
        return "web" in components and topology.web_runtime is ServiceLocation.HOST

    def _resolve_db_host(self, preset: dict[str, Any]) -> str:
        explicit_value = self._lookup_config_value(["DB_HOST", "db_host"])
        if explicit_value is not None:
            return str(explicit_value)

        preset_value = self._lookup_preset_value(preset, ["db_host", "DB_HOST"])
        if preset_value is not None:
            return str(preset_value)

        if self.interactive and not self._has_complete_direct_values(preset):
            return self.get_config_or_prompt(
                "DB_HOST",
                "Database host",
                "localhost",
                prompt_key="target_env.db_host",
            )

        return "localhost"

    def _has_complete_direct_values(self, preset: dict[str, Any]) -> bool:
        required = [
            (["AVATAR_API_URL", "AVATAR_API_PUBLIC_URL", "api_url"], ["api_url", "avatar_api_url"]),
            (
                ["AVATAR_STORAGE_ENDPOINT_PUBLIC_URL", "storage_public_url"],
                ["storage_public_url", "avatar_storage_endpoint_public_url"],
            ),
            (
                ["SSO_PROVIDER_URL", "AVATAR_AUTHENTIK_URL", "sso_url"],
                ["sso_url", "avatar_authentik_url"],
            ),
        ]
        return all(
            self._lookup_config_value(explicit_keys) is not None
            or self._lookup_preset_value(preset, preset_keys) is not None
            for explicit_keys, preset_keys in required
        )

    def _lookup_config_value(self, keys: list[str]) -> Any | None:
        for key in keys:
            if key in self.config:
                return self.config[key]
        return None

    @staticmethod
    def _lookup_preset_value(preset: dict[str, Any], keys: list[str]) -> Any | None:
        for key in keys:
            if key in preset:
                return preset[key]
        return None

    @staticmethod
    def _web_uses_same_docker_network(topology: GenerateEnvTopology) -> bool:
        return (
            topology.web_runtime is ServiceLocation.DOCKER
            and topology.api_location is ServiceLocation.DOCKER
        )

    @staticmethod
    def _web_uses_same_docker_storage(topology: GenerateEnvTopology) -> bool:
        return (
            topology.web_runtime is ServiceLocation.DOCKER
            and topology.storage_location is ServiceLocation.DOCKER
        )

    @staticmethod
    def _coerce_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "y", "on"}
        return bool(value)
