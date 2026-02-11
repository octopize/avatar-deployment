"""Email configuration step."""

from typing import Any

from .base import DeploymentStep


class EmailStep(DeploymentStep):
    """Handles email configuration and credentials."""

    name = "email"
    description = "Configure email provider (AWS SES or SMTP) and credentials"

    def collect_config(self) -> dict[str, Any]:
        """Collect email configuration."""
        config = {}

        print("\n--- Email Configuration ---")

        # Email provider
        default_provider = self.get_default_value("email.provider")
        provider = self.config.get(
            "MAIL_PROVIDER",
            self.prompt("Mail provider (aws or smtp)", default_provider, key="email.mail_provider")
            if self.interactive
            else default_provider,
        ).lower()

        config["MAIL_PROVIDER"] = provider

        # SMTP configuration
        if provider == "smtp":
            smtp_defaults = self.get_default_value("email.smtp")

            config["SMTP_HOST"] = self.config.get(
                "SMTP_HOST",
                self.prompt("SMTP host", smtp_defaults["host"], key="email.smtp_host")
                if self.interactive
                else smtp_defaults["host"],
            )
            config["SMTP_PORT"] = self.config.get(
                "SMTP_PORT",
                self.prompt("SMTP port", str(smtp_defaults["port"]), key="email.smtp_port")
                if self.interactive
                else str(smtp_defaults["port"]),
            )
            config["SMTP_USE_TLS"] = self.config.get("SMTP_USE_TLS", smtp_defaults["use_tls"])
            config["SMTP_START_TLS"] = self.config.get("SMTP_START_TLS", smtp_defaults["start_tls"])
            config["SMTP_VERIFY"] = self.config.get("SMTP_VERIFY", smtp_defaults["verify"])
            config["SMTP_SENDER_EMAIL"] = self.config.get(
                "SMTP_SENDER_EMAIL",
                self.prompt(
                    "SMTP sender email",
                    smtp_defaults["sender_email"],
                    key="email.smtp_sender_email",
                )
                if self.interactive
                else smtp_defaults["sender_email"],
            )

        # Email authentication
        config["USE_EMAIL_AUTHENTICATION"] = self.config.get(
            "USE_EMAIL_AUTHENTICATION",
            self.get_default_value("application.email_authentication"),
        )

        self.config.update(config)

        return config

    def generate_secrets(self) -> dict[str, str]:
        """Generate email-related secrets."""
        secrets_dict = {}

        # SMTP password (if using SMTP)
        if self.config["MAIL_PROVIDER"] == "smtp":
            if self.interactive:
                smtp_password = self.input_gatherer.prompt(
                    "SMTP password (press Enter to skip)", default="", key="email.smtp_password"
                )
                if smtp_password:
                    secrets_dict["smtp_password"] = smtp_password

        # AWS SES credentials (if using AWS)
        elif self.config["MAIL_PROVIDER"] == "aws":
            # Generate empty placeholder files for AWS credentials
            # These will be provided by Octopize to the user
            secrets_dict["aws_mail_account_access_key_id"] = ""
            secrets_dict["aws_mail_account_secret_access_key"] = ""

        return secrets_dict
