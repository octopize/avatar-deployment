"""Tests for UserStep email validation."""

import pytest

from octopize_avatar_deploy.steps.user import validate_comma_separated_emails


class TestEmailValidation:
    """Test email validation function."""

    def test_valid_single_email(self):
        """Test validation of a single valid email."""
        is_valid, error = validate_comma_separated_emails("admin@example.com")
        assert is_valid is True
        assert error == ""

    def test_valid_multiple_emails(self):
        """Test validation of multiple valid emails."""
        is_valid, error = validate_comma_separated_emails(
            "admin@example.com,user@test.org,support@company.co.uk"
        )
        assert is_valid is True
        assert error == ""

    def test_valid_emails_with_spaces(self):
        """Test validation handles extra spaces."""
        is_valid, error = validate_comma_separated_emails(
            "admin@example.com, user@test.org , support@company.co.uk"
        )
        assert is_valid is True
        assert error == ""

    def test_valid_email_with_plus(self):
        """Test validation accepts + in email addresses."""
        is_valid, error = validate_comma_separated_emails("admin+test@example.com")
        assert is_valid is True
        assert error == ""

    def test_valid_email_with_dots(self):
        """Test validation accepts dots in email addresses."""
        is_valid, error = validate_comma_separated_emails("first.last@example.com")
        assert is_valid is True
        assert error == ""

    def test_empty_string_is_valid(self):
        """Test that empty string is allowed (optional field)."""
        is_valid, error = validate_comma_separated_emails("")
        assert is_valid is True
        assert error == ""

    def test_whitespace_only_is_valid(self):
        """Test that whitespace-only string is treated as empty."""
        is_valid, error = validate_comma_separated_emails("   ")
        assert is_valid is True
        assert error == ""

    def test_invalid_email_no_at(self):
        """Test validation rejects email without @."""
        is_valid, error = validate_comma_separated_emails("adminexample.com")
        assert is_valid is False
        assert "Invalid email" in error
        assert "adminexample.com" in error

    def test_invalid_email_no_domain(self):
        """Test validation rejects email without domain."""
        is_valid, error = validate_comma_separated_emails("admin@")
        assert is_valid is False
        assert "Invalid email" in error

    def test_invalid_email_no_tld(self):
        """Test validation rejects email without top-level domain."""
        is_valid, error = validate_comma_separated_emails("admin@example")
        assert is_valid is False
        assert "Invalid email" in error

    def test_invalid_email_multiple_at(self):
        """Test validation rejects email with multiple @ symbols."""
        is_valid, error = validate_comma_separated_emails("admin@@example.com")
        assert is_valid is False
        assert "Invalid email" in error

    def test_invalid_email_in_list(self):
        """Test validation rejects list with one invalid email."""
        is_valid, error = validate_comma_separated_emails(
            "admin@example.com,invalid-email,user@test.org"
        )
        assert is_valid is False
        assert "Invalid email" in error
        assert "invalid-email" in error

    def test_empty_email_in_list(self):
        """Test validation rejects list with empty entries."""
        is_valid, error = validate_comma_separated_emails("admin@example.com,,user@test.org")
        assert is_valid is False
        assert "Empty email" in error

    def test_trailing_comma(self):
        """Test validation rejects trailing comma."""
        is_valid, error = validate_comma_separated_emails("admin@example.com,")
        assert is_valid is False
        assert "Empty email" in error


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
        from octopize_avatar_deploy.steps.user import UserStep

        # Mock user input with valid email
        responses = ["admin@example.com,user@test.org"]
        monkeypatch.setattr("builtins.input", lambda _: responses.pop(0))

        step = UserStep(
            output_dir=tmp_path, defaults=defaults_email_auth, interactive=True
        )
        step.config = {"USE_EMAIL_AUTHENTICATION": "true"}

        config = step.collect_config()

        assert config["ADMIN_EMAILS"] == "admin@example.com,user@test.org"

    def test_collect_config_invalid_then_valid_email(
        self, defaults_email_auth, tmp_path, monkeypatch
    ):
        """Test that invalid emails are rejected and user is re-prompted."""
        from octopize_avatar_deploy.steps.user import UserStep

        # Mock user input: first invalid, then valid
        responses = [
            "not-an-email",  # Invalid
            "admin@example.com",  # Valid
        ]
        monkeypatch.setattr("builtins.input", lambda _: responses.pop(0))

        step = UserStep(
            output_dir=tmp_path, defaults=defaults_email_auth, interactive=True
        )
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
        from octopize_avatar_deploy.steps.user import UserStep

        # Mock user input with empty response (using default)
        responses = [""]
        monkeypatch.setattr("builtins.input", lambda _: responses.pop(0))

        step = UserStep(
            output_dir=tmp_path, defaults=defaults_email_auth, interactive=True
        )
        step.config = {"USE_EMAIL_AUTHENTICATION": "true"}

        config = step.collect_config()

        assert config["ADMIN_EMAILS"] == ""
