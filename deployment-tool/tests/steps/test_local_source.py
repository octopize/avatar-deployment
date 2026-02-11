"""Tests for LocalSourceStep configuration step."""

import pytest

from octopize_avatar_deploy.deployment_mode import DeploymentMode
from octopize_avatar_deploy.steps import LocalSourceStep


class TestLocalSourceStep:
    """Test the LocalSourceStep."""

    @pytest.fixture
    def step(self, tmp_path):
        """Create a LocalSourceStep instance."""
        defaults = {
            "local_source": {
                "web_source_path": "/default/path/to/avatar-website",
                "npmrc_path": "/default/path/to/.npmrc",
            }
        }
        config = {}
        return LocalSourceStep(tmp_path, defaults, config, interactive=False)

    def test_step_metadata(self, step):
        """Test step metadata."""
        assert step.name == "local_source"
        assert step.required is True
        assert "local source" in step.description.lower()

    def test_modes_dev_only(self, step):
        """Test that step only runs in dev mode."""
        assert step.modes == [DeploymentMode.DEV]
        assert DeploymentMode.DEV in step.modes
        assert DeploymentMode.PRODUCTION not in step.modes

    def test_collect_config_noninteractive(self, tmp_path):
        """Test configuration collection in non-interactive mode."""
        # Create temporary directories for testing
        web_source_dir = tmp_path / "avatar-website"
        web_source_dir.mkdir()

        npmrc_file = tmp_path / ".npmrc"
        npmrc_file.write_text("//registry.npmjs.org/:_authToken=test")

        defaults = {
            "local_source": {
                "web_source_path": str(web_source_dir),
                "npmrc_path": str(npmrc_file),
            }
        }
        config = {}

        step = LocalSourceStep(tmp_path, defaults, config, interactive=False)
        collected = step.collect_config()

        assert "WEB_SOURCE_PATH" in collected
        assert "NPMRC_PATH" in collected
        assert collected["WEB_SOURCE_PATH"] == str(web_source_dir)
        assert collected["NPMRC_PATH"] == str(npmrc_file)

    def test_collect_config_from_preloaded_config(self, tmp_path):
        """Test that preloaded config takes precedence."""
        # Create temporary directories
        web_source_dir = tmp_path / "avatar-website"
        web_source_dir.mkdir()

        npmrc_file = tmp_path / ".npmrc"
        npmrc_file.write_text("test")

        config = {
            "WEB_SOURCE_PATH": str(web_source_dir),
            "NPMRC_PATH": str(npmrc_file),
        }

        defaults = {
            "local_source": {
                "web_source_path": "/wrong/path",
                "npmrc_path": "/wrong/npmrc",
            }
        }

        step = LocalSourceStep(tmp_path, defaults, config, interactive=False)
        collected = step.collect_config()

        assert collected["WEB_SOURCE_PATH"] == str(web_source_dir)
        assert collected["NPMRC_PATH"] == str(npmrc_file)

    def test_path_validation_directory_missing(self, tmp_path):
        """Test that missing directory raises ValueError."""
        npmrc_file = tmp_path / ".npmrc"
        npmrc_file.write_text("test")

        defaults = {
            "local_source": {
                "web_source_path": "/nonexistent/path",
                "npmrc_path": str(npmrc_file),
            }
        }

        step = LocalSourceStep(tmp_path, defaults, {}, interactive=False)

        with pytest.raises(ValueError, match="does not exist"):
            step.collect_config()

    def test_path_validation_file_missing(self, tmp_path):
        """Test that missing npmrc file raises ValueError."""
        web_source_dir = tmp_path / "avatar-website"
        web_source_dir.mkdir()

        defaults = {
            "local_source": {
                "web_source_path": str(web_source_dir),
                "npmrc_path": "/nonexistent/.npmrc",
            }
        }

        step = LocalSourceStep(tmp_path, defaults, {}, interactive=False)

        with pytest.raises(ValueError, match="does not exist"):
            step.collect_config()

    def test_generate_secrets(self, step):
        """Test that no secrets are generated."""
        secrets = step.generate_secrets()
        assert secrets == {}
        assert len(secrets) == 0

    def test_validate_directory_path_success(self, tmp_path):
        """Test directory path validation with valid directory."""
        test_dir = tmp_path / "test_dir"
        test_dir.mkdir()

        is_valid, error = LocalSourceStep._validate_directory_path(str(test_dir))
        assert is_valid is True
        assert error == ""

    def test_validate_directory_path_not_exists(self):
        """Test directory path validation with non-existent path."""
        is_valid, error = LocalSourceStep._validate_directory_path("/nonexistent/path")
        assert is_valid is False
        assert "does not exist" in error

    def test_validate_directory_path_is_file(self, tmp_path):
        """Test directory path validation with file instead of directory."""
        test_file = tmp_path / "test_file.txt"
        test_file.write_text("test")

        is_valid, error = LocalSourceStep._validate_directory_path(str(test_file))
        assert is_valid is False
        assert "not a directory" in error

    def test_validate_file_path_success(self, tmp_path):
        """Test file path validation with valid file."""
        test_file = tmp_path / ".npmrc"
        test_file.write_text("test")

        is_valid, error = LocalSourceStep._validate_file_path(str(test_file))
        assert is_valid is True
        assert error == ""

    def test_validate_file_path_not_exists(self):
        """Test file path validation with non-existent path."""
        is_valid, error = LocalSourceStep._validate_file_path("/nonexistent/.npmrc")
        assert is_valid is False
        assert "does not exist" in error

    def test_validate_file_path_is_directory(self, tmp_path):
        """Test file path validation with directory instead of file."""
        test_dir = tmp_path / "test_dir"
        test_dir.mkdir()

        is_valid, error = LocalSourceStep._validate_file_path(str(test_dir))
        assert is_valid is False
        assert "not a file" in error
