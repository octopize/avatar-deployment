"""User authentication configuration step."""

import re
from typing import Any

from .base import DeploymentStep


def validate_comma_separated_emails(value: str) -> tuple[bool, str]:
    """
    Validate comma-separated email addresses.

    Args:
        value: String containing comma-separated email addresses

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not value.strip():
        # Empty is allowed (optional field)
        return True, ""

    # Simple email regex pattern
    email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"

    emails = [email.strip() for email in value.split(",")]

    for email in emails:
        if not email:
            return False, "Empty email address found in list"
        if not re.match(email_pattern, email):
            return False, f"Invalid email address: {email}"

    return True, ""


class UserStep(DeploymentStep):
    """Handles user authentication configuration."""

    name = "user"
    description = "Configure user authentication settings"
    required = True

    def collect_config(self) -> dict[str, Any]:
        """Collect user authentication configuration."""
        config = {}

        # Check if email authentication is enabled
        # Get from config, or fallback to defaults
        use_email_auth = self.config.get(
            "USE_EMAIL_AUTHENTICATION",
            self.defaults.get("application", {}).get("email_authentication", True),
        )
        # Convert to string for comparison (defaults might be bool)
        use_email_auth_str = str(use_email_auth).lower()

        if use_email_auth_str == "true":
            if self.interactive:
                admin_emails = self.prompt(
                    "Admin email addresses (comma-separated)",
                    default="",
                    validate=validate_comma_separated_emails,
                    key="user.admin_emails",
                )
                config["ADMIN_EMAILS"] = admin_emails
            else:
                config["ADMIN_EMAILS"] = self.config.get("ADMIN_EMAILS", "")

        self.config.update(config)

        return config

    def generate_secrets(self) -> dict[str, str]:
        """Generate user-related secrets."""
        secrets_dict = {}

        # Admin emails for email-based authentication
        # USE_EMAIL_AUTHENTICATION comes from EmailStep, so use .get() with fallback
        use_email_auth = self.config.get(
            "USE_EMAIL_AUTHENTICATION",
            self.defaults.get("application", {}).get("email_authentication", "true"),
        )
        # Convert to string for comparison
        use_email_auth_str = str(use_email_auth).lower()

        if use_email_auth_str == "true":
            admin_emails = self.config.get("ADMIN_EMAILS", "")
            secrets_dict["admin_emails"] = admin_emails

        return secrets_dict
