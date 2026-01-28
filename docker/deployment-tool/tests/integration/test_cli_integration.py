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


class TestConfigFileErrorHandling:
    """Test config file error handling - HIGH PRIORITY."""

    def test_config_file_not_found(self, temp_deployment_dir, log_file, docker_templates_dir):
        """Test error when config file doesn't exist."""
        non_existent_config = temp_deployment_dir / "missing-config.yaml"

        harness = CLITestHarness(
            responses=[],
            args=[
                "--config",
                str(non_existent_config),
                "--output-dir",
                str(temp_deployment_dir),
                "--template-from",
                str(docker_templates_dir),
            ],
            log_file=str(log_file),
        )
        exit_code = harness.run()

        assert exit_code != 0
        assert compare_output(log_file, temp_deployment_dir, "config_not_found", fixture_manager)

    def test_malformed_yaml_config(self, temp_deployment_dir, log_file, docker_templates_dir):
        """Test error when config file has invalid YAML syntax."""
        malformed_config = temp_deployment_dir / "malformed.yaml"
        malformed_config.write_text("base_url: invalid\n\ttabs_not_allowed: true\n  - broken list")

        harness = CLITestHarness(
            responses=[],
            args=[
                "--config",
                str(malformed_config),
                "--output-dir",
                str(temp_deployment_dir),
                "--template-from",
                str(docker_templates_dir),
            ],
            log_file=str(log_file),
        )
        exit_code = harness.run()

        assert exit_code != 0
        assert compare_output(log_file, temp_deployment_dir, "malformed_yaml", fixture_manager)

    def test_invalid_url_in_config(self, temp_deployment_dir, log_file, docker_templates_dir):
        """Test behavior when config contains invalid URL format.
        
        Note: Currently the tool does not validate URL format, so invalid URLs
        will be accepted. This test documents the current behavior.
        """
        invalid_config = temp_deployment_dir / "invalid_url.yaml"
        config_data = {
            "base_url": "not-a-valid-url",
            "admin_email": "admin@test.com",
        }
        with open(invalid_config, "w") as f:
            yaml.dump(config_data, f)

        harness = CLITestHarness(
            responses=[],
            args=[
                "--config",
                str(invalid_config),
                "--non-interactive",
                "--output-dir",
                str(temp_deployment_dir),
                "--template-from",
                str(docker_templates_dir),
            ],
            log_file=str(log_file),
        )
        exit_code = harness.run()

        # Currently accepts invalid URLs - may change in future
        # Document actual behavior in fixture
        assert compare_output(log_file, temp_deployment_dir, "invalid_url_config", fixture_manager)

    def test_invalid_port_in_config(self, temp_deployment_dir, log_file, docker_templates_dir):
        """Test behavior when config contains invalid port number.
        
        Note: YAML will parse "not-a-number" as a string, not an int.
        This test documents how the tool handles type mismatches.
        """
        invalid_config = temp_deployment_dir / "invalid_port.yaml"
        config_data = {
            "base_url": "https://avatar.test.com",
            "smtp_host": "smtp.test.com",
            "smtp_port": "not-a-number",
        }
        with open(invalid_config, "w") as f:
            yaml.dump(config_data, f)

        harness = CLITestHarness(
            responses=[],
            args=[
                "--config",
                str(invalid_config),
                "--non-interactive",
                "--output-dir",
                str(temp_deployment_dir),
                "--template-from",
                str(docker_templates_dir),
            ],
            log_file=str(log_file),
        )
        exit_code = harness.run()

        # Document actual behavior in fixture
        assert compare_output(log_file, temp_deployment_dir, "invalid_port_config", fixture_manager)

    def test_type_mismatch_in_config(self, temp_deployment_dir, log_file, docker_templates_dir):
        """Test error when config contains type mismatches."""
        invalid_config = temp_deployment_dir / "type_mismatch.yaml"
        config_data = {
            "base_url": "https://avatar.test.com",
            "enable_telemetry": "yes",  # Should be boolean
        }
        with open(invalid_config, "w") as f:
            yaml.dump(config_data, f)

        harness = CLITestHarness(
            responses=[],
            args=[
                "--config",
                str(invalid_config),
                "--non-interactive",
                "--output-dir",
                str(temp_deployment_dir),
                "--template-from",
                str(docker_templates_dir),
            ],
            log_file=str(log_file),
        )
        exit_code = harness.run()

        # Behavior depends on implementation - may succeed or fail
        # Document actual behavior in fixture
        assert compare_output(log_file, temp_deployment_dir, "type_mismatch_config", fixture_manager)


