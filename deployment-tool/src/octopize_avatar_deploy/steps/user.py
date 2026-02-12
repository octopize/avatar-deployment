"""User authentication configuration step."""

import re
from typing import Any

from .base import (
    DefaultKey,
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

        # Check if email authentication is enabled
        # Get from config, or fallback to defaults
        use_email_auth = self.get_config(
            "USE_EMAIL_AUTHENTICATION",
            DefaultKey("application.email_authentication"),
        )
        # Convert to string for comparison (defaults might be bool)
        use_email_auth_str = str(use_email_auth).lower()

        if use_email_auth_str == "true":
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
        secrets_dict = {}

        # Admin emails for email-based authentication
        # USE_EMAIL_AUTHENTICATION comes from EmailStep, so use .get() with fallback
        use_email_auth = self.get_config(
            "USE_EMAIL_AUTHENTICATION",
            DefaultKey("application.email_authentication"),
        )
        # Convert to string for comparison
        use_email_auth_str = str(use_email_auth).lower()

        if use_email_auth_str == "true":
            admin_emails = self.get_config("ADMIN_EMAILS", "")
            secrets_dict["admin_emails"] = admin_emails

        return secrets_dict
