"""Required configuration step - collects mandatory deployment settings."""

import secrets
from typing import Any

from .base import DeploymentStep


class RequiredConfigStep(DeploymentStep):
    """Collects required configuration that must be provided."""

    name = "required_config"
    description = "Collect required deployment settings (PUBLIC_URL, ENV_NAME, etc.)"
    required = True

    def collect_config(self) -> dict[str, Any]:
        """Collect required configuration."""
        config = {}

        # Public URL - Required
        if "PUBLIC_URL" in self.config:
            config["PUBLIC_URL"] = self.config["PUBLIC_URL"]
        elif self.interactive:
            config["PUBLIC_URL"] = self.prompt(
                "Public URL (domain name, e.g., avatar.example.com)"
            )
        else:
            config["PUBLIC_URL"] = ""

        # Environment name - Required
        if "ENV_NAME" in self.config:
            config["ENV_NAME"] = self.config["ENV_NAME"]
        elif self.interactive:
            config["ENV_NAME"] = self.prompt("Environment name (e.g., mycompany-prod)")
        else:
            config["ENV_NAME"] = ""

        # Organization name - Required
        if "ORGANIZATION_NAME" in self.config:
            config["ORGANIZATION_NAME"] = self.config["ORGANIZATION_NAME"]
        elif self.interactive:
            config["ORGANIZATION_NAME"] = self.prompt(
                "Organization name (e.g., MyCompany)"
            )
        else:
            config["ORGANIZATION_NAME"] = ""

        # Avatar home directory - always use default, not configurable
        config["AVATAR_HOME"] = self.defaults["application"]["home_directory"]

        # Service versions
        config["AVATAR_API_VERSION"] = self.config.get(
            "AVATAR_API_VERSION", self.defaults["images"]["api"]
        )
        config["AVATAR_WEB_VERSION"] = self.config.get(
            "AVATAR_WEB_VERSION", self.defaults["images"]["web"]
        )
        config["AVATAR_PDFGENERATOR_VERSION"] = self.config.get(
            "AVATAR_PDFGENERATOR_VERSION", self.defaults["images"]["pdfgenerator"]
        )
        config["AVATAR_SEAWEEDFS_VERSION"] = self.config.get(
            "AVATAR_SEAWEEDFS_VERSION", self.defaults["images"]["seaweedfs"]
        )
        config["AVATAR_AUTHENTIK_VERSION"] = self.config.get(
            "AVATAR_AUTHENTIK_VERSION", self.defaults["images"]["authentik"]
        )

        # Update self.config so generate_secrets() can access these values
        self.config.update(config)

        return config

    def generate_secrets(self) -> dict[str, str]:
        """Generate required API secrets."""
        return {
            "pepper": secrets.token_hex(),
            "authjwt_secret_key": secrets.token_hex(),
            "organization_name": self.config["ORGANIZATION_NAME"],
            "clevercloud_sso_salt": secrets.token_hex(),
        }