class TestNonInteractiveModeCompleteness:
    """Test non-interactive mode behavior - HIGH PRIORITY."""

    def test_non_interactive_with_complete_config(self, temp_deployment_dir, log_file, docker_templates_dir):
        """Test non-interactive mode with complete config - should succeed without prompts."""
        complete_config = temp_deployment_dir / "complete.yaml"
        config_data = {
            "base_url": "https://avatar.complete.com",
            "django_secret_key": "complete-secret-key-123",
            "admin_email": "admin@complete.com",
            "smtp_host": "smtp.complete.com",
            "smtp_port": 587,
            "smtp_from_address": "noreply@complete.com",
            "smtp_username": "smtp-user",
            "smtp_password": "smtp-pass",
            "db_host": "db.complete.com",
            "db_name": "avatar_complete",
            "db_user": "avatar_user",
            "storage_backend": "seaweedfs",
            "storage_endpoint": "s3.complete.com:8333",
            "storage_bucket": "avatar-data",
            "dataset_expiration": "30d",
            "enable_telemetry": True,
            "environment_name": "production",
        }
        with open(complete_config, "w") as f:
            yaml.dump(config_data, f)

        harness = CLITestHarness(
            responses=[],
            args=[
                "--config",
                str(complete_config),
                "--non-interactive",
                "--output-dir",
                str(temp_deployment_dir),
                "--template-from",
                str(docker_templates_dir),
            ],
            log_file=str(log_file),
        )
        exit_code = harness.run()

        assert exit_code == 0
        assert compare_output(log_file, temp_deployment_dir, "non_interactive_complete", fixture_manager)
        assert compare_generated_files(temp_deployment_dir, "non_interactive_complete", FIXTURES_DIR)

    def test_non_interactive_without_config(self, temp_deployment_dir, log_file, docker_templates_dir):
        """Test non-interactive mode without config file - should use all defaults or fail."""
        harness = CLITestHarness(
            responses=[],
            args=[
                "--non-interactive",
                "--output-dir",
                str(temp_deployment_dir),
                "--template-from",
                str(docker_templates_dir),
            ],
            log_file=str(log_file),
        )
        exit_code = harness.run()

        # Should either succeed with defaults or fail with clear message
        # Document actual behavior in fixture
        assert compare_output(log_file, temp_deployment_dir, "non_interactive_no_config", fixture_manager)

    def test_non_interactive_with_partial_config(self, temp_deployment_dir, log_file, docker_templates_dir):
        """Test non-interactive mode with partial config - should use defaults for missing values or fail."""
        partial_config = temp_deployment_dir / "partial.yaml"
        config_data = {
            "base_url": "https://avatar.partial.com",
            "admin_email": "admin@partial.com",
            # Missing: SMTP, DB, storage, etc.
        }
        with open(partial_config, "w") as f:
            yaml.dump(config_data, f)

        harness = CLITestHarness(
            responses=[],
            args=[
                "--config",
                str(partial_config),
                "--non-interactive",
                "--output-dir",
                str(temp_deployment_dir),
                "--template-from",
                str(docker_templates_dir),
            ],
            log_file=str(log_file),
        )
        exit_code = harness.run()

        # Document actual behavior - may succeed with defaults or fail
        assert compare_output(log_file, temp_deployment_dir, "non_interactive_partial_config", fixture_manager)


