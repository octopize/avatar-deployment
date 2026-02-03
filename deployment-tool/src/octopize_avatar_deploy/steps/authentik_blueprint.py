"""Authentik blueprint configuration step."""

import secrets
from typing import Any

from .base import DeploymentStep


class AuthentikBlueprintStep(DeploymentStep):
    """Handles Authentik blueprint configuration for SSO setup.

    The blueprint template (octopize-avatar-blueprint.yaml) is stored in
    docker/templates/authentik/ and will be populated with these values.

    This step derives all values from existing configuration without prompting:
    - Domain from PUBLIC_URL
    - Random OAuth2 client ID
    - Redirect URI from domain
    - Default license type
    """

    name = "authentik-blueprint"
    description = "Configure Authentik SSO blueprint settings"
    required = True

    def collect_config(self) -> dict[str, Any]:
        """Collect Authentik blueprint configuration.

        All values are derived from existing config without user prompts.
        """
        config = {}

        # Extract domain from PUBLIC_URL (required config value)
        public_url = self.config.get("PUBLIC_URL", "")
        # Remove protocol and trailing slashes
        domain = public_url.replace("https://", "").replace("http://", "").rstrip("/")

        # Ensure domain is not empty
        if not domain:
            raise ValueError(
                f"PUBLIC_URL '{public_url}' is not set or invalid; cannot derive BLUEPRINT_DOMAIN."
            )

        config["BLUEPRINT_DOMAIN"] = domain

        # Generate random OAuth2 client ID (or use existing if provided)
        client_id = self.config.get("BLUEPRINT_CLIENT_ID", secrets.token_hex(32))
        config["BLUEPRINT_CLIENT_ID"] = client_id

        # Generate OAuth2 client secret (or use existing if provided)
        # This is a config value because it goes directly into the blueprint template
        client_secret = self.config.get("BLUEPRINT_CLIENT_SECRET", secrets.token_hex(32))
        config["BLUEPRINT_CLIENT_SECRET"] = client_secret

        # Build API redirect URI from domain
        redirect_uri = self.config.get(
            "BLUEPRINT_API_REDIRECT_URI", f"https://{domain}/api/login/sso/auth"
        )
        config["BLUEPRINT_API_REDIRECT_URI"] = redirect_uri

        # Use default license type (or from config)
        license_type = self.config.get(
            "BLUEPRINT_SELF_SERVICE_LICENSE",
            "demo",  # Default to demo license
        )
        config["BLUEPRINT_SELF_SERVICE_LICENSE"] = license_type

        # Update self.config for generate_secrets()
        self.config.update(config)

        return config

    def generate_secrets(self) -> dict[str, str]:
        """Generate Authentik blueprint secrets.

        The blueprint step doesn't generate any docker secrets.
        All values are stored as config values instead.
        """
        return {}
