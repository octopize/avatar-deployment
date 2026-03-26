"""
Integration tests for CLI using CLITestHarness - simplified version.

These tests verify end-to-end CLI behavior with various argument combinations
focusing on successful execution rather than output comparison.
"""

# Import fixture utilities
import contextlib
import io
import os
import tempfile
import uuid
from pathlib import Path

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

ResponseMap = dict[str, str | bool]


def _create_cli_harness(
    *,
    responses: ResponseMap | None = None,
    args: list[str] | None = None,
    silent: bool = False,
    log_file: Path | str | None = None,
) -> CLITestHarness:
    """Create a CLI test harness with normalized defaults."""
    return CLITestHarness(
        responses=responses or {},
        args=args or [],
        silent=silent,
        log_file=log_file,
    )


def _build_deploy_args(
    output_dir: Path | str,
    template_from: Path | str,
    *extra_args: str,
) -> list[str]:
    """Build common deploy CLI arguments with optional extra flags."""
    return [
        "deploy",
        *extra_args,
        "--output-dir",
        str(output_dir),
        "--template-from",
        str(template_from),
    ]


def _create_deploy_harness(
    *,
    output_dir: Path | str,
    template_from: Path | str,
    responses: ResponseMap | None = None,
    log_file: Path | str | None = None,
    extra_args: list[str] | None = None,
    silent: bool = False,
) -> CLITestHarness:
    """Create a harness for the deploy subcommand."""
    return _create_cli_harness(
        responses=responses,
        args=_build_deploy_args(output_dir, template_from, *(extra_args or [])),
        silent=silent,
        log_file=log_file,
    )


def _run_cli_and_capture_output(
    args: list[str], *, capture_stderr: bool = False
) -> tuple[int, str]:
    """Run the CLI and capture stdout or stderr for help/usage assertions."""
    captured_output = io.StringIO()
    redirect_stream = contextlib.redirect_stderr if capture_stderr else contextlib.redirect_stdout

    with redirect_stream(captured_output):
        exit_code = _create_cli_harness(args=args, silent=True).run()

    return exit_code, captured_output.getvalue()


def _assert_cli_output_matches_fixture(
    fixture_name: str,
    *,
    args: list[str],
    expected_exit_code: int,
    capture_stderr: bool = False,
) -> None:
    """Run CLI output through fixture comparison."""
    exit_code, actual_output = _run_cli_and_capture_output(args, capture_stderr=capture_stderr)

    assert exit_code == expected_exit_code

    expected_output = fixture_manager.load_expected_output(fixture_name)
    assert fixture_manager.compare_output(actual_output, expected_output, fixture_name=fixture_name)


