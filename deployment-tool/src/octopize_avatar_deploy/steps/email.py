"""Email configuration step."""

from typing import Any

from .base import DefaultKey, DeploymentStep, parse_str


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
        provider = self.get_config_or_prompt(
            "MAIL_PROVIDER",
            "Mail provider (aws or smtp)",
            default_provider,
            prompt_key="email.mail_provider",
        ).lower()

        config["MAIL_PROVIDER"] = provider

        # SMTP configuration
        if provider == "smtp":
            config["SMTP_HOST"] = self.get_config_or_prompt(
                "SMTP_HOST",
                "SMTP host",
                DefaultKey("email.smtp.host"),
                prompt_key="email.smtp_host",
            )
            config["SMTP_PORT"] = self.get_config_or_prompt(
                "SMTP_PORT",
                "SMTP port",
                DefaultKey("email.smtp.port"),
                prompt_key="email.smtp_port",
                parse_and_validate=parse_str,
            )
            config["SMTP_USE_TLS"] = self.get_config(
                "SMTP_USE_TLS", DefaultKey("email.smtp.use_tls")
            )
            config["SMTP_START_TLS"] = self.get_config(
                "SMTP_START_TLS", DefaultKey("email.smtp.start_tls")
            )
            config["SMTP_VERIFY"] = self.get_config("SMTP_VERIFY", DefaultKey("email.smtp.verify"))
            config["SMTP_SENDER_EMAIL"] = self.get_config_or_prompt(
                "SMTP_SENDER_EMAIL",
                "SMTP sender email",
                DefaultKey("email.smtp.sender_email"),
                prompt_key="email.smtp_sender_email",
            )

        # Email authentication
        config["USE_EMAIL_AUTHENTICATION"] = self.get_config(
            "USE_EMAIL_AUTHENTICATION",
            DefaultKey("application.email_authentication"),
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
