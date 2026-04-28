"""Storage configuration step."""

import secrets
from typing import Any

from .base import DeploymentStep


class StorageStep(DeploymentStep):
    """Handles storage configuration and credentials."""

    name = "storage"
    description = "Configure S3-compatible storage (SeaweedFS) credentials"

    def collect_config(self) -> dict[str, Any]:
        """Collect storage configuration."""
        config: dict[str, Any] = {}

        # Storage configuration is mostly handled via secrets
        # No interactive prompts needed for basic setup

        return config

    def generate_secrets(self) -> dict[str, str]:
        """Generate storage-related secrets.

        storage_encryption_key is a hex-encoded 256-bit Key Encryption Key (KEK) for
        SeaweedFS SSE-S3 at-rest encryption (passed as WEED_S3_SSE_KEK). It must be
        generated once and never rotated unless all encrypted objects are re-encrypted.

        For existing deployments that were previously running SeaweedFS < 4.21, the KEK
        was auto-generated and stored in the filer at /etc/s3/sse_kek. Retrieve it with:

            echo "fs.meta.cat /etc/s3/sse_kek" | \\
                weed shell -master=master:9333 -filer=filer:8888

        Then set storage_encryption_key in .secrets/ to that hex value instead of
        generating a new one.
        """
        return {
            "file_jwt_secret_key": secrets.token_hex(),
            "file_encryption_key": self.generate_encryption_key(),
            "storage_admin_access_key_id": secrets.token_hex(),
            "storage_admin_secret_access_key": secrets.token_hex(),
            # 32 bytes = 256-bit hex key, required by WEED_S3_SSE_KEK
            "storage_encryption_key": secrets.token_hex(32),
        }
