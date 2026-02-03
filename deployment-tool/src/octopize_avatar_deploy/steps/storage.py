"""Storage configuration step."""

import secrets
from typing import Any

from .base import DeploymentStep


class StorageStep(DeploymentStep):
    """Handles storage configuration and credentials."""

    name = "storage"
    description = "Configure S3-compatible storage (SeaweedFS) credentials"
    required = True

    def collect_config(self) -> dict[str, Any]:
        """Collect storage configuration."""
        config: dict[str, Any] = {}

        # Storage configuration is mostly handled via secrets
        # No interactive prompts needed for basic setup

        return config

    def generate_secrets(self) -> dict[str, str]:
        """Generate storage-related secrets."""
        return {
            "file_jwt_secret_key": secrets.token_hex(),
            "file_encryption_key": self.generate_encryption_key(),
            "storage_admin_access_key_id": secrets.token_hex(),
            "storage_admin_secret_access_key": secrets.token_hex(),
        }
