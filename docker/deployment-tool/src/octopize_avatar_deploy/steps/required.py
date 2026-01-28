"""Required configuration step - collects mandatory deployment settings."""

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

        if self.interactive:
            print("\n" + "=" * 60)
            print("Required Configuration")
            print("=" * 60)

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

        # Avatar home directory
        default_home = self.defaults["application"]["home_directory"]
        config["AVATAR_HOME"] = self.config.get(
            "AVATAR_HOME",
            self.prompt("Avatar home directory", default_home)
            if self.interactive
            else default_home,
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

        return config

    def generate_secrets(self) -> dict[str, str]:
        """No secrets generated in this step."""
        return {}
