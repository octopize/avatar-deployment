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
            public_url = self.config["PUBLIC_URL"]
        elif self.interactive:
            public_url = self.prompt(
                "Public URL (domain name, e.g., avatar.example.com)",
                key="required_config.public_url",
            )
        else:
            public_url = ""

        # Normalize PUBLIC_URL to strip protocol and store just the domain
        if public_url:
            public_url = public_url.replace("https://", "").replace("http://", "").rstrip("/")
        config["PUBLIC_URL"] = public_url

        # Environment name - Required
        if "ENV_NAME" in self.config:
            config["ENV_NAME"] = self.config["ENV_NAME"]
        elif self.interactive:
            config["ENV_NAME"] = self.prompt(
                "Environment name (e.g., mycompany-prod)", key="required_config.env_name"
            )
        else:
            config["ENV_NAME"] = ""

        # Organization name - Required
        if "ORGANIZATION_NAME" in self.config:
            config["ORGANIZATION_NAME"] = self.config["ORGANIZATION_NAME"]
        elif self.interactive:
            while True:
                org_name = self.prompt(
                    "Organization name (e.g., MyCompany)", key="required_config.organization_name"
                )
                if org_name.strip():
                    config["ORGANIZATION_NAME"] = org_name
                    break
                self.printer.print_error("Organization name is required and cannot be empty")
        else:
            raise ValueError(
                "ORGANIZATION_NAME is required but not provided in configuration file. "
                "Please add ORGANIZATION_NAME to your config or run in interactive mode."
            )

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
