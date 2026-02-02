"""Tests for UserStep."""

import pytest

from octopize_avatar_deploy.steps.user import UserStep


class TestUserStepMetadata:
    """Test UserStep metadata."""

    @pytest.fixture
    def defaults_email_auth(self):
        """Provide defaults with email authentication enabled."""
        return {
            "application": {
                "email_authentication": True,
            },
        }

    def test_step_name(self, defaults_email_auth, tmp_path):
        """Test step has correct name."""
        step = UserStep(output_dir=tmp_path, defaults=defaults_email_auth)
        assert step.name == "user"

    def test_step_description(self, defaults_email_auth, tmp_path):
        """Test step has correct description."""
        step = UserStep(output_dir=tmp_path, defaults=defaults_email_auth)
        assert "user authentication" in step.description.lower()


class TestUserStepConfigCollection:
    """Test UserStep config collection."""

    @pytest.fixture
    def defaults_email_auth(self):
        """Provide defaults with email authentication enabled."""
        return {
            "application": {
                "email_authentication": True,
            },
        }

    @pytest.fixture
    def defaults_no_email_auth(self):
        """Provide defaults with email authentication disabled."""
        return {
            "application": {
                "email_authentication": False,
            },
        }

    def test_collect_config_email_auth_interactive(
        self, defaults_email_auth, tmp_path, monkeypatch
    ):
        """Test config collection with email auth in interactive mode."""
        # Mock user input
        responses = ["admin@example.com,user@example.com"]
        monkeypatch.setattr("builtins.input", lambda _: responses.pop(0))

        step = UserStep(output_dir=tmp_path, defaults=defaults_email_auth, interactive=True)
        # Set the email auth flag before collecting config
        step.config = {"USE_EMAIL_AUTHENTICATION": "true"}

        config = step.collect_config()

        assert config["ADMIN_EMAILS"] == "admin@example.com,user@example.com"

    def test_collect_config_email_auth_non_interactive(self, defaults_email_auth, tmp_path):
        """Test config collection with email auth in non-interactive mode."""
        step = UserStep(output_dir=tmp_path, defaults=defaults_email_auth, interactive=False)
        step.config = {
            "USE_EMAIL_AUTHENTICATION": "true",
            "ADMIN_EMAILS": "admin@example.com",
        }

        config = step.collect_config()

        assert config["ADMIN_EMAILS"] == "admin@example.com"

    def test_collect_config_email_auth_non_interactive_no_existing_value(
        self, defaults_email_auth, tmp_path
    ):
        """Test config collection with email auth enabled but no existing admin emails."""
        step = UserStep(output_dir=tmp_path, defaults=defaults_email_auth, interactive=False)
        step.config = {"USE_EMAIL_AUTHENTICATION": "true"}

        config = step.collect_config()

        # Should default to empty string
        assert config["ADMIN_EMAILS"] == ""

    def test_collect_config_no_email_auth(self, defaults_no_email_auth, tmp_path, monkeypatch):
        """Test config collection when email auth is not enabled."""
        # Mock user input (should never be called)
        monkeypatch.setattr("builtins.input", lambda _: "should_not_be_used")

        step = UserStep(output_dir=tmp_path, defaults=defaults_no_email_auth, interactive=True)

        config = step.collect_config()

        # Should not prompt or set ADMIN_EMAILS
        assert "ADMIN_EMAILS" not in config

    def test_collect_config_username_auth(self, defaults_no_email_auth, tmp_path, monkeypatch):
        """Test config collection when using username authentication."""
        # Mock user input (should never be called)
        monkeypatch.setattr("builtins.input", lambda _: "should_not_be_used")

        step = UserStep(output_dir=tmp_path, defaults=defaults_no_email_auth, interactive=True)

        config = step.collect_config()

        # Should not collect admin emails for username auth
        assert "ADMIN_EMAILS" not in config


class TestUserStepSecretGeneration:
    """Test UserStep secret generation."""

    @pytest.fixture
    def defaults_email_auth(self):
        """Provide defaults with email authentication enabled."""
        return {
            "application": {
                "email_authentication": True,
            },
        }

    @pytest.fixture
    def defaults_no_email_auth(self):
        """Provide defaults with email authentication disabled."""
        return {
            "application": {
                "email_authentication": False,
            },
        }

    def test_generate_secrets_email_auth_enabled(self, defaults_email_auth, tmp_path):
        """Test secret generation with email auth enabled."""
        step = UserStep(output_dir=tmp_path, defaults=defaults_email_auth)
        step.config = {
            "USE_EMAIL_AUTHENTICATION": "true",
            "ADMIN_EMAILS": "admin@example.com,user@example.com",
        }

        secrets = step.generate_secrets()

        assert "admin_emails" in secrets
        assert secrets["admin_emails"] == "admin@example.com,user@example.com"

    def test_generate_secrets_email_auth_disabled(self, defaults_no_email_auth, tmp_path):
        """Test secret generation with email auth disabled."""
        step = UserStep(output_dir=tmp_path, defaults=defaults_no_email_auth)
        step.config = {"USE_EMAIL_AUTHENTICATION": "false"}

        secrets = step.generate_secrets()

        # Should not generate admin_emails secret
        assert "admin_emails" not in secrets

    def test_generate_secrets_email_auth_empty_emails(self, defaults_email_auth, tmp_path):
        """Test secret generation with email auth but empty admin emails."""
        step = UserStep(output_dir=tmp_path, defaults=defaults_email_auth)
        step.config = {"USE_EMAIL_AUTHENTICATION": "true", "ADMIN_EMAILS": ""}

        secrets = step.generate_secrets()

        # Should still generate the secret, even if empty
        assert "admin_emails" in secrets
        assert secrets["admin_emails"] == ""
