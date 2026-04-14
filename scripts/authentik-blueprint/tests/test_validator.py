"""Tests for BlueprintValidator."""

import pytest
from authentik_blueprint.validator import BlueprintValidator


@pytest.fixture
def validator():
    return BlueprintValidator()


# ---------------------------------------------------------------------------
# validate_known_field_choices
# ---------------------------------------------------------------------------

class TestValidateKnownFieldChoices:
    def test_valid_pkce_s256(self, validator):
        content = '      pkce: "S256"'
        assert validator.validate_known_field_choices(content) == []

    def test_valid_pkce_plain(self, validator):
        content = "      pkce: plain"
        assert validator.validate_known_field_choices(content) == []

    def test_valid_pkce_none(self, validator):
        content = '      pkce: "none"'
        assert validator.validate_known_field_choices(content) == []

    def test_invalid_pkce_list_string(self, validator):
        """Catches the exact bug that silently broke the Google source on staging."""
        content = "      pkce: \"['plain', 'S256']\""
        errors = validator.validate_known_field_choices(content)
        assert len(errors) == 1
        assert "pkce" in errors[0]
        assert "not a valid choice" in errors[0]
        assert "['none', 'plain', 'S256']" in errors[0]

    def test_invalid_pkce_arbitrary_string(self, validator):
        content = "      pkce: sha512"
        errors = validator.validate_known_field_choices(content)
        assert len(errors) == 1
        assert "pkce" in errors[0]

    def test_unrelated_field_ignored(self, validator):
        content = "      name: Avatar API"
        assert validator.validate_known_field_choices(content) == []

    def test_pkce_in_comment_not_checked(self, validator):
        """Comment lines that happen to contain 'pkce' should not trigger validation."""
        content = "      # pkce: \"['plain', 'S256']\"  ← example of bad value"
        # comment lines don't match the field pattern (no leading spaces before #)
        # but a line with leading spaces and a # is still a comment in YAML —
        # the validator is regex-based and will match on content; that's acceptable
        # since blueprint comments should not contain field-like patterns anyway.
        # This test just documents the current behaviour.
        errors = validator.validate_known_field_choices(content)
        # "      # pkce: ..." doesn't match `^\s+pkce:\s+` because of the `#`
        assert errors == []


# ---------------------------------------------------------------------------
# Full validate() integration: new check present in output
# ---------------------------------------------------------------------------

class TestValidateIntegration:
    def test_bad_pkce_fails_validation(self, validator, tmp_path):
        blueprint = tmp_path / "bad.yaml"
        blueprint.write_text(
            "---\nversion: 1\nentries:\n  - attrs:\n      pkce: \"['plain', 'S256']\"\n"
        )
        assert validator.validate(blueprint, verbose=False) is False

    def test_good_pkce_passes_validation(self, validator, tmp_path):
        blueprint = tmp_path / "good.yaml"
        blueprint.write_text(
            "---\nversion: 1\nentries:\n  - attrs:\n      pkce: \"S256\"\n"
        )
        assert validator.validate(blueprint, verbose=False) is True
