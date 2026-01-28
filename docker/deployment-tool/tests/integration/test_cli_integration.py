"""
Integration tests for CLI using CLITestHarness - simplified version.

These tests verify end-to-end CLI behavior with various argument combinations
focusing on successful execution rather than output comparison.
"""

# Import fixture utilities
import io
import sys
from pathlib import Path

import pytest
import yaml

from octopize_avatar_deploy.cli_test_harness import CLITestHarness
from tests.conftest import compare_generated_files, compare_output
from tests.fixtures import FixtureManager

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"
fixture_manager = FixtureManager(FIXTURES_DIR)


class TestCLIBasicCommands:
    """Test basic CLI commands and arguments."""

    def test_help_flag(self):
        """Test --help flag."""

        # Capture stdout since --help writes to stdout and exits early
        old_stdout = sys.stdout
        sys.stdout = captured_output = io.StringIO()

        try:
            harness = CLITestHarness(responses=[], args=["--help"], silent=True)
            exit_code = harness.run()
        finally:
            sys.stdout = old_stdout

        assert exit_code == 0

        # Compare output
        actual_output = captured_output.getvalue()
        expected_output = fixture_manager.load_expected_output("help")
        assert fixture_manager.compare_output(actual_output, expected_output, fixture_name="help")


class TestCLIDeploymentScenarios:
    """Test complete deployment scenarios."""

    @pytest.mark.parametrize(
        "scenario",
        [
            "basic_deployment",
            "cloud_storage",
            "no_telemetry",
        ],
    )
    def test_deployment_scenarios(self, scenario, temp_deployment_dir, log_file, docker_templates_dir):
        """Test various deployment scenarios with different configurations."""
        responses = fixture_manager.load_input_fixture(scenario)

        harness = CLITestHarness(
            responses=responses,
            args=[
                "--output-dir",
                str(temp_deployment_dir),
                "--template-from",
                str(docker_templates_dir),
            ],
            log_file=str(log_file),
        )
        exit_code = harness.run()

        assert exit_code == 0
        assert compare_output(log_file, temp_deployment_dir, scenario, fixture_manager)

        # Verify generated configuration files
        assert compare_generated_files(temp_deployment_dir, scenario, FIXTURES_DIR)


class TestCLIErrorHandling:
    """Test CLI error handling."""

    def test_missing_templates_directory(self, temp_deployment_dir, log_file):
        """Test behavior when template source directory doesn't exist."""
        non_existent = temp_deployment_dir / "non-existent-templates"
        harness = CLITestHarness(
            responses=[],
            args=["--output-dir", str(temp_deployment_dir), "--template-from", str(non_existent)],
            log_file=str(log_file),
        )
        exit_code = harness.run()
        assert exit_code != 0
        assert compare_output(log_file, temp_deployment_dir, "missing_templates", fixture_manager)


class TestCLINonInteractiveMode:
    """Test non-interactive mode."""

    def test_non_interactive_with_config(self, temp_deployment_dir, log_file, docker_templates_dir):
        """Test non-interactive mode with config file."""
        config_data = {
            "base_url": "https://test.local",
            "django_secret_key": "test-key",
            "admin_email": "admin@test.local",
        }
        config_file = temp_deployment_dir / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        harness = CLITestHarness(
            responses=[],
            args=[
                "--output-dir",
                str(temp_deployment_dir),
                "--config",
                str(config_file),
                "--non-interactive",
                "--template-from",
                str(docker_templates_dir),
            ],
            log_file=str(log_file),
        )
        exit_code = harness.run()

        # With incomplete config, should either succeed with defaults or fail
        # The exact behavior depends on implementation
        assert exit_code in (0, 1)
        assert compare_output(log_file, temp_deployment_dir, "non_interactive_incomplete_config", fixture_manager)


class TestCLIDifferentStorageBackends:
    """Test all supported storage backends."""

    @pytest.mark.parametrize(
        "storage_backend,extra_responses",
        [
            ("seaweedfs", ["s3.local:8333", "avatar-bucket"]),
        ],
    )
    def test_storage_backend_configurations(
        self, temp_deployment_dir, log_file, docker_templates_dir, storage_backend, extra_responses
    ):
        """Test different storage backend configurations."""
        base_responses = [
            "https://avatar.test.com",
            "admin@test.com",
            "smtp.test.com",
            "587",
            "noreply@test.com",
            "user",
            "pass",
            "postgres.local",
            "avatar",
            "avatar_user",
        ]
        responses = base_responses + [storage_backend] + extra_responses + ["30d", True, "test"]

        harness = CLITestHarness(
            responses=responses,
            args=[
                "--output-dir",
                str(temp_deployment_dir),
                "--template-from",
                str(docker_templates_dir),
            ],
            log_file=str(log_file),
        )
        exit_code = harness.run()

        assert exit_code == 0
        assert compare_output(log_file, temp_deployment_dir, f"storage_{storage_backend}", fixture_manager)

        # Verify generated configuration files
        assert compare_generated_files(temp_deployment_dir, f"storage_{storage_backend}", FIXTURES_DIR)
