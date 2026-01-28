"""Storage and application secrets configuration step."""

import base64
import secrets
from typing import Any

from .base import DeploymentStep


class StorageStep(DeploymentStep):
    """Handles storage configuration and application secrets."""

    name = "storage"
    description = "Configure storage backend and generate application secrets"
    required = True

    def collect_config(self) -> dict[str, Any]:
        """Collect storage configuration."""
        config = {}

        if self.interactive:
            print("\n--- Storage & Application Settings ---")

        # Dataset expiration
        default_expiration = self.defaults["application"]["dataset_expiration"]
        config["DATASET_EXPIRATION_DAYS"] = self.config.get(
            "DATASET_EXPIRATION_DAYS",
            self.prompt("Dataset expiration (e.g., 30d, 2w)", default_expiration)
            if self.interactive
            else default_expiration,
        )

        # Email authentication
        config["USE_EMAIL_AUTHENTICATION"] = self.config.get(
            "USE_EMAIL_AUTHENTICATION",
            self.defaults["application"]["email_authentication"],
        )

        return config

    def generate_secrets(self) -> dict[str, str]:
        """Generate application and storage secrets."""
        return {
            "avatar_api_encryption_key": base64.b64encode(
                secrets.token_bytes(32)
            ).decode(),
            "authentik_secret_key": secrets.token_urlsafe(50),
            "seaweedfs_s3_key_id": secrets.token_hex(16),
            "seaweedfs_s3_key_secret": secrets.token_urlsafe(32),
        }
