"""Tests for UserStep email validation."""

import pytest

from octopize_avatar_deploy.steps.base import ValidationError, ValidationSuccess
from octopize_avatar_deploy.steps.user import UserStep, validate_comma_separated_emails


class TestEmailValidation:
    """Test email validation function."""

    def test_valid_single_email(self):
        """Test validation of a single valid email."""
        result = validate_comma_separated_emails("admin@example.com")
        assert isinstance(result, ValidationSuccess)
        # Error message not checked for success

    def test_valid_multiple_emails(self):
        """Test validation of multiple valid emails."""
        result = validate_comma_separated_emails(
            "admin@example.com,user@test.org,support@company.co.uk"
        )
        assert isinstance(result, ValidationSuccess)
        # Error message not checked for success

    def test_valid_emails_with_spaces(self):
        """Test validation handles extra spaces."""
        result = validate_comma_separated_emails(
            "admin@example.com, user@test.org , support@company.co.uk"
        )
        assert isinstance(result, ValidationSuccess)
        # Error message not checked for success

    def test_valid_email_with_plus(self):
        """Test validation accepts + in email addresses."""
        result = validate_comma_separated_emails("admin+test@example.com")
        assert isinstance(result, ValidationSuccess)
        # Error message not checked for success

    def test_valid_email_with_dots(self):
        """Test validation accepts dots in email addresses."""
        result = validate_comma_separated_emails("first.last@example.com")
        assert isinstance(result, ValidationSuccess)
        # Error message not checked for success

    def test_empty_string_is_valid(self):
        """Test that empty string is allowed (optional field)."""
        result = validate_comma_separated_emails("")
        assert isinstance(result, ValidationSuccess)
        # Error message not checked for success

    def test_whitespace_only_is_valid(self):
        """Test that whitespace-only string is treated as empty."""
        result = validate_comma_separated_emails("   ")
        assert isinstance(result, ValidationSuccess)
        # Error message not checked for success

    def test_invalid_email_no_at(self):
        """Test validation rejects email without @."""
        result = validate_comma_separated_emails("adminexample.com")
        assert isinstance(result, ValidationError)
        assert "Invalid email" in result.message
        assert "adminexample.com" in result.message

    def test_invalid_email_no_domain(self):
        """Test validation rejects email without domain."""
        result = validate_comma_separated_emails("admin@")
        assert isinstance(result, ValidationError)
        assert "Invalid email" in result.message

    def test_invalid_email_no_tld(self):
        """Test validation rejects email without top-level domain."""
        result = validate_comma_separated_emails("admin@example")
        assert isinstance(result, ValidationError)
        assert "Invalid email" in result.message

    def test_invalid_email_multiple_at(self):
        """Test validation rejects email with multiple @ symbols."""
        result = validate_comma_separated_emails("admin@@example.com")
        assert isinstance(result, ValidationError)
        assert "Invalid email" in result.message

    def test_invalid_email_in_list(self):
        """Test validation rejects list with one invalid email."""
        result = validate_comma_separated_emails(
            "admin@example.com,invalid-email,user@test.org"
        )
        assert isinstance(result, ValidationError)
        assert "Invalid email" in result.message
        assert "invalid-email" in result.message

    def test_empty_email_in_list(self):
        """Test validation rejects list with empty entries."""
        result = validate_comma_separated_emails("admin@example.com,,user@test.org")
        assert isinstance(result, ValidationError)
        assert "Empty email" in result.message

    def test_trailing_comma(self):
        """Test validation rejects trailing comma."""
        result = validate_comma_separated_emails("admin@example.com,")
        assert isinstance(result, ValidationError)
        assert "Empty email" in result.message


class TestUserStepWithValidation:
    """Test UserStep using email validation in interactive mode."""

    @pytest.fixture
    def defaults_email_auth(self):
        """Provide defaults with email authentication enabled."""
        return {
            "application": {
                "email_authentication": True,
            },
        }

    def test_collect_config_valid_email(self, defaults_email_auth, tmp_path, monkeypatch):
        """Test that valid emails are accepted."""

        # Mock user input with valid email
        responses = ["admin@example.com,user@test.org"]
        monkeypatch.setattr("builtins.input", lambda _: responses.pop(0))

        step = UserStep(output_dir=tmp_path, defaults=defaults_email_auth, interactive=True)
        step.config = {"USE_EMAIL_AUTHENTICATION": "true"}

        config = step.collect_config()

        assert config["ADMIN_EMAILS"] == "admin@example.com,user@test.org"

    def test_collect_config_invalid_then_valid_email(
        self, defaults_email_auth, tmp_path, monkeypatch
    ):
        """Test that invalid emails are rejected and user is re-prompted."""

        # Mock user input: first invalid, then valid
        responses = [
            "not-an-email",  # Invalid
            "admin@example.com",  # Valid
        ]
        monkeypatch.setattr("builtins.input", lambda _: responses.pop(0))

        step = UserStep(output_dir=tmp_path, defaults=defaults_email_auth, interactive=True)
        step.config = {"USE_EMAIL_AUTHENTICATION": "true"}

        config = step.collect_config()

        # Should eventually accept the valid email
        assert config["ADMIN_EMAILS"] == "admin@example.com"
        # Verify we used both responses
        assert len(responses) == 0

    def test_collect_config_empty_email_is_accepted(
        self, defaults_email_auth, tmp_path, monkeypatch
    ):
        """Test that empty email list is allowed (optional field)."""

        # Mock user input with empty response (using default)
        responses = [""]
        monkeypatch.setattr("builtins.input", lambda _: responses.pop(0))

        step = UserStep(output_dir=tmp_path, defaults=defaults_email_auth, interactive=True)
        step.config = {"USE_EMAIL_AUTHENTICATION": "true"}

        config = step.collect_config()

        assert config["ADMIN_EMAILS"] == ""
