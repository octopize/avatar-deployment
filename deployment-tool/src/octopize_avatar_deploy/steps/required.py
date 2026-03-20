"""Required configuration step - collects mandatory deployment settings."""

import secrets
from typing import Any

from octopize_avatar_deploy.public_url import normalize_public_url

from .base import DefaultKey, DeploymentStep


class RequiredConfigStep(DeploymentStep):
    """Collects required configuration that must be provided."""

    name = "required_config"
    description = "Collect required deployment settings (PUBLIC_URL, ENV_NAME, etc.)"

    def collect_config(self) -> dict[str, Any]:
        """Collect required configuration."""
        config = {}
        is_generate_env = bool(self.config.get("_generate_env_mode"))

        if "PUBLIC_URL" in self.config or not is_generate_env:
            public_url = self.get_config_or_prompt(
                "PUBLIC_URL",
                "Public URL (e.g., avatar.example.com or https://avatar.example.com)",
                "",
                prompt_key="required_config.public_url",
                parse_and_validate=normalize_public_url,
            )
            config["PUBLIC_URL"] = public_url

        # Environment name - Required
        config["ENV_NAME"] = self.get_config_or_prompt(
            "ENV_NAME",
            "Environment name (e.g., mycompany-prod)",
            "",
            prompt_key="required_config.env_name",
        )

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
        config["AVATAR_API_VERSION"] = self.get_config(
            "AVATAR_API_VERSION", DefaultKey("images.api")
        )
        config["AVATAR_WEB_VERSION"] = self.get_config(
            "AVATAR_WEB_VERSION", DefaultKey("images.web")
        )
        config["AVATAR_PDFGENERATOR_VERSION"] = self.get_config(
            "AVATAR_PDFGENERATOR_VERSION", DefaultKey("images.pdfgenerator")
        )
        config["AVATAR_SEAWEEDFS_VERSION"] = self.get_config(
            "AVATAR_SEAWEEDFS_VERSION", DefaultKey("images.seaweedfs")
        )
        config["AVATAR_AUTHENTIK_VERSION"] = self.get_config(
            "AVATAR_AUTHENTIK_VERSION", DefaultKey("images.authentik")
        )

        # Full deployment uses PUBLIC_URL-derived service URLs. The generate-env flow
        # collects these explicitly via TargetEnvironmentStep instead.
        if not is_generate_env:
            if "AVATAR_API_URL" not in self.config:
                config["AVATAR_API_URL"] = f"https://{config['PUBLIC_URL']}/api"
            if "AVATAR_STORAGE_ENDPOINT_PUBLIC_URL" not in self.config:
                config["AVATAR_STORAGE_ENDPOINT_PUBLIC_URL"] = (
                    f"https://{config['PUBLIC_URL']}/storage"
                )
            if "AVATAR_STORAGE_ENDPOINT_INTERNAL_URL" not in self.config:
                config["AVATAR_STORAGE_ENDPOINT_INTERNAL_URL"] = "http://s3:8333"

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
