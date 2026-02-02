"""Tests for template version validation."""

import tempfile
from pathlib import Path

import pytest

from octopize_avatar_deploy.version_compat import (
    VersionError,
    validate_template_version,
)


class TestTemplateVersionValidation:
    """Test template version validation."""

    def test_valid_template_version(self):
        """Test validation passes with valid version."""
        with tempfile.TemporaryDirectory() as tmpdir:
            version_file = Path(tmpdir) / ".template-version"
            version_file.write_text("0.1.0\n")

            # Should not raise
            validate_template_version(version_file, script_version="1.0.0")

    def test_valid_template_version_with_constraint(self):
        """Test validation passes when constraint is satisfied."""
        with tempfile.TemporaryDirectory() as tmpdir:
            version_file = Path(tmpdir) / ".template-version"
            version_file.write_text("0.1.0\n>=1.0.0\n")

            # Should not raise
            validate_template_version(version_file, script_version="1.0.0")

    def test_incompatible_template_version(self):
        """Test validation fails when constraint is not satisfied."""
        with tempfile.TemporaryDirectory() as tmpdir:
            version_file = Path(tmpdir) / ".template-version"
            version_file.write_text("2.0.0\n>=2.0.0\n")

            with pytest.raises(VersionError, match="not compatible"):
                validate_template_version(version_file, script_version="1.0.0")

    def test_missing_version_file(self):
        """Test validation fails when file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            version_file = Path(tmpdir) / ".template-version"

            with pytest.raises(VersionError, match="not found"):
                validate_template_version(version_file, script_version="1.0.0")

    def test_empty_version_file(self):
        """Test validation fails with empty file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            version_file = Path(tmpdir) / ".template-version"
            version_file.write_text("")

            with pytest.raises(VersionError, match="empty or missing version"):
                validate_template_version(version_file, script_version="1.0.0")

    def test_invalid_version_format(self):
        """Test validation fails with invalid version format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            version_file = Path(tmpdir) / ".template-version"
            version_file.write_text("invalid-version\n")

            with pytest.raises(VersionError, match="Invalid template version format"):
                validate_template_version(version_file, script_version="1.0.0")

    def test_verbose_output(self, capsys):
        """Test verbose mode prints validation details."""
        with tempfile.TemporaryDirectory() as tmpdir:
            version_file = Path(tmpdir) / ".template-version"
            version_file.write_text("0.1.0\n>=1.0.0\n")

            validate_template_version(version_file, script_version="1.0.0", verbose=True)

            captured = capsys.readouterr()
            assert "Template version: 0.1.0" in captured.out
            assert "Compatibility spec: >=1.0.0" in captured.out
            assert "Script version: 1.0.0" in captured.out
            assert "✓ Compatible" in captured.out
