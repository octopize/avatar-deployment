"""Authentik blueprint configuration step."""

import secrets
from typing import Any

from octopize_avatar_deploy.public_url import extract_public_url_domain_or_raise
from octopize_avatar_deploy.topology_urls import (
    public_base_url_from_service_url,
    public_domain_from_url,
)

from .base import DeploymentStep


class AuthentikBlueprintStep(DeploymentStep):
    """Handles Authentik blueprint configuration for SSO setup.

    The blueprint (octopize-avatar-blueprint.yaml) uses authentik's !Env tags
    to resolve configuration values from environment variables at blueprint
    apply time. These environment variables are passed to the authentik
    containers via docker-compose.

    This step derives all values from existing configuration without prompting.
    """

    name = "authentik-blueprint"
    description = "Configure Authentik SSO blueprint settings"

    def collect_config(self) -> dict[str, Any]:
        """Collect Authentik blueprint configuration."""
        config = {}

        public_base_url = self._resolve_public_base_url()
        api_public_url = str(self.get_config("AVATAR_API_URL", ""))
        domain = public_domain_from_url(public_base_url or "")

        if public_base_url is None or domain is None:
            raise ValueError(
                f"PUBLIC_URL '{self.get_config('PUBLIC_URL', '')}' is not set or invalid;"
                " cannot derive AVATAR_AUTHENTIK_BLUEPRINT_DOMAIN."
            )

        config["AVATAR_AUTHENTIK_BLUEPRINT_DOMAIN"] = domain

        client_id = self.get_config("AVATAR_AUTHENTIK_BLUEPRINT_CLIENT_ID", secrets.token_hex(32))
        config["AVATAR_AUTHENTIK_BLUEPRINT_CLIENT_ID"] = client_id

        client_secret = self.get_config(
            "AVATAR_AUTHENTIK_BLUEPRINT_CLIENT_SECRET", secrets.token_hex(32)
        )
        config["AVATAR_AUTHENTIK_BLUEPRINT_CLIENT_SECRET"] = client_secret

        redirect_uri = self.get_config(
            "AVATAR_AUTHENTIK_BLUEPRINT_API_REDIRECT_URI",
            f"{api_public_url.rstrip('/')}/login/sso/auth"
            if api_public_url
            else f"{public_base_url}/api/login/sso/auth",
        )
        config["AVATAR_AUTHENTIK_BLUEPRINT_API_REDIRECT_URI"] = redirect_uri

        license_type = self.get_config(
            "AVATAR_AUTHENTIK_BLUEPRINT_SELF_SERVICE_LICENSE",
            "demo",
        )
        config["AVATAR_AUTHENTIK_BLUEPRINT_SELF_SERVICE_LICENSE"] = license_type

        if "SSO_PROVIDER_URL" not in self.config:
            config["SSO_PROVIDER_URL"] = f"{public_base_url}/sso"

        self.config.update(config)
        return config

    def _resolve_public_base_url(self) -> str | None:
        """Resolve the public base URL from explicit or derived config values."""
        resolved_base = self.get_config("RESOLVED_PUBLIC_BASE_URL", "")
        if resolved_base:
            return str(resolved_base).rstrip("/")

        public_url = self.get_config("PUBLIC_URL", "")
        if public_url:
            return f"https://{extract_public_url_domain_or_raise(public_url)}"

        api_public_url = self.get_config("AVATAR_API_URL", "")
        if api_public_url:
            return public_base_url_from_service_url(str(api_public_url))

        return None

    def generate_secrets(self) -> dict[str, str]:
        """Generate Authentik blueprint secrets."""
        return {}
