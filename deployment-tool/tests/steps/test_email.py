#!/usr/bin/env python3
"""Tests for email configuration step."""

import pytest

from octopize_avatar_deploy.steps import EmailStep


class TestEmailStep:
    """Test the EmailStep."""

    @pytest.fixture
    def defaults_smtp(self):
        """Provide SMTP defaults."""
        return {
            "email": {
                "provider": "smtp",
                "smtp": {
                    "host": "smtp.example.com",
                    "port": 587,
                    "use_tls": True,
                    "start_tls": True,
                    "verify": True,
                    "sender_email": "noreply@example.com",
                },
            },
            "application": {
                "email_authentication": True,
            },
        }

    @pytest.fixture
    def defaults_aws(self):
        """Provide AWS SES defaults."""
        return {
            "email": {
                "provider": "aws",
                "smtp": {
                    "host": "smtp.example.com",
                    "port": 587,
                    "use_tls": True,
                    "start_tls": True,
                    "verify": True,
                    "sender_email": "noreply@example.com",
                },
            },
            "application": {
                "email_authentication": True,
            },
        }

    @pytest.fixture
    def step_smtp(self, tmp_path, defaults_smtp):
        """Create an EmailStep instance with SMTP config."""
        config = {"MAIL_PROVIDER": "smtp"}
        return EmailStep(tmp_path, defaults_smtp, config, interactive=False)

    @pytest.fixture
    def step_aws(self, tmp_path, defaults_aws):
        """Create an EmailStep instance with AWS config."""
        config = {"MAIL_PROVIDER": "aws"}
        return EmailStep(tmp_path, defaults_aws, config, interactive=False)

    def test_collect_config_smtp(self, step_smtp):
        """Test SMTP email configuration collection."""
        config = step_smtp.collect_config()

        assert config["MAIL_PROVIDER"] == "smtp"
        assert "SMTP_HOST" in config
        assert "SMTP_PORT" in config
        assert "SMTP_SENDER_EMAIL" in config
        assert "SMTP_USE_TLS" in config
        assert "SMTP_START_TLS" in config
        assert "SMTP_VERIFY" in config
        assert "USE_EMAIL_AUTHENTICATION" in config

    def test_collect_config_smtp_values(self, step_smtp):
        """Test SMTP configuration has correct values."""
        config = step_smtp.collect_config()

        assert config["SMTP_HOST"] == "smtp.example.com"
        assert config["SMTP_PORT"] == "587"
        assert config["SMTP_SENDER_EMAIL"] == "noreply@example.com"
        assert config["USE_EMAIL_AUTHENTICATION"] is True

    def test_collect_config_aws(self, step_aws):
        """Test AWS email configuration collection."""
        config = step_aws.collect_config()

        assert config["MAIL_PROVIDER"] == "aws"
        # AWS provider doesn't configure SMTP settings
        assert "SMTP_HOST" not in config

    def test_collect_config_custom_values(self, tmp_path, defaults_smtp):
        """Test that custom values override defaults."""
        config = {
            "MAIL_PROVIDER": "smtp",
            "SMTP_HOST": "custom.smtp.com",
            "SMTP_PORT": "465",
        }
        step = EmailStep(tmp_path, defaults_smtp, config, interactive=False)

        result = step.collect_config()

        assert result["SMTP_HOST"] == "custom.smtp.com"
        assert result["SMTP_PORT"] == "465"

    def test_generate_secrets_non_interactive(self, step_smtp):
        """Test secret generation in non-interactive mode."""
        secrets_dict = step_smtp.generate_secrets()

        # Non-interactive mode should not prompt for secrets
        assert isinstance(secrets_dict, dict)

    def test_step_metadata(self, step_smtp):
        """Test step metadata."""
        assert step_smtp.name == "email"
        assert step_smtp.required is True
        assert "email" in step_smtp.description.lower()
