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

    def test_init_default_template_from(self, temp_output_dir):
        """Test initialization with default template source (github)."""
        runner = DeploymentRunner(output_dir=temp_output_dir)

        assert runner.output_dir == temp_output_dir
        assert runner.templates_dir == temp_output_dir / ".avatar-templates"
        assert runner.template_from == "github"
        assert runner.verbose is False

    def test_init_local_template_source(self, temp_output_dir, mock_docker_source):
        """Test initialization with local template source."""
        runner = DeploymentRunner(output_dir=temp_output_dir, template_from=str(mock_docker_source))

        assert runner.output_dir == temp_output_dir
        assert runner.template_from == str(mock_docker_source)
        # Templates are always stored at output_dir/.avatar-templates
        assert runner.templates_dir == temp_output_dir / ".avatar-templates"

    def test_init_verbose_enabled(self, temp_output_dir):
        """Test initialization with verbose output enabled."""
        runner = DeploymentRunner(output_dir=temp_output_dir, verbose=True)

        assert runner.verbose is True

    def test_init_string_paths(self):
        """Test initialization with string paths instead of Path objects."""
        with tempfile.TemporaryDirectory() as tmpdir:
            template_source = str(Path(tmpdir) / "templates")
            runner = DeploymentRunner(output_dir=str(tmpdir), template_from=template_source)

            assert isinstance(runner.output_dir, Path)
            assert runner.output_dir == Path(tmpdir)
            assert runner.template_from == template_source
            # Templates dir always at output_dir/.avatar-templates
            assert runner.templates_dir == Path(tmpdir) / ".avatar-templates"

    def test_verify_templates_success(self, temp_output_dir, temp_templates_dir):
        """Test template verification with valid templates."""
        # Copy templates to the expected location using shutil
        import shutil

        templates_dir = temp_output_dir / ".avatar-templates"
        shutil.copytree(temp_templates_dir, templates_dir)

        runner = DeploymentRunner(
            output_dir=temp_output_dir,
            template_from=str(temp_templates_dir),
        )

        result = runner._verify_templates()

        assert result is True

    def test_verify_templates_no_directory(self, temp_output_dir):
        """Test template verification when directory doesn't exist."""
        # Templates dir doesn't exist yet
        runner = DeploymentRunner(
            output_dir=temp_output_dir,
            template_from="github",
            verbose=True,
        )

        result = runner._verify_templates()

        assert result is False

    def test_verify_templates_empty_directory(self, temp_output_dir):
        """Test template verification with empty templates directory."""
        # Create empty templates directory
        templates_dir = temp_output_dir / ".avatar-templates"
        templates_dir.mkdir()

        runner = DeploymentRunner(
            output_dir=temp_output_dir,
            template_from="github",
            verbose=True,
        )

        result = runner._verify_templates()

        assert result is False

    def test_ensure_templates_with_local_source(self, temp_output_dir, mock_docker_source):
        """Test ensure_templates with local template source."""
        runner = DeploymentRunner(
            output_dir=temp_output_dir,
            template_from=str(mock_docker_source),
            verbose=True,
        )

        result = runner.ensure_templates()

        # Should have copied templates successfully
        assert result is True
        # Verify templates were copied to the expected location
        assert (temp_output_dir / ".avatar-templates" / ".env.template").exists()
        assert (temp_output_dir / ".avatar-templates" / "nginx.conf.template").exists()
        assert (temp_output_dir / ".avatar-templates" / "docker-compose.yml").exists()

    def test_ensure_templates_local_source_not_found(self, temp_output_dir):
        """Test ensure_templates with non-existent local template source."""
        non_existent = temp_output_dir / "non-existent"

        runner = DeploymentRunner(
            output_dir=temp_output_dir,
            template_from=str(non_existent),
        )

        result = runner.ensure_templates()

        assert result is False

    @patch("octopize_avatar_deploy.configure.DeploymentConfigurator")
    def test_run_success(self, mock_configurator_class, temp_output_dir, mock_docker_source):
        """Test successful run of deployment process."""
        # Setup mock
        mock_configurator = MagicMock()
        mock_configurator_class.return_value = mock_configurator

        (temp_output_dir / ".avatar-templates").mkdir(parents=True, exist_ok=True)

        runner = DeploymentRunner(
            output_dir=temp_output_dir,
            template_from=str(mock_docker_source),
        )

        runner.run(interactive=False, save_config=True)

        # Verify configurator was created correctly
        assert mock_configurator_class.call_count == 1
        call_kwargs = mock_configurator_class.call_args[1]
        assert call_kwargs["templates_dir"] == temp_output_dir / ".avatar-templates"
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
        self, mock_configurator_class, temp_output_dir, mock_docker_source
    ):
        """Test run with config file parameter."""
        mock_configurator = MagicMock()
        mock_configurator_class.return_value = mock_configurator

        config_file = temp_output_dir / "config.yaml"
        config_file.write_text("key: value")

        runner = DeploymentRunner(
            output_dir=temp_output_dir,
            template_from=str(mock_docker_source),
        )

        runner.run(config_file=config_file)

        mock_configurator.run.assert_called_once_with(
            interactive=True,
            config_file=config_file,
            save_config=False,
        )

    def test_run_no_templates_raises_error(self, temp_output_dir):
        """Test run raises RuntimeError when templates are not available."""
        non_existent = temp_output_dir / "non-existent"
        runner = DeploymentRunner(
            output_dir=temp_output_dir,
            template_from=str(non_existent),
        )

        with pytest.raises(RuntimeError, match="Templates not available"):
            runner.run()

    def test_run_downloads_templates_before_configure(self, temp_output_dir):
        """Test run ensures templates are provided before configurator runs."""
        with patch(
            "octopize_avatar_deploy.configure.DeploymentRunner._verify_templates",
            return_value=True,
        ):
            with patch(
                "octopize_avatar_deploy.configure.GitHubTemplateProvider"
            ) as mock_provider_class:
                with patch(
                    "octopize_avatar_deploy.configure.DeploymentConfigurator"
                ) as mock_configurator_class:
                    mock_provider = MagicMock()
                    mock_provider.check_cached_templates.return_value = False

                    def _provide_all(dest_dir):
                        dest_dir.mkdir(parents=True, exist_ok=True)
                        return True

                    mock_provider.provide_all.side_effect = _provide_all
                    mock_provider_class.return_value = mock_provider

                    mock_configurator = MagicMock()
                    mock_configurator_class.return_value = mock_configurator

                    runner = DeploymentRunner(
                        output_dir=temp_output_dir,
                        template_from="github",
                    )

                    runner.run(interactive=False)

                    mock_provider.provide_all.assert_called_once_with(
                        temp_output_dir / ".avatar-templates"
                    )
                    mock_configurator.run.assert_called_once()

    def test_all_constructor_parameters_combination(self, temp_output_dir, mock_docker_source):
        """Test that all constructor parameters can be used together."""
        runner = DeploymentRunner(
            output_dir=str(temp_output_dir),
            template_from=str(mock_docker_source),
            verbose=True,
        )

        assert runner.output_dir == temp_output_dir
        assert runner.template_from == str(mock_docker_source)
        assert runner.templates_dir == temp_output_dir / ".avatar-templates"
        assert runner.verbose is True

        # Verify templates are copied successfully
        result = runner.ensure_templates()
        assert result is True
        # Verify templates were copied
        assert (temp_output_dir / ".avatar-templates" / ".env.template").exists()

    def test_verbose_prints_messages(self, temp_output_dir, mock_docker_source, capsys):
        """Test that verbose mode prints informative messages."""
        runner = DeploymentRunner(
            output_dir=temp_output_dir,
            template_from=str(mock_docker_source),
            verbose=True,
        )

        with patch("octopize_avatar_deploy.configure.LocalTemplateProvider") as mock_provider:
            mock_provider_instance = MagicMock()
            mock_provider_instance.provide_all.return_value = True
            mock_provider.return_value = mock_provider_instance

            runner.ensure_templates()

        captured = capsys.readouterr()
        assert "Copying templates" in captured.out
        assert str(mock_docker_source) in captured.out

    def test_verbose_false_no_prints(self, temp_output_dir, mock_docker_source, capsys):
        """Test that verbose=False suppresses informational messages."""
        runner = DeploymentRunner(
            output_dir=temp_output_dir,
            template_from=str(mock_docker_source),
            verbose=False,
        )

        with patch("octopize_avatar_deploy.configure.LocalTemplateProvider") as mock_provider:
            mock_provider_instance = MagicMock()
            mock_provider_instance.provide_all.return_value = True
            mock_provider.return_value = mock_provider_instance

            runner.ensure_templates()

        captured = capsys.readouterr()
        assert "Copying templates" not in captured.out
