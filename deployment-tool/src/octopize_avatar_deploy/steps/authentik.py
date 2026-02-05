"""Authentik configuration step."""

import secrets
from typing import Any

from .base import DeploymentStep


class AuthentikStep(DeploymentStep):
    """Handles Authentik SSO configuration and credentials."""

    name = "authentik"
    description = "Configure Authentik SSO authentication credentials"
    required = True

    def collect_config(self) -> dict[str, Any]:
        """Collect Authentik configuration."""
        config = {}

        # Authentik database name and user
        # These are typically set to default values unless customized
        authentik_db_name = self.config.get(
            "AUTHENTIK_DATABASE_NAME",
            "authentik",
        )
        authentik_db_user = self.config.get(
            "AUTHENTIK_DATABASE_USER",
            "authentik",
        )

        config["AUTHENTIK_DATABASE_NAME"] = authentik_db_name
        config["AUTHENTIK_DATABASE_USER"] = authentik_db_user

        # Bootstrap configuration for automated install (skip OOBE)
        # Default email for akadmin user
        if "AUTHENTIK_BOOTSTRAP_EMAIL" in self.config:
            authentik_bootstrap_email = self.config["AUTHENTIK_BOOTSTRAP_EMAIL"]
        elif self.interactive:
            authentik_bootstrap_email = self.prompt(
                "Enter email address for Authentik admin user (akadmin)",
                default="admin@example.com",
                key="authentik.bootstrap_email",
            )
        else:
            authentik_bootstrap_email = "admin@example.com"
        config["AUTHENTIK_BOOTSTRAP_EMAIL"] = authentik_bootstrap_email

        # Generate bootstrap credentials (these go in .env, not as secrets)
        config["AUTHENTIK_BOOTSTRAP_PASSWORD"] = secrets.token_urlsafe(32)
        config["AUTHENTIK_BOOTSTRAP_TOKEN"] = secrets.token_urlsafe(32)

        # Update self.config so generate_secrets() can access these values
        self.config.update(config)

        return config

    def generate_secrets(self) -> dict[str, str]:
        """Generate Authentik-related secrets."""
        return {
            "authentik_database_name": self.config["AUTHENTIK_DATABASE_NAME"],
            "authentik_database_user": self.config["AUTHENTIK_DATABASE_USER"],
            "authentik_database_password": secrets.token_hex(),
            "authentik_secret_key": secrets.token_hex(),
        }
