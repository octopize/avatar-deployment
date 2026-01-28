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

        return config

    def generate_secrets(self) -> dict[str, str]:
        """Generate database passwords."""
        return {
            "db_password": secrets.token_urlsafe(32),
            "authentik_db_password": secrets.token_urlsafe(32),
        }
