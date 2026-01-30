"""Database configuration step."""

import secrets
from typing import Any

from .base import DeploymentStep


class DatabaseStep(DeploymentStep):
    """Handles database configuration and credentials."""

    name = "database"
    description = "Configure PostgreSQL database credentials"
    required = True

    def collect_config(self) -> dict[str, Any]:
        """Collect database configuration."""
        config = {}

        config["DB_NAME"] = self.get_config_value("DB_NAME", "avatar")
        config["DB_USER"] = self.get_config_value("DB_USER", "avatar")
        config["DB_ADMIN_USER"] = self.get_config_value("DB_ADMIN_USER", "avatar_dba")

        # Update self.config so generate_secrets() can access these values
        self.config.update(config)

        return config

    def generate_secrets(self) -> dict[str, str]:
        """Generate database passwords and configuration."""
        return {
            "db_password": secrets.token_hex(),
            "db_admin_password": secrets.token_hex(),
            "db_admin_user": self.config["DB_ADMIN_USER"],
            "db_user": self.config["DB_USER"],
            "db_name": self.config["DB_NAME"],
        }
