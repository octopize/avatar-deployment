"""Tests for schema_checker module."""

import ast
from pathlib import Path

import pytest
import yaml

from authentik_blueprint.schema_checker import (
    _make_blueprint_loader,
    _SkipValue,
    extract_app_label_map,
    extract_field_choices_refs,
    extract_text_choices,
    load_blueprint,
    validate_blueprint,
)


# ---------------------------------------------------------------------------
# extract_text_choices
# ---------------------------------------------------------------------------

class TestExtractTextChoices:
    def test_tuple_style(self, tmp_path):
        f = tmp_path / "models.py"
        f.write_text("""\
from django.db import models

class PKCEMethod(models.TextChoices):
    NONE = "none", "No PKCE"
    PLAIN = "plain", "Plain"
    S256 = "S256", "S256"
""")
        result = extract_text_choices(f)
        assert result == {"PKCEMethod": ["none", "plain", "S256"]}

    def test_simple_style(self, tmp_path):
        f = tmp_path / "models.py"
        f.write_text("""\
from django.db import models

class MyChoices(models.TextChoices):
    A = "a"
    B = "b"
""")
        result = extract_text_choices(f)
        assert result == {"MyChoices": ["a", "b"]}

    def test_non_choices_class_ignored(self, tmp_path):
        f = tmp_path / "models.py"
        f.write_text("""\
class NotAChoices:
    NONE = "none"
""")
        result = extract_text_choices(f)
        assert result == {}

    def test_syntax_error_returns_empty(self, tmp_path):
        f = tmp_path / "broken.py"
        f.write_text("class (: ??? bad syntax")
        result = extract_text_choices(f)
        assert result == {}


# ---------------------------------------------------------------------------
# extract_field_choices_refs
# ---------------------------------------------------------------------------

class TestExtractFieldChoicesRefs:
    def test_extracts_field_with_choices(self, tmp_path):
        f = tmp_path / "models.py"
        f.write_text("""\
from django.db import models

class OAuthSource(models.Model):
    pkce = models.TextField(choices=PKCEMethod.choices, default="none")
""")
        result = extract_field_choices_refs(f)
        assert result == {"OAuthSource": {"pkce": "PKCEMethod"}}

    def test_field_without_choices_ignored(self, tmp_path):
        f = tmp_path / "models.py"
        f.write_text("""\
from django.db import models

class MyModel(models.Model):
    name = models.CharField(max_length=255)
""")
        result = extract_field_choices_refs(f)
        assert result == {}


# ---------------------------------------------------------------------------
# extract_app_label_map
# ---------------------------------------------------------------------------

class TestExtractAppLabelMap:
    def test_extracts_label_and_name(self, tmp_path):
        app_dir = tmp_path / "sources" / "oauth"
        app_dir.mkdir(parents=True)
        (app_dir / "apps.py").write_text("""\
class AuthentikSourceOAuthConfig:
    name = "authentik.sources.oauth"
    label = "authentik_sources_oauth"
""")
        result = extract_app_label_map(tmp_path)
        assert result == {"authentik_sources_oauth": "authentik.sources.oauth"}

    def test_class_without_both_fields_ignored(self, tmp_path):
        (tmp_path / "apps.py").write_text("""\
class IncompleteConfig:
    name = "something"
""")
        result = extract_app_label_map(tmp_path)
        assert result == {}


# ---------------------------------------------------------------------------
# load_blueprint — custom tag handling
# ---------------------------------------------------------------------------

class TestLoadBlueprint:
    def test_env_tag_becomes_non_string(self, tmp_path):
        """!Env values are not plain strings — validate_blueprint will skip them."""
        f = tmp_path / "bp.yaml"
        f.write_text("entries:\n  - attrs:\n      key: !Env MY_VAR\n")
        bp = load_blueprint(f)
        # The value is some non-string object (EnvTag or _SkipValue depending on
        # what constructors are registered in this test session).
        assert not isinstance(bp["entries"][0]["attrs"]["key"], str)

    def test_keyof_tag_becomes_non_string(self, tmp_path):
        """!KeyOf values are not plain strings — validate_blueprint will skip them."""
        f = tmp_path / "bp.yaml"
        f.write_text("entries:\n  - attrs:\n      flow: !KeyOf some-id\n")
        bp = load_blueprint(f)
        assert not isinstance(bp["entries"][0]["attrs"]["flow"], str)

    def test_plain_string_preserved(self, tmp_path):
        f = tmp_path / "bp.yaml"
        f.write_text("entries:\n  - attrs:\n      pkce: \"S256\"\n")
        bp = load_blueprint(f)
        assert bp["entries"][0]["attrs"]["pkce"] == "S256"


# ---------------------------------------------------------------------------
# validate_blueprint
# ---------------------------------------------------------------------------

class TestValidateBlueprint:
    def _schema(self):
        return {
            "authentik_sources_oauth": {
                "oauthsource": {
                    "pkce": ["none", "plain", "S256"],
                }
            }
        }

    def test_valid_value_no_errors(self):
        blueprint = {
            "entries": [{
                "model": "authentik_sources_oauth.oauthsource",
                "id": "google",
                "attrs": {"pkce": "S256"},
            }]
        }
        errors = validate_blueprint(blueprint, self._schema(), verbose=False)
        assert errors == []

    def test_invalid_list_string_caught(self):
        """Catches the exact bug that broke the Google source on staging."""
        blueprint = {
            "entries": [{
                "model": "authentik_sources_oauth.oauthsource",
                "id": "google",
                "attrs": {"pkce": "['plain', 'S256']"},
            }]
        }
        errors = validate_blueprint(blueprint, self._schema(), verbose=False)
        assert len(errors) == 1
        assert "pkce" in errors[0]
        assert "not a valid choice" in errors[0]

    def test_non_string_not_validated(self):
        """Non-string values (!Env, !KeyOf, etc.) are skipped, not flagged."""
        blueprint = {
            "entries": [{
                "model": "authentik_sources_oauth.oauthsource",
                "id": "google",
                "attrs": {"pkce": object()},  # any non-str is skipped
            }]
        }
        errors = validate_blueprint(blueprint, self._schema(), verbose=False)
        assert errors == []

    def test_field_not_in_attrs_skipped(self):
        blueprint = {
            "entries": [{
                "model": "authentik_sources_oauth.oauthsource",
                "id": "google",
                "attrs": {},
            }]
        }
        errors = validate_blueprint(blueprint, self._schema(), verbose=False)
        assert errors == []

    def test_unknown_model_skipped(self):
        blueprint = {
            "entries": [{
                "model": "authentik_core.user",
                "id": "x",
                "attrs": {"pkce": "bad"},
            }]
        }
        errors = validate_blueprint(blueprint, self._schema(), verbose=False)
        assert errors == []
