#!/usr/bin/env python3
"""Integration tests for DeploymentRunner class."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from octopize_avatar_deploy.configure import DeploymentRunner


class TestDeploymentRunner:
    """Test the DeploymentRunner orchestrator class."""

    @pytest.fixture
    def temp_output_dir(self):
        """Create a temporary output directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def temp_templates_dir(self):
        """Create a temporary templates directory with mock templates."""
        with tempfile.TemporaryDirectory() as tmpdir:
            templates_dir = Path(tmpdir)
            # Create mock template files
            (templates_dir / ".env.template").write_text("# Mock env template")
            (templates_dir / "nginx.conf.template").write_text("# Mock nginx template")
            yield templates_dir

    def test_init_default_templates_dir(self, temp_output_dir):
        """Test initialization with default templates directory."""
        runner = DeploymentRunner(output_dir=temp_output_dir)

        assert runner.output_dir == temp_output_dir
        assert runner.templates_dir == temp_output_dir / ".avatar-templates"
        assert runner.download_branch == "main"
        assert runner.skip_download is False
        assert runner.verbose is False

    def test_init_custom_templates_dir(self, temp_output_dir, temp_templates_dir):
        """Test initialization with custom templates directory."""
        runner = DeploymentRunner(
            output_dir=temp_output_dir, templates_dir=temp_templates_dir
        )

        assert runner.output_dir == temp_output_dir
        assert runner.templates_dir == temp_templates_dir
        assert runner.templates_dir != temp_output_dir / ".avatar-templates"

    def test_init_custom_branch(self, temp_output_dir):
        """Test initialization with custom download branch."""
        runner = DeploymentRunner(output_dir=temp_output_dir, download_branch="develop")

        assert runner.download_branch == "develop"

    def test_init_skip_download_enabled(self, temp_output_dir):
        """Test initialization with skip_download enabled."""
        runner = DeploymentRunner(output_dir=temp_output_dir, skip_download=True)

        assert runner.skip_download is True

    def test_init_verbose_enabled(self, temp_output_dir):
        """Test initialization with verbose output enabled."""
        runner = DeploymentRunner(output_dir=temp_output_dir, verbose=True)

        assert runner.verbose is True

    def test_init_string_paths(self):
        """Test initialization with string paths instead of Path objects."""
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = DeploymentRunner(
                output_dir=str(tmpdir), templates_dir=str(Path(tmpdir) / "templates")
            )

            assert isinstance(runner.output_dir, Path)
            assert isinstance(runner.templates_dir, Path)
            assert runner.output_dir == Path(tmpdir)
            assert runner.templates_dir == Path(tmpdir) / "templates"

    def test_verify_templates_success(self, temp_output_dir, temp_templates_dir):
        """Test template verification with valid templates."""
        runner = DeploymentRunner(
            output_dir=temp_output_dir,
            templates_dir=temp_templates_dir,
            skip_download=True,
        )

        result = runner._verify_templates()

        assert result is True

    def test_verify_templates_no_directory(self, temp_output_dir):
        """Test template verification when directory doesn't exist."""
        non_existent_dir = temp_output_dir / "non-existent"
        runner = DeploymentRunner(
            output_dir=temp_output_dir,
            templates_dir=non_existent_dir,
            skip_download=True,
            verbose=True,
        )

        result = runner._verify_templates()

        assert result is False

    def test_verify_templates_empty_directory(self, temp_output_dir):
        """Test template verification with empty templates directory."""
        empty_dir = temp_output_dir / "empty"
        empty_dir.mkdir()
        runner = DeploymentRunner(
            output_dir=temp_output_dir,
            templates_dir=empty_dir,
            skip_download=True,
            verbose=True,
        )

        result = runner._verify_templates()

        assert result is False

    def test_ensure_templates_with_skip_download(
        self, temp_output_dir, temp_templates_dir
    ):
        """Test ensure_templates when skip_download is True."""
        runner = DeploymentRunner(
            output_dir=temp_output_dir,
            templates_dir=temp_templates_dir,
            skip_download=True,
            verbose=True,
        )

        with patch("octopize_avatar_deploy.configure.download_templates") as mock_dl:
            result = runner.ensure_templates()

            # Should not call download_templates
            mock_dl.assert_not_called()
            assert result is True

    @patch("octopize_avatar_deploy.configure.download_templates")
    def test_ensure_templates_with_download_success(
        self, mock_download, temp_output_dir, temp_templates_dir
    ):
        """Test ensure_templates with successful download."""
        mock_download.return_value = True

        runner = DeploymentRunner(
            output_dir=temp_output_dir,
            templates_dir=temp_templates_dir,
            skip_download=False,
            verbose=True,
        )

        # Pre-create templates to pass verification
        result = runner.ensure_templates()

        # Should call download_templates
        mock_download.assert_called_once_with(
            output_dir=temp_templates_dir,
            force=False,
            branch="main",
            verbose=True,
        )
        assert result is True

    @patch("octopize_avatar_deploy.configure.download_templates")
    def test_ensure_templates_with_download_failure(
        self, mock_download, temp_output_dir
    ):
        """Test ensure_templates with download failure and no cache."""
        mock_download.return_value = False

        non_existent_dir = temp_output_dir / "templates"
        runner = DeploymentRunner(
            output_dir=temp_output_dir,
            templates_dir=non_existent_dir,
            skip_download=False,
            verbose=True,
        )

        result = runner.ensure_templates()

        mock_download.assert_called_once()
        assert result is False

    @patch("octopize_avatar_deploy.configure.download_templates")
    def test_ensure_templates_custom_branch(
        self, mock_download, temp_output_dir, temp_templates_dir
    ):
        """Test ensure_templates uses custom branch for download."""
        mock_download.return_value = True

        runner = DeploymentRunner(
            output_dir=temp_output_dir,
            templates_dir=temp_templates_dir,
            download_branch="develop",
            skip_download=False,
        )

        runner.ensure_templates()

        mock_download.assert_called_once_with(
            output_dir=temp_templates_dir,
            force=False,
            branch="develop",  # Should use custom branch
            verbose=False,
        )

    @patch("octopize_avatar_deploy.configure.DeploymentConfigurator")
    def test_run_success(
        self, mock_configurator_class, temp_output_dir, temp_templates_dir
    ):
        """Test successful run of deployment process."""
        # Setup mock
        mock_configurator = MagicMock()
        mock_configurator_class.return_value = mock_configurator

        runner = DeploymentRunner(
            output_dir=temp_output_dir,
            templates_dir=temp_templates_dir,
            skip_download=True,
        )

        runner.run(interactive=False, save_config=True)

        # Verify configurator was created correctly
        assert mock_configurator_class.call_count == 1
        call_kwargs = mock_configurator_class.call_args[1]
        assert call_kwargs["templates_dir"] == temp_templates_dir
        assert call_kwargs["output_dir"] == temp_output_dir
        assert "printer" in call_kwargs

        # Verify run was called with correct args
        mock_configurator.run.assert_called_once_with(
            interactive=False,
            config_file=None,
            save_config=True,
        )

    @patch("octopize_avatar_deploy.configure.DeploymentConfigurator")
    def test_run_with_config_file(
        self, mock_configurator_class, temp_output_dir, temp_templates_dir
    ):
        """Test run with config file parameter."""
        mock_configurator = MagicMock()
        mock_configurator_class.return_value = mock_configurator

        config_file = temp_output_dir / "config.yaml"
        config_file.write_text("key: value")

        runner = DeploymentRunner(
            output_dir=temp_output_dir,
            templates_dir=temp_templates_dir,
            skip_download=True,
        )

        runner.run(config_file=config_file)

        mock_configurator.run.assert_called_once_with(
            interactive=True,
            config_file=config_file,
            save_config=False,
        )

    def test_run_no_templates_raises_error(self, temp_output_dir):
        """Test run raises RuntimeError when templates are not available."""
        non_existent_dir = temp_output_dir / "non-existent"
        runner = DeploymentRunner(
            output_dir=temp_output_dir,
            templates_dir=non_existent_dir,
            skip_download=True,
        )

        with pytest.raises(RuntimeError, match="Templates not available"):
            runner.run()

    @patch("octopize_avatar_deploy.configure.download_templates")
    @patch("octopize_avatar_deploy.configure.DeploymentConfigurator")
    def test_run_downloads_templates_before_configure(
        self, mock_configurator_class, mock_download, temp_output_dir
    ):
        """Test run ensures templates are downloaded before configurator runs."""
        mock_download.return_value = True
        mock_configurator = MagicMock()
        mock_configurator_class.return_value = mock_configurator

        templates_dir = temp_output_dir / "templates"
        templates_dir.mkdir()
        (templates_dir / ".env.template").write_text("# Mock")

        runner = DeploymentRunner(
            output_dir=temp_output_dir,
            templates_dir=templates_dir,
            skip_download=False,
            download_branch="feature/test",
        )

        runner.run(interactive=False)

        # Should download first
        mock_download.assert_called_once_with(
            output_dir=templates_dir,
            force=False,
            branch="feature/test",
            verbose=False,
        )

        # Then configure
        mock_configurator.run.assert_called_once()

    def test_all_constructor_parameters_combination(
        self, temp_output_dir, temp_templates_dir
    ):
        """Test that all constructor parameters can be used together."""
        runner = DeploymentRunner(
            output_dir=str(temp_output_dir),
            templates_dir=str(temp_templates_dir),
            download_branch="staging",
            skip_download=True,
            verbose=True,
        )

        assert runner.output_dir == temp_output_dir
        assert runner.templates_dir == temp_templates_dir
        assert runner.download_branch == "staging"
        assert runner.skip_download is True
        assert runner.verbose is True

        # Verify all parameters are actually used
        with patch("octopize_avatar_deploy.configure.download_templates") as mock_dl:
            result = runner.ensure_templates()

            # skip_download=True means no download
            mock_dl.assert_not_called()
            # Should still verify templates
            assert result is True

    def test_verbose_prints_messages(self, temp_output_dir, temp_templates_dir, capsys):
        """Test that verbose mode prints informative messages."""
        runner = DeploymentRunner(
            output_dir=temp_output_dir,
            templates_dir=temp_templates_dir,
            skip_download=True,
            verbose=True,
        )

        runner.ensure_templates()

        captured = capsys.readouterr()
        assert "Skipping download" in captured.out
        assert str(temp_templates_dir) in captured.out

    def test_verbose_false_no_prints(self, temp_output_dir, temp_templates_dir, capsys):
        """Test that verbose=False suppresses informational messages."""
        runner = DeploymentRunner(
            output_dir=temp_output_dir,
            templates_dir=temp_templates_dir,
            skip_download=True,
            verbose=False,
        )

        runner.ensure_templates()

        captured = capsys.readouterr()
        assert "Skipping download" not in captured.out
