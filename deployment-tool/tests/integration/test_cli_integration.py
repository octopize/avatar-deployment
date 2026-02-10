"""
Integration tests for CLI using CLITestHarness - simplified version.

These tests verify end-to-end CLI behavior with various argument combinations
focusing on successful execution rather than output comparison.
"""

# Import fixture utilities
import io
import os
import sys
import tempfile
from pathlib import Path
import uuid
import re

import pytest
import yaml

from octopize_avatar_deploy.cli_test_harness import CLITestHarness
from tests.conftest import (
    compare_generated_files,
    compare_output,
)
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
    def test_deployment_scenarios(
        self, scenario, temp_deployment_dir, log_file, docker_templates_dir
    ):
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

    def test_blueprint_template_rendering(
        self, temp_deployment_dir, log_file, docker_templates_dir
    ):
        """Test that the Authentik blueprint is properly copied with !Env tags intact."""
        responses = fixture_manager.load_input_fixture("basic_deployment")

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

        # Verify blueprint file was generated
        blueprint_file = temp_deployment_dir / "authentik" / "octopize-avatar-blueprint.yaml"
        assert blueprint_file.exists(), "Blueprint should be copied to output directory"

        # Read the blueprint
        blueprint_content = blueprint_file.read_text()

        # Verify !Env tags are present (not rendered away by Jinja2)
        # Note: Tags may be with or without quotes (both are valid YAML)
        assert "!Env" in blueprint_content and "AVATAR_AUTHENTIK_BLUEPRINT_DOMAIN" in blueprint_content
        assert "AVATAR_AUTHENTIK_BLUEPRINT_CLIENT_ID" in blueprint_content
        assert "AVATAR_AUTHENTIK_BLUEPRINT_CLIENT_SECRET" in blueprint_content
        assert "AVATAR_AUTHENTIK_BLUEPRINT_API_REDIRECT_URI" in blueprint_content

        # Verify the license setup references the blueprint env variable
        assert "AVATAR_AUTHENTIK_BLUEPRINT_SELF_SERVICE_LICENSE" in blueprint_content
        assert "group.attributes" in blueprint_content and "license" in blueprint_content

        # Verify no Jinja2 placeholders remain
        assert "{{ BLUEPRINT_" not in blueprint_content