class TestSaveConfigRoundTrip:
    """Test save config and round-trip functionality - HIGH PRIORITY."""

    def test_save_config_in_interactive_mode(self, temp_deployment_dir, log_file, docker_templates_dir):
        """Test --save-config saves configuration correctly after interactive responses."""
        responses = fixture_manager.load_input_fixture("basic_deployment")

        harness = CLITestHarness(
            responses=responses,
            args=[
                "--output-dir",
                str(temp_deployment_dir),
                "--template-from",
                str(docker_templates_dir),
                "--save-config",
            ],
            log_file=str(log_file),
        )
        exit_code = harness.run()

        assert exit_code == 0

        # Verify deployment-config.yaml was created
        saved_config = temp_deployment_dir / "deployment-config.yaml"
        assert saved_config.exists(), "deployment-config.yaml should be created"

        # Verify it's valid YAML
        with open(saved_config) as f:
            config_data = yaml.safe_load(f)
            assert isinstance(config_data, dict)
            # Config is saved in .env format (PUBLIC_URL, etc)
            assert len(config_data) > 0, "Config should not be empty"

        assert compare_output(log_file, temp_deployment_dir, "save_config_interactive", fixture_manager)

    def test_save_config_with_existing_config(self, temp_deployment_dir, log_file, docker_templates_dir):
        """Test --save-config with --config loads existing, allows modification, then saves."""
        existing_config = temp_deployment_dir / "existing.yaml"
        config_data = {
            "base_url": "https://existing.com",
            "admin_email": "admin@existing.com",
        }
        with open(existing_config, "w") as f:
            yaml.dump(config_data, f)

        # Responses to override some values
        responses = [
            "https://modified.com",  # New base URL
            "admin@modified.com",  # New admin email
            "smtp.test.com",
            "587",
            "noreply@test.com",
            "user",
            "pass",
            "postgres.local",
            "avatar",
            "avatar_user",
            "seaweedfs",
            "s3.local:8333",
            "avatar-bucket",
            "30d",
            True,
            "production",
        ]

        harness = CLITestHarness(
            responses=responses,
            args=[
                "--config",
                str(existing_config),
                "--output-dir",
                str(temp_deployment_dir),
                "--template-from",
                str(docker_templates_dir),
                "--save-config",
            ],
            log_file=str(log_file),
        )
        exit_code = harness.run()

        assert exit_code == 0

        # Verify deployment-config.yaml was created
        saved_config = temp_deployment_dir / "deployment-config.yaml"
        assert saved_config.exists()

        assert compare_output(log_file, temp_deployment_dir, "save_config_with_existing", fixture_manager)

    def test_config_round_trip_validation(self, temp_deployment_dir, log_file, docker_templates_dir):
        """Test save config, then reload it - should produce identical output."""
        # First run: interactive mode with --save-config
        responses = fixture_manager.load_input_fixture("basic_deployment")

        first_dir = temp_deployment_dir / "first"
        first_dir.mkdir()
        first_log = first_dir / "output.log"

        harness1 = CLITestHarness(
            responses=responses,
            args=[
                "--output-dir",
                str(first_dir),
                "--template-from",
                str(docker_templates_dir),
                "--save-config",
            ],
            log_file=str(first_log),
        )
        exit_code1 = harness1.run()
        assert exit_code1 == 0

        saved_config = first_dir / "deployment-config.yaml"
        assert saved_config.exists()

        # Second run: non-interactive mode using saved config
        second_dir = temp_deployment_dir / "second"
        second_dir.mkdir()
        second_log = second_dir / "output.log"

        harness2 = CLITestHarness(
            responses=[],
            args=[
                "--config",
                str(saved_config),
                "--non-interactive",
                "--output-dir",
                str(second_dir),
                "--template-from",
                str(docker_templates_dir),
            ],
            log_file=str(second_log),
        )
        exit_code2 = harness2.run()
        assert exit_code2 == 0

        # Compare generated files (excluding secrets which are random)
        # This verifies the config round-trip produces consistent output
        assert compare_generated_files(first_dir, "config_round_trip_first", FIXTURES_DIR)
        assert compare_generated_files(second_dir, "config_round_trip_second", FIXTURES_DIR)


class TestOutputDirectoryEdgeCases:
    """Test output directory edge cases - HIGH PRIORITY."""

    def test_output_dir_is_current_directory(self, docker_templates_dir):
        """Test --output-dir . (current directory)."""
        import os
        import tempfile

        # Create a temp dir and change to it
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            log_file = tmppath / "output.log"
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                responses = fixture_manager.load_input_fixture("basic_deployment")

                harness = CLITestHarness(
                    responses=responses,
                    args=[
                        "--output-dir",
                        ".",
                        "--template-from",
                        str(docker_templates_dir),
                    ],
                    log_file=str(log_file),
                )
                exit_code = harness.run()

                assert exit_code == 0
                # Verify at least the .env file was created in current directory
                assert (tmppath / ".env").exists(), "Should create .env in current directory"

            finally:
                os.chdir(original_cwd)

    def test_output_dir_deeply_nested_nonexistent(self, temp_deployment_dir, log_file, docker_templates_dir):
        """Test creating deeply nested output directory that doesn't exist."""
        nested_dir = temp_deployment_dir / "deeply" / "nested" / "path" / "that" / "doesnt" / "exist"
        responses = fixture_manager.load_input_fixture("basic_deployment")

        harness = CLITestHarness(
            responses=responses,
            args=[
                "--output-dir",
                str(nested_dir),
                "--template-from",
                str(docker_templates_dir),
            ],
            log_file=str(log_file),
        )
        exit_code = harness.run()

        assert exit_code == 0
        assert nested_dir.exists()
        assert (nested_dir / ".env").exists()
        assert compare_output(log_file, nested_dir, "output_dir_nested", fixture_manager)

    def test_output_dir_with_spaces(self, temp_deployment_dir, log_file, docker_templates_dir):
        """Test output directory with spaces in path."""
        dir_with_spaces = temp_deployment_dir / "path with spaces"
        responses = fixture_manager.load_input_fixture("basic_deployment")

        harness = CLITestHarness(
            responses=responses,
            args=[
                "--output-dir",
                str(dir_with_spaces),
                "--template-from",
                str(docker_templates_dir),
            ],
            log_file=str(log_file),
        )
        exit_code = harness.run()

        assert exit_code == 0
        assert dir_with_spaces.exists()
        assert (dir_with_spaces / ".env").exists()

    def test_output_dir_relative_path(self, temp_deployment_dir, log_file, docker_templates_dir):
        """Test output directory with relative path."""
        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(temp_deployment_dir)
            responses = fixture_manager.load_input_fixture("basic_deployment")

            harness = CLITestHarness(
                responses=responses,
                args=[
                    "--output-dir",
                    "../relative/path",
                    "--template-from",
                    str(docker_templates_dir),
                ],
                log_file=str(log_file),
            )
            exit_code = harness.run()

            assert exit_code == 0
            relative_dir = temp_deployment_dir.parent / "relative" / "path"
            assert relative_dir.exists()
            assert (relative_dir / ".env").exists()

        finally:
            os.chdir(original_cwd)

    def test_output_dir_readonly_permission(self, temp_deployment_dir, log_file, docker_templates_dir):
        """Test error when output directory parent has no write permissions."""
        import os
        import stat

        readonly_parent = temp_deployment_dir / "readonly"
        readonly_parent.mkdir()

        # Make directory read-only
        os.chmod(readonly_parent, stat.S_IRUSR | stat.S_IXUSR)

        try:
            target_dir = readonly_parent / "cannot_create"
            responses = fixture_manager.load_input_fixture("basic_deployment")

            harness = CLITestHarness(
                responses=responses,
                args=[
                    "--output-dir",
                    str(target_dir),
                    "--template-from",
                    str(docker_templates_dir),
                ],
                log_file=str(log_file),
            )
            exit_code = harness.run()

            # Should fail with permission error
            assert exit_code != 0
            assert compare_output(log_file, temp_deployment_dir, "output_dir_permission_denied", fixture_manager)

        finally:
            # Restore permissions for cleanup
            os.chmod(readonly_parent, stat.S_IRWXU)


