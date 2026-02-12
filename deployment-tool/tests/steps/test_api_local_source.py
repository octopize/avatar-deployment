"""Tests for ApiLocalSourceStep configuration step."""

import pytest

from octopize_avatar_deploy.deployment_mode import DeploymentMode
from octopize_avatar_deploy.steps import ApiLocalSourceStep
from octopize_avatar_deploy.steps.base import ValidationError, ValidationSuccess


class TestApiLocalSourceStep:
    """Test the ApiLocalSourceStep."""

    @pytest.fixture
    def step(self, tmp_path):
        """Create an ApiLocalSourceStep instance."""
        defaults = {
            "local_source": {
                "api_source_path": "/default/path/to/avatar/services/api",
            }
        }
        config = {}
        return ApiLocalSourceStep(tmp_path, defaults, config, interactive=False)

    @pytest.fixture
    def monorepo_structure(self, tmp_path):
        """Create a typical monorepo directory structure for testing."""
        # Create monorepo structure:
        # tmp_path/avatar_repo/
        #   services/api/
        #   avatar/
        #   core/
        #   dp/
        repo_root = tmp_path / "avatar_repo"
        repo_root.mkdir()

        api_dir = repo_root / "services" / "api"
        api_dir.mkdir(parents=True)

        avatar_dir = repo_root / "avatar"
        avatar_dir.mkdir()

        core_dir = repo_root / "core"
        core_dir.mkdir()

        dp_dir = repo_root / "dp"
        dp_dir.mkdir()

        return {
            "repo_root": repo_root,
            "api_dir": api_dir,
            "avatar_dir": avatar_dir,
            "core_dir": core_dir,
            "dp_dir": dp_dir,
        }

    def test_step_metadata(self, step):
        """Test step metadata."""
        assert step.name == "api_local_source"
        assert step.required is True
        assert "api" in step.description.lower()
        assert "source" in step.description.lower()

    def test_modes_dev_only(self, step):
        """Test that step only runs in dev mode."""
        assert step.modes == [DeploymentMode.DEV]
        assert DeploymentMode.DEV in step.modes
        assert DeploymentMode.PRODUCTION not in step.modes

    def test_collect_config_noninteractive(self, tmp_path, monorepo_structure):
        """Test configuration collection in non-interactive mode."""
        defaults = {
            "local_source": {
                "api_source_path": str(monorepo_structure["api_dir"]),
            }
        }
        config = {}

        step = ApiLocalSourceStep(tmp_path, defaults, config, interactive=False)
        collected = step.collect_config()

        assert "API_SOURCE_PATH" in collected
        assert "API_CONTEXT_AVATAR" in collected
        assert "API_CONTEXT_CORE" in collected
        assert "API_CONTEXT_DP" in collected

        assert collected["API_SOURCE_PATH"] == str(monorepo_structure["api_dir"])
        assert collected["API_CONTEXT_AVATAR"] == str(monorepo_structure["avatar_dir"])
        assert collected["API_CONTEXT_CORE"] == str(monorepo_structure["core_dir"])
        assert collected["API_CONTEXT_DP"] == str(monorepo_structure["dp_dir"])

    def test_collect_config_from_preloaded_config(self, tmp_path, monorepo_structure):
        """Test that preloaded config takes precedence."""
        config = {
            "API_SOURCE_PATH": str(monorepo_structure["api_dir"]),
        }

        defaults = {
            "local_source": {
                "api_source_path": "/wrong/path",
            }
        }

        step = ApiLocalSourceStep(tmp_path, defaults, config, interactive=False)
        collected = step.collect_config()

        assert collected["API_SOURCE_PATH"] == str(monorepo_structure["api_dir"])
        assert collected["API_CONTEXT_AVATAR"] == str(monorepo_structure["avatar_dir"])

    def test_path_derivation_logic(self, tmp_path, monorepo_structure):
        """Test that additional context paths are correctly derived."""
        defaults = {
            "local_source": {
                "api_source_path": str(monorepo_structure["api_dir"]),
            }
        }

        step = ApiLocalSourceStep(tmp_path, defaults, {}, interactive=False)
        collected = step.collect_config()

        # Verify paths are derived from parent directory structure
        repo_root = monorepo_structure["repo_root"]

        assert collected["API_CONTEXT_AVATAR"] == str(repo_root / "avatar")
        assert collected["API_CONTEXT_CORE"] == str(repo_root / "core")
        assert collected["API_CONTEXT_DP"] == str(repo_root / "dp")

    def test_api_path_missing(self, tmp_path):
        """Test that missing API directory raises ValueError."""
        defaults = {
            "local_source": {
                "api_source_path": "/nonexistent/path",
            }
        }

        step = ApiLocalSourceStep(tmp_path, defaults, {}, interactive=False)

        with pytest.raises(ValueError, match="does not exist"):
            step.collect_config()

    def test_api_path_not_directory(self, tmp_path):
        """Test that API path being a file raises ValueError."""
        api_file = tmp_path / "api.txt"
        api_file.write_text("not a directory")

        defaults = {
            "local_source": {
                "api_source_path": str(api_file),
            }
        }

        step = ApiLocalSourceStep(tmp_path, defaults, {}, interactive=False)

        with pytest.raises(ValueError, match="not a directory"):
            step.collect_config()

    def test_missing_avatar_context(self, tmp_path):
        """Test that missing avatar context directory raises ValueError."""
        # Create incomplete structure - missing avatar/
        repo_root = tmp_path / "avatar_repo"
        api_dir = repo_root / "services" / "api"
        api_dir.mkdir(parents=True)

        core_dir = repo_root / "core"
        core_dir.mkdir()

        dp_dir = repo_root / "dp"
        dp_dir.mkdir()

        # Note: avatar/ is NOT created

        defaults = {
            "local_source": {
                "api_source_path": str(api_dir),
            }
        }

        step = ApiLocalSourceStep(tmp_path, defaults, {}, interactive=False)

        with pytest.raises(ValueError, match="avatar.*does not exist"):
            step.collect_config()

    def test_missing_core_context(self, tmp_path):
        """Test that missing core context directory raises ValueError."""
        # Create incomplete structure - missing core/
        repo_root = tmp_path / "avatar_repo"
        api_dir = repo_root / "services" / "api"
        api_dir.mkdir(parents=True)

        avatar_dir = repo_root / "avatar"
        avatar_dir.mkdir()

        dp_dir = repo_root / "dp"
        dp_dir.mkdir()

        # Note: core/ is NOT created

        defaults = {
            "local_source": {
                "api_source_path": str(api_dir),
            }
        }

        step = ApiLocalSourceStep(tmp_path, defaults, {}, interactive=False)

        with pytest.raises(ValueError, match="core.*does not exist"):
            step.collect_config()

    def test_missing_dp_context(self, tmp_path):
        """Test that missing dp context directory raises ValueError."""
        # Create incomplete structure - missing dp/
        repo_root = tmp_path / "avatar_repo"
        api_dir = repo_root / "services" / "api"
        api_dir.mkdir(parents=True)

        avatar_dir = repo_root / "avatar"
        avatar_dir.mkdir()

        core_dir = repo_root / "core"
        core_dir.mkdir()

        # Note: dp/ is NOT created

        defaults = {
            "local_source": {
                "api_source_path": str(api_dir),
            }
        }

        step = ApiLocalSourceStep(tmp_path, defaults, {}, interactive=False)

        with pytest.raises(ValueError, match="dp.*does not exist"):
            step.collect_config()

    def test_context_path_is_file_not_directory(self, tmp_path):
        """Test that context path being a file (not directory) raises ValueError."""
        # Create structure but make avatar a file instead of directory
        repo_root = tmp_path / "avatar_repo"
        api_dir = repo_root / "services" / "api"
        api_dir.mkdir(parents=True)

        # Create avatar as a file
        avatar_file = repo_root / "avatar"
        avatar_file.write_text("not a directory")

        core_dir = repo_root / "core"
        core_dir.mkdir()

        dp_dir = repo_root / "dp"
        dp_dir.mkdir()

        defaults = {
            "local_source": {
                "api_source_path": str(api_dir),
            }
        }

        step = ApiLocalSourceStep(tmp_path, defaults, {}, interactive=False)

        with pytest.raises(ValueError, match="avatar.*not a directory"):
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

        result = ApiLocalSourceStep._validate_directory_path(str(test_dir))
        assert isinstance(result, ValidationSuccess)
        assert result.value == str(test_dir)

    def test_validate_directory_path_not_exists(self):
        """Test directory path validation with non-existent path."""
        result = ApiLocalSourceStep._validate_directory_path("/nonexistent/path")
        assert isinstance(result, ValidationError)
        assert "does not exist" in result.message

    def test_validate_directory_path_is_file(self, tmp_path):
        """Test directory path validation with file instead of directory."""
        test_file = tmp_path / "test_file.txt"
        test_file.write_text("test")

        result = ApiLocalSourceStep._validate_directory_path(str(test_file))
        assert isinstance(result, ValidationError)
        assert "not a directory" in result.message

    def test_path_expansion_with_tilde(self, tmp_path, monorepo_structure, monkeypatch):
        """Test that tilde (~) in paths is properly expanded."""
        # Create a mock home directory
        fake_home = tmp_path / "fake_home"
        fake_home.mkdir()

        # Create monorepo under fake home
        repo_root = fake_home / "avatar_repo"
        repo_root.mkdir()

        api_dir = repo_root / "services" / "api"
        api_dir.mkdir(parents=True)

        avatar_dir = repo_root / "avatar"
        avatar_dir.mkdir()

        core_dir = repo_root / "core"
        core_dir.mkdir()

        dp_dir = repo_root / "dp"
        dp_dir.mkdir()

        # Mock HOME environment variable
        monkeypatch.setenv("HOME", str(fake_home))

        # Use tilde in path
        defaults = {
            "local_source": {
                "api_source_path": "~/avatar_repo/services/api",
            }
        }

        step = ApiLocalSourceStep(tmp_path, defaults, {}, interactive=False)
        collected = step.collect_config()

        # Verify paths are expanded and correctly derived
        assert str(api_dir) in collected["API_SOURCE_PATH"]
        assert str(avatar_dir) in collected["API_CONTEXT_AVATAR"]
