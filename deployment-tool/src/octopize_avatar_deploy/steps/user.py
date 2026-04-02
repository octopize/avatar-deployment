"""User authentication configuration step."""

import re
from typing import Any

from .base import (
    DeploymentStep,
    ValidationError,
    ValidationSuccess,
)


def validate_comma_separated_emails(value: str) -> ValidationSuccess[str] | ValidationError:
    """
    Validate comma-separated email addresses.

    Args:
        value: String containing comma-separated email addresses

    Returns:
        ValidationSuccess with the value or ValidationError with message
    """
    if not value.strip():
        # Empty is allowed (optional field)
        return ValidationSuccess(value)

    # Simple email regex pattern
    email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"

    emails = [email.strip() for email in value.split(",")]

    for email in emails:
        if not email:
            return ValidationError("Empty email address found in list")
        if not re.match(email_pattern, email):
            return ValidationError(f"Invalid email address: {email}")

    return ValidationSuccess(value)


class UserStep(DeploymentStep):
    """Handles user authentication configuration."""

    name = "user"
    description = "Configure user authentication settings"

    def collect_config(self) -> dict[str, Any]:
        """Collect user authentication configuration."""
        config = {}

        admin_emails = self.get_config_or_prompt(
            "ADMIN_EMAILS",
            "Admin email addresses (comma-separated)",
            "",
            prompt_key="user.admin_emails",
            validate=validate_comma_separated_emails,
        )
        config["ADMIN_EMAILS"] = admin_emails

        self.config.update(config)

        return config

    def generate_secrets(self) -> dict[str, str]:
        """Generate user-related secrets."""
        admin_emails = self.get_config("ADMIN_EMAILS", "")
        return {"admin_emails": admin_emails}