class TestCLIErrorHandling:
    """Test CLI error handling."""

    def test_missing_templates_directory(self, temp_deployment_dir, log_file):
        """Test behavior when template source directory doesn't exist."""
        non_existent = temp_deployment_dir / "non-existent-templates"
        harness = CLITestHarness(
            responses=[],
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
        assert compare_output(log_file, temp_deployment_dir, "missing_templates", fixture_manager)


class TestCLINonInteractiveMode:
    """Test non-interactive mode."""

    def test_non_interactive_with_config(self, temp_deployment_dir, log_file, docker_templates_dir):
        """Test non-interactive mode with config file."""
        config_file = fixture_manager.get_config_fixture_path("non_interactive_incomplete_config")

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
        assert exit_code == 0
        assert compare_output(
            log_file,
            temp_deployment_dir,
            "non_interactive_incomplete_config",
            fixture_manager,
        )

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
        # Can't use load_config_from_fixture since it would fail parsing
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

    @pytest.mark.parametrize(
        "config_fixture",
        [
            "invalid_url_config",
            "invalid_port_config",
            "type_mismatch_config",
        ],
    )
    def test_invalid_config_handling(
        self, config_fixture, temp_deployment_dir, log_file, docker_templates_dir
    ):
        """Test behavior when config contains invalid values.

        This tests various config validation scenarios:
        - invalid_url_config: Invalid URL format (currently accepted)
        - invalid_port_config: Port as string instead of int (currently accepted)
        - type_mismatch_config: Type mismatches in config values (currently accepted)

        Note: The tool currently does not validate these inputs, so they succeed.
        These tests document current behavior - validation may be added in the future.
        """
        config_file = fixture_manager.get_config_fixture_path(config_fixture)

        harness = CLITestHarness(
            responses=[],
            args=[
                "--config",
                str(config_file),
                "--non-interactive",
                "--output-dir",
                str(temp_deployment_dir),
                "--template-from",
                str(docker_templates_dir),
            ],
            log_file=str(log_file),
        )
        exit_code = harness.run()

        # Currently these all succeed - no validation implemented yet
        assert exit_code == 0

        # Document actual behavior in fixture
        assert compare_output(log_file, temp_deployment_dir, config_fixture, fixture_manager)


class TestNonInteractiveModeCompleteness:
    """Test non-interactive mode behavior - HIGH PRIORITY."""

    @pytest.mark.parametrize(
        "scenario,config_fixture,expected_exit_code,check_files",
        [
            ("non_interactive_complete", "non_interactive_complete", 0, True),
            ("non_interactive_no_config", None, None, False),
            (
                "non_interactive_partial_config",
                "non_interactive_partial_config",
                None,
                False,
            ),
        ],
    )
    def test_non_interactive_modes(
        self,
        scenario,
        config_fixture,
        expected_exit_code,
        check_files,
        temp_deployment_dir,
        log_file,
        docker_templates_dir,
    ):
        """Test non-interactive mode with different config completeness levels.

        Scenarios:
        - non_interactive_complete: Complete config, should succeed without prompts
        - non_interactive_no_config: No config file, should use defaults or fail
        - non_interactive_partial_config: Partial config, should use defaults for missing
          values or fail
        """
        args = [
            "--non-interactive",
            "--output-dir",
            str(temp_deployment_dir),
            "--template-from",
            str(docker_templates_dir),
        ]

        if config_fixture:
            config_file = fixture_manager.get_config_fixture_path(config_fixture)
            args.extend(["--config", str(config_file)])

        harness = CLITestHarness(
            responses=[],
            args=args,
            log_file=str(log_file),
        )
        exit_code = harness.run()

        if expected_exit_code is not None:
            assert exit_code == expected_exit_code

        assert compare_output(log_file, temp_deployment_dir, scenario, fixture_manager)

        if check_files:
            assert compare_generated_files(temp_deployment_dir, scenario, FIXTURES_DIR)

    def test_save_config_in_interactive_mode(
        self, temp_deployment_dir, log_file, docker_templates_dir
    ):
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

        assert compare_output(
            log_file, temp_deployment_dir, "save_config_interactive", fixture_manager
        )

    def test_save_config_with_existing_config(
        self, temp_deployment_dir, log_file, docker_templates_dir
    ):
        """Test --save-config with --config loads existing, allows modification, then saves."""
        existing_config = fixture_manager.get_config_fixture_path("save_config_with_existing")
        responses = fixture_manager.load_input_fixture("save_config_with_existing")

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

        assert compare_output(
            log_file, temp_deployment_dir, "save_config_with_existing", fixture_manager
        )

    def test_config_round_trip_validation(
        self, temp_deployment_dir, log_file, docker_templates_dir
    ):
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

    def test_output_dir_is_current_directory(self, docker_templates_dir):
        """Test --output-dir . (current directory)."""

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

    def test_output_dir_deeply_nested_nonexistent(
        self, temp_deployment_dir, log_file, docker_templates_dir
    ):
        """Test creating deeply nested output directory that doesn't exist."""
        nested_dir = (
            temp_deployment_dir / "deeply" / "nested" / "path" / "that" / "doesnt" / "exist"
        )
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

        original_cwd = os.getcwd()
        try:
            os.chdir(temp_deployment_dir)
            responses = fixture_manager.load_input_fixture("basic_deployment")

            # Use a unique directory name to avoid conflicts between test runs
            unique_dir = f"relative-{uuid.uuid4().hex[:8]}"

            harness = CLITestHarness(
                responses=responses,
                args=[
                    "--output-dir",
                    f"../{unique_dir}/path",
                    "--template-from",
                    str(docker_templates_dir),
                ],
                log_file=str(log_file),
            )
            exit_code = harness.run()

            assert exit_code == 0
            relative_dir = temp_deployment_dir.parent / unique_dir / "path"
            assert relative_dir.exists()
            assert (relative_dir / ".env").exists()

        finally:
            os.chdir(original_cwd)

    def test_output_dir_readonly_permission(
        self, temp_deployment_dir, log_file, docker_templates_dir
    ):
        """Test error when output directory parent has no write permissions."""
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
            assert compare_output(
                log_file,
                temp_deployment_dir,
                "output_dir_permission_denied",
                fixture_manager,
            )

        finally:
            # Restore permissions for cleanup
            os.chmod(readonly_parent, stat.S_IRWXU)

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
        assert compare_output(
            log_file, temp_deployment_dir, "template_source_not_found", fixture_manager
        )

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
        assert compare_output(
            log_file, temp_deployment_dir, "template_source_empty", fixture_manager
        )

    def test_template_from_partial_templates(self, temp_deployment_dir, log_file):
        """Test error when template directory is missing required templates."""
        partial_dir = temp_deployment_dir / "partial-templates"
        partial_dir.mkdir()

        # Create only one template file (incomplete set)
        (partial_dir / "docker-compose.yml.template").write_text("# Incomplete template set")

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
        assert compare_output(
            log_file, temp_deployment_dir, "template_source_partial", fixture_manager
        )

    def test_template_from_local_path_verbose(
        self, temp_deployment_dir, log_file, docker_templates_dir
    ):
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
        assert compare_output(
            log_file,
            temp_deployment_dir,
            "template_from_local_verbose",
            fixture_manager,
        )


class TestCLIResumeWorkflow:
    """Test resuming interrupted configurations."""

    def test_resume_from_interrupted_configuration(
        self, temp_deployment_dir, log_file, docker_templates_dir
    ):
        """Test resuming configuration after partial completion."""

        # First run - simulate interruption by providing incomplete responses
        # This will complete only the first few steps before running out of responses
        first_run_path = FIXTURES_DIR / "resume_interrupted" / "input_first_run.yaml"
        with open(first_run_path) as f:
            first_run_responses = yaml.safe_load(f)["responses"]

        # We expect the first run to fail/exit because we don't have enough responses
        # But it should save state for completed steps
        first_run_log = temp_deployment_dir / "output_first_run.log"
        harness1 = CLITestHarness(
            responses=first_run_responses,
            args=[
                "--output-dir",
                str(temp_deployment_dir),
                "--template-from",
                str(docker_templates_dir),
            ],
            log_file=str(first_run_log),
        )
        exit_code1 = harness1.run()

        # First run should fail due to incomplete responses
        assert exit_code1 != 0, "First run should fail with incomplete responses"

        # Verify first run output shows partial completion
        first_output = first_run_log.read_text()
        assert "Avatar Deployment Configuration" in first_output
        assert "Executing configuration steps..." in first_output

        # Compare first run output (partial completion with error)
        assert compare_output(
            first_run_log,
            temp_deployment_dir,
            "resume_interrupted/first_run",
            fixture_manager,
        )

        # State should be saved for completed steps
        state_file = temp_deployment_dir / ".deployment-state.yaml"
        assert state_file.exists(), "State file should be created after partial run"

        # Second run - resume with answer "yes" to resume prompt
        resume_path = FIXTURES_DIR / "resume_interrupted" / "input_resume.yaml"
        with open(resume_path) as f:
            resume_responses = yaml.safe_load(f)["responses"]

        # Use separate log file for resume run
        resume_log = temp_deployment_dir / "output_resume.log"
        harness2 = CLITestHarness(
            responses=resume_responses,
            args=[
                "--output-dir",
                str(temp_deployment_dir),
                "--template-from",
                str(docker_templates_dir),
            ],
            log_file=str(resume_log),
        )
        exit_code2 = harness2.run()

        # Second run should succeed
        assert exit_code2 == 0, "Resume run should complete successfully"

        # Verify the resume output contains expected messages
        resume_output = resume_log.read_text()

        # Should show deployment status screen
        assert "Deployment Configuration Status" in resume_output
        assert "steps completed" in resume_output

        # Should show resume message (this is logged via printer)
        assert "Resuming from last completed step..." in resume_output

        # Should show SKIPPED markers for already-completed steps
        assert "[SKIPPED - already completed]" in resume_output

        # Verify multiple steps were skipped
        skipped_count = resume_output.count("[SKIPPED - already completed]")
        assert skipped_count >= 5, "Should have skipped at least 5 completed steps"

        # Compare resume run output
        assert compare_output(
            resume_log, temp_deployment_dir, "resume_interrupted/resume", fixture_manager
        )
