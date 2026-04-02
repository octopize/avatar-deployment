"""Tests for UserStep."""

import pytest

from octopize_avatar_deploy.steps.user import UserStep


class TestUserStepMetadata:
    """Test UserStep metadata."""

    def test_step_name(self, tmp_path):
        """Test step has correct name."""
        step = UserStep(output_dir=tmp_path, defaults={})
        assert step.name == "user"

    def test_step_description(self, tmp_path):
        """Test step has correct description."""
        step = UserStep(output_dir=tmp_path, defaults={})
        assert "user authentication" in step.description.lower()


class TestUserStepConfigCollection:
    """Test UserStep config collection."""

    def test_collect_config_interactive(self, tmp_path, monkeypatch):
        """Test config collection in interactive mode."""
        responses = ["admin@example.com,user@example.com"]
        monkeypatch.setattr("builtins.input", lambda _: responses.pop(0))

        step = UserStep(output_dir=tmp_path, defaults={}, interactive=True)

        config = step.collect_config()

        assert config["ADMIN_EMAILS"] == "admin@example.com,user@example.com"

    def test_collect_config_non_interactive(self, tmp_path):
        """Test config collection in non-interactive mode."""
        step = UserStep(output_dir=tmp_path, defaults={}, interactive=False)
        step.config = {"ADMIN_EMAILS": "admin@example.com"}

        config = step.collect_config()

        assert config["ADMIN_EMAILS"] == "admin@example.com"

    def test_collect_config_non_interactive_no_existing_value(self, tmp_path):
        """Test config collection in non-interactive mode with no existing admin emails."""
        step = UserStep(output_dir=tmp_path, defaults={}, interactive=False)

        config = step.collect_config()

        assert config["ADMIN_EMAILS"] == ""


class TestUserStepSecretGeneration:
    """Test UserStep secret generation."""

    def test_generate_secrets(self, tmp_path):
        """Test secret generation."""
        step = UserStep(output_dir=tmp_path, defaults={})
        step.config = {"ADMIN_EMAILS": "admin@example.com,user@example.com"}

        secrets = step.generate_secrets()

        assert "admin_emails" in secrets
        assert secrets["admin_emails"] == "admin@example.com,user@example.com"

    def test_generate_secrets_empty_emails(self, tmp_path):
        """Test secret generation with empty admin emails."""
        step = UserStep(output_dir=tmp_path, defaults={})
        step.config = {"ADMIN_EMAILS": ""}

        secrets = step.generate_secrets()

        assert "admin_emails" in secrets
        assert secrets["admin_emails"] == ""