class TestTemplateSourceValidation:
    """Test template source validation - HIGH PRIORITY."""

    def test_template_from_nonexistent_path(self, temp_deployment_dir, log_file):
        """Test error when --template-from points to non-existent directory."""
        non_existent = temp_deployment_dir / "nonexistent-templates"
        responses = fixture_manager.load_input_fixture("basic_deployment")

        harness = CLITestHarness(
            responses=responses,
            args=[
                "--output-dir",
                str(temp_deployment_dir),
                "--template-from",
                str(non_existent),
            ],
            log_file=str(log_file),
        )
        exit_code = harness.run()

        assert exit_code != 0
        assert compare_output(log_file, temp_deployment_dir, "template_source_not_found", fixture_manager)

    def test_template_from_empty_directory(self, temp_deployment_dir, log_file):
        """Test error when --template-from points to empty directory."""
        empty_dir = temp_deployment_dir / "empty-templates"
        empty_dir.mkdir()

        responses = fixture_manager.load_input_fixture("basic_deployment")

        harness = CLITestHarness(
            responses=responses,
            args=[
                "--output-dir",
                str(temp_deployment_dir),
                "--template-from",
                str(empty_dir),
            ],
            log_file=str(log_file),
        )
        exit_code = harness.run()

        assert exit_code != 0
        assert compare_output(log_file, temp_deployment_dir, "template_source_empty", fixture_manager)

    def test_template_from_partial_templates(self, temp_deployment_dir, log_file):
        """Test error when template directory is missing required templates."""
        partial_dir = temp_deployment_dir / "partial-templates"
        partial_dir.mkdir()

        # Create only one template file (incomplete set)
        (partial_dir / "docker-compose.yml.j2").write_text("# Incomplete template set")

        responses = fixture_manager.load_input_fixture("basic_deployment")

        harness = CLITestHarness(
            responses=responses,
            args=[
                "--output-dir",
                str(temp_deployment_dir),
                "--template-from",
                str(partial_dir),
            ],
            log_file=str(log_file),
        )
        exit_code = harness.run()

        # Should fail listing missing templates
        assert exit_code != 0
        assert compare_output(log_file, temp_deployment_dir, "template_source_partial", fixture_manager)

    def test_template_from_local_path_verbose(self, temp_deployment_dir, log_file, docker_templates_dir):
        """Test --template-from with local path and --verbose shows copy progress."""
        responses = fixture_manager.load_input_fixture("basic_deployment")

        harness = CLITestHarness(
            responses=responses,
            args=[
                "--output-dir",
                str(temp_deployment_dir),
                "--template-from",
                str(docker_templates_dir),
                "--verbose",
            ],
            log_file=str(log_file),
        )
        exit_code = harness.run()

        assert exit_code == 0
        # Verify .avatar-templates directory was created
        templates_dir = temp_deployment_dir / ".avatar-templates"
        assert templates_dir.exists()
        assert compare_output(log_file, temp_deployment_dir, "template_from_local_verbose", fixture_manager)