class TestCLIBasicCommands:
    """Test basic CLI commands and arguments."""

    @pytest.mark.parametrize(
        ("fixture_name", "args"),
        [
            ("help", ["--help"]),
            ("deploy_help", ["deploy", "--help"]),
            ("generate_env_help", ["generate-env", "--help"]),
        ],
    )
    def test_help_output(self, fixture_name: str, args: list[str]) -> None:
        """Each CLI command should expose a stable help message."""
        _assert_cli_output_matches_fixture(
            fixture_name,
            args=args,
            expected_exit_code=0,
        )

    def test_missing_subcommand_shows_usage_error(self) -> None:
        """The top-level CLI should require an explicit subcommand."""
        _assert_cli_output_matches_fixture(
            "missing_subcommand",
            args=[],
            expected_exit_code=2,
            capture_stderr=True,
        )

    def test_generate_env_rejects_output_dir(self) -> None:
        """generate-env should no longer accept deploy's --output-dir flag."""
        _assert_cli_output_matches_fixture(
            "generate_env_output_dir_error",
            args=["generate-env", "--output-dir", "./out"],
            expected_exit_code=2,
            capture_stderr=True,
        )


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

        harness = _create_deploy_harness(
            responses=responses,
            output_dir=temp_deployment_dir,
            template_from=docker_templates_dir,
            log_file=log_file,
        )
        exit_code = harness.run()

        assert exit_code == 0
        assert compare_output(log_file, temp_deployment_dir, scenario, fixture_manager)

        # Verify generated configuration files
        assert compare_generated_files(temp_deployment_dir, scenario, FIXTURES_DIR)

    def test_dev_mode_deployment(self, temp_deployment_dir, log_file, docker_templates_dir):
        """Test dev mode deployment with local source bind mounts."""
        # Create temporary directories for local source paths
        web_source_dir = temp_deployment_dir / "test-avatar-website"
        web_source_dir.mkdir()
        (web_source_dir / "package.json").write_text('{"name": "test"}')

        npmrc_file = temp_deployment_dir / "test-.npmrc"
        npmrc_file.write_text("//registry.npmjs.org/:_authToken=test")

        # Create monorepo structure for API
        api_repo = temp_deployment_dir / "test-avatar-repo"
        api_repo.mkdir()

        api_dir = api_repo / "services" / "api"
        api_dir.mkdir(parents=True)
        (api_dir / "main.py").write_text("# API main\n")

        # Create additional contexts
        (api_repo / "avatar").mkdir()
        (api_repo / "core").mkdir()
        (api_repo / "dp").mkdir()

        # Load fixture and replace placeholders with temp paths
        responses = fixture_manager.load_input_fixture("dev_mode_deployment")
        responses["local_source.web_source_path"] = str(web_source_dir)
        responses["local_source.npmrc_path"] = str(npmrc_file)
        responses["local_source.api_source_path"] = str(api_dir)

        harness = _create_deploy_harness(
            responses=responses,
            output_dir=temp_deployment_dir,
            template_from=docker_templates_dir,
            log_file=log_file,
            extra_args=["--mode", "dev"],
        )
        exit_code = harness.run()

        assert exit_code == 0

        # Verify output and generated files (like other deployment tests)
        assert compare_output(
            log_file, temp_deployment_dir, "dev_mode_deployment", fixture_manager
        )
        assert compare_generated_files(temp_deployment_dir, "dev_mode_deployment", FIXTURES_DIR)

        # Verify compose.override.yaml was generated
        override_file = temp_deployment_dir / "compose.override.yaml"
        assert override_file.exists(), "compose.override.yaml should be generated in dev mode"

        # Verify override file contains bind mount paths
        override_content = override_file.read_text()
        assert str(web_source_dir) in override_content, "Web source path should be in override"
        assert str(npmrc_file) in override_content, "NPM RC path should be in override"
        assert str(api_dir) in override_content, "API source path should be in override"

        # Verify standard files still generated
        assert (temp_deployment_dir / "docker-compose.yml").exists()
        assert (temp_deployment_dir / ".env").exists()

        # Verify override file has expected structure for web
        assert "services:" in override_content
        assert "web:" in override_content
        assert "build:" in override_content
        assert "volumes:" in override_content
        assert "secrets:" in override_content

        # Verify override file has expected structure for API
        assert "api:" in override_content
        assert "additional_contexts:" in override_content
        assert "init-db:" in override_content
        assert "dask-scheduler:" in override_content
        assert "dask-worker:" in override_content

    def test_blueprint_template_rendering(
        self, temp_deployment_dir, log_file, docker_templates_dir
    ):
        """Test that the Authentik blueprint is properly copied with !Env tags intact."""
        responses = fixture_manager.load_input_fixture("basic_deployment")

        harness = _create_deploy_harness(
            responses=responses,
            output_dir=temp_deployment_dir,
            template_from=docker_templates_dir,
            log_file=log_file,
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
        assert (
            "!Env" in blueprint_content
            and "AVATAR_AUTHENTIK_BLUEPRINT_DOMAIN" in blueprint_content
        )
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
        harness = _create_deploy_harness(
            output_dir=temp_deployment_dir,
            template_from=non_existent,
            log_file=log_file,
        )
        exit_code = harness.run()
        assert exit_code != 0
        assert compare_output(log_file, temp_deployment_dir, "missing_templates", fixture_manager)


class TestCLINonInteractiveMode:
    """Test non-interactive mode."""

    def test_non_interactive_with_config(
        self, temp_deployment_dir, log_file, docker_templates_dir
    ):
        """Test non-interactive mode with config file."""
        config_file = fixture_manager.get_config_fixture_path("non_interactive_incomplete_config")

        harness = _create_deploy_harness(
            output_dir=temp_deployment_dir,
            template_from=docker_templates_dir,
            log_file=log_file,
            extra_args=["--config", str(config_file), "--non-interactive"],
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

        harness = _create_deploy_harness(
            output_dir=temp_deployment_dir,
            template_from=docker_templates_dir,
            log_file=log_file,
            extra_args=["--config", str(non_existent_config)],
        )
        exit_code = harness.run()

        assert exit_code != 0
        assert compare_output(log_file, temp_deployment_dir, "config_not_found", fixture_manager)

    def test_malformed_yaml_config(self, temp_deployment_dir, log_file, docker_templates_dir):
        """Test error when config file has invalid YAML syntax."""
        # Can't use load_config_from_fixture since it would fail parsing
        malformed_config = temp_deployment_dir / "malformed.yaml"
        malformed_config.write_text("base_url: invalid\n\ttabs_not_allowed: true\n  - broken list")

        harness = _create_deploy_harness(
            output_dir=temp_deployment_dir,
            template_from=docker_templates_dir,
            log_file=log_file,
            extra_args=["--config", str(malformed_config)],
        )
        exit_code = harness.run()

        assert exit_code != 0
        assert compare_output(log_file, temp_deployment_dir, "malformed_yaml", fixture_manager)

    @pytest.mark.parametrize(
        ("config_fixture", "expected_exit_code"),
        [
            ("invalid_url_config", 1),
            ("invalid_port_config", 0),
            ("type_mismatch_config", 0),
        ],
    )
    def test_invalid_config_handling(
        self,
        config_fixture,
        expected_exit_code,
        temp_deployment_dir,
        log_file,
        docker_templates_dir,
    ):
        """Test behavior when config contains invalid values.

        This tests various config validation scenarios:
        - invalid_url_config: Invalid PUBLIC_URL format (rejected)
        - invalid_port_config: Port as string instead of int (currently accepted)
        - type_mismatch_config: Type mismatches in config values (currently accepted)

        These tests document the current validation contract for config-file inputs.
        """
        config_file = fixture_manager.get_config_fixture_path(config_fixture)

        harness = _create_deploy_harness(
            output_dir=temp_deployment_dir,
            template_from=docker_templates_dir,
            log_file=log_file,
            extra_args=["--config", str(config_file), "--non-interactive"],
        )
        exit_code = harness.run()

        assert exit_code == expected_exit_code

        # Document current behavior in fixture
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
            "deploy",
            "--non-interactive",
            "--output-dir",
            str(temp_deployment_dir),
            "--template-from",
            str(docker_templates_dir),
        ]

        if config_fixture:
            config_file = fixture_manager.get_config_fixture_path(config_fixture)
            args.extend(["--config", str(config_file)])

        harness = _create_cli_harness(args=args, log_file=log_file)
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

        harness = _create_deploy_harness(
            responses=responses,
            output_dir=temp_deployment_dir,
            template_from=docker_templates_dir,
            log_file=log_file,
            extra_args=["--save-config"],
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

        harness = _create_deploy_harness(
            responses=responses,
            output_dir=temp_deployment_dir,
            template_from=docker_templates_dir,
            log_file=log_file,
            extra_args=["--config", str(existing_config), "--save-config"],
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

        harness1 = _create_deploy_harness(
            responses=responses,
            output_dir=first_dir,
            template_from=docker_templates_dir,
            log_file=first_log,
            extra_args=["--save-config"],
        )
        exit_code1 = harness1.run()
        assert exit_code1 == 0

        saved_config = first_dir / "deployment-config.yaml"
        assert saved_config.exists()

        # Second run: non-interactive mode using saved config
        second_dir = temp_deployment_dir / "second"
        second_dir.mkdir()
        second_log = second_dir / "output.log"

        harness2 = _create_deploy_harness(
            output_dir=second_dir,
            template_from=docker_templates_dir,
            log_file=second_log,
            extra_args=["--config", str(saved_config), "--non-interactive"],
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

                harness = _create_deploy_harness(
                    responses=responses,
                    output_dir=".",
                    template_from=docker_templates_dir,
                    log_file=log_file,
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

        harness = _create_deploy_harness(
            responses=responses,
            output_dir=nested_dir,
            template_from=docker_templates_dir,
            log_file=log_file,
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

        harness = _create_deploy_harness(
            responses=responses,
            output_dir=dir_with_spaces,
            template_from=docker_templates_dir,
            log_file=log_file,
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

            harness = _create_deploy_harness(
                responses=responses,
                output_dir=f"../{unique_dir}/path",
                template_from=docker_templates_dir,
                log_file=log_file,
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

            harness = _create_deploy_harness(
                responses=responses,
                output_dir=target_dir,
                template_from=docker_templates_dir,
                log_file=log_file,
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

        harness = _create_deploy_harness(
            responses=responses,
            output_dir=temp_deployment_dir,
            template_from=non_existent,
            log_file=log_file,
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

        harness = _create_deploy_harness(
            responses=responses,
            output_dir=temp_deployment_dir,
            template_from=empty_dir,
            log_file=log_file,
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

        harness = _create_deploy_harness(
            responses=responses,
            output_dir=temp_deployment_dir,
            template_from=partial_dir,
            log_file=log_file,
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

        harness = _create_deploy_harness(
            responses=responses,
            output_dir=temp_deployment_dir,
            template_from=docker_templates_dir,
            log_file=log_file,
            extra_args=["--verbose"],
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
        harness1 = _create_deploy_harness(
            responses=first_run_responses,
            output_dir=temp_deployment_dir,
            template_from=docker_templates_dir,
            log_file=first_run_log,
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
        harness2 = _create_deploy_harness(
            responses=resume_responses,
            output_dir=temp_deployment_dir,
            template_from=docker_templates_dir,
            log_file=resume_log,
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
