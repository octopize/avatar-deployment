#!/usr/bin/env python3
"""Integration tests for DeploymentConfigurator class."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from octopize_avatar_deploy.configure import DeploymentConfigurator


class TestDeploymentConfigurator:
    """Test the DeploymentConfigurator class."""

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
            (templates_dir / ".env.template").write_text(
                "# Environment Configuration\n"
                "API_URL={{ api_url }}\n"
                "DB_HOST={{ db_host }}\n"
            )
            (templates_dir / "nginx.conf.template").write_text(
                "server {\n    server_name {{ domain }};\n}\n"
            )
            yield templates_dir

    @pytest.fixture
    def defaults_file(self, temp_output_dir):
        """Create a mock defaults.yaml file."""
        defaults = {
            "version": "1.0.0",
            "images": {"api": "1.0.0", "web": "1.0.0"},
            "email": {"provider": "smtp"},
        }
        defaults_path = temp_output_dir / "defaults.yaml"
        with open(defaults_path, "w") as f:
            yaml.dump(defaults, f)
        return defaults_path

    def test_init_default_parameters(
        self, temp_templates_dir, temp_output_dir, defaults_file
    ):
        """Test initialization with default parameters."""
        configurator = DeploymentConfigurator(
            templates_dir=temp_templates_dir,
            output_dir=temp_output_dir,
            defaults_file=defaults_file,
        )

        assert configurator.templates_dir == temp_templates_dir
        assert configurator.output_dir == temp_output_dir
        assert configurator.config == {}
        assert configurator.use_state is True
        assert configurator.state is not None
        assert configurator.defaults is not None
        assert configurator.env is not None

    def test_init_with_config(self, temp_templates_dir, temp_output_dir, defaults_file):
        """Test initialization with pre-loaded configuration."""
        config = {"api_url": "https://api.example.com", "db_host": "localhost"}

        configurator = DeploymentConfigurator(
            templates_dir=temp_templates_dir,
            output_dir=temp_output_dir,
            defaults_file=defaults_file,
            config=config,
        )

        assert configurator.config == config

    def test_init_without_state(
        self, temp_templates_dir, temp_output_dir, defaults_file
    ):
        """Test initialization with state management disabled."""
        configurator = DeploymentConfigurator(
            templates_dir=temp_templates_dir,
            output_dir=temp_output_dir,
            defaults_file=defaults_file,
            use_state=False,
        )

        assert configurator.use_state is False
        assert configurator.state is None

    def test_init_creates_state_file(
        self, temp_templates_dir, temp_output_dir, defaults_file
    ):
        """Test that initialization creates state file when use_state is True."""
        configurator = DeploymentConfigurator(
            templates_dir=temp_templates_dir,
            output_dir=temp_output_dir,
            defaults_file=defaults_file,
            use_state=True,
        )

        # State file should be initialized (but may not exist on disk yet)
        assert configurator.state is not None

    def test_load_defaults_from_file(
        self, temp_templates_dir, temp_output_dir, defaults_file
    ):
        """Test loading defaults from provided defaults file."""
        configurator = DeploymentConfigurator(
            templates_dir=temp_templates_dir,
            output_dir=temp_output_dir,
            defaults_file=defaults_file,
        )

        assert configurator.defaults["version"] == "1.0.0"
        assert "images" in configurator.defaults
        assert configurator.defaults["images"]["api"] == "1.0.0"

    def test_load_defaults_from_script_directory(
        self, temp_templates_dir, temp_output_dir
    ):
        """Test loading defaults from script directory when no file provided."""
        configurator = DeploymentConfigurator(
            templates_dir=temp_templates_dir,
            output_dir=temp_output_dir,
        )

        # Should load from octopize_avatar_deploy/defaults.yaml
        assert "version" in configurator.defaults
        assert "images" in configurator.defaults

    def test_load_defaults_missing_file_raises_error(
        self, temp_templates_dir, temp_output_dir
    ):
        """Test that missing defaults file raises FileNotFoundError."""
        non_existent = temp_output_dir / "non-existent.yaml"

        with patch("pathlib.Path.exists", return_value=False):
            with pytest.raises(FileNotFoundError, match="defaults.yaml not found"):
                DeploymentConfigurator(
                    templates_dir=temp_templates_dir,
                    output_dir=temp_output_dir,
                    defaults_file=non_existent,
                )

    def test_render_template_basic(
        self, temp_templates_dir, temp_output_dir, defaults_file
    ):
        """Test rendering a basic template."""
        configurator = DeploymentConfigurator(
            templates_dir=temp_templates_dir,
            output_dir=temp_output_dir,
            defaults_file=defaults_file,
        )

        configurator.config = {
            "api_url": "https://api.example.com",
            "db_host": "db.example.com",
        }

        configurator.render_template(".env.template", ".env")

        env_file = temp_output_dir / ".env"
        assert env_file.exists()

        content = env_file.read_text()
        assert "API_URL=https://api.example.com" in content
        assert "DB_HOST=db.example.com" in content

    def test_render_template_creates_subdirectories(
        self, temp_templates_dir, temp_output_dir, defaults_file
    ):
        """Test that render_template creates parent directories."""
        configurator = DeploymentConfigurator(
            templates_dir=temp_templates_dir,
            output_dir=temp_output_dir,
            defaults_file=defaults_file,
        )

        configurator.config = {"domain": "example.com"}
        configurator.render_template("nginx.conf.template", "deep/nested/nginx.conf")

        nginx_file = temp_output_dir / "deep/nested/nginx.conf"
        assert nginx_file.exists()
        assert "server_name example.com" in nginx_file.read_text()

    def test_render_template_handles_errors(
        self, temp_templates_dir, temp_output_dir, defaults_file
    ):
        """Test that render_template raises exception on errors."""
        from jinja2 import TemplateNotFound

        configurator = DeploymentConfigurator(
            templates_dir=temp_templates_dir,
            output_dir=temp_output_dir,
            defaults_file=defaults_file,
        )

        with pytest.raises(TemplateNotFound):
            configurator.render_template("non-existent.template", "output.txt")

    def test_generate_configs(
        self, temp_templates_dir, temp_output_dir, defaults_file, capsys
    ):
        """Test generate_configs creates all expected files."""
        configurator = DeploymentConfigurator(
            templates_dir=temp_templates_dir,
            output_dir=temp_output_dir,
            defaults_file=defaults_file,
        )

        configurator.config = {
            "api_url": "https://api.example.com",
            "db_host": "localhost",
            "domain": "example.com",
        }

        configurator.generate_configs()

        # Check files were created
        assert (temp_output_dir / ".env").exists()
        assert (temp_output_dir / "nginx/nginx.conf").exists()

        # Check output message
        captured = capsys.readouterr()
        assert "Generating Configuration Files" in captured.out
        assert "✓ Configuration files generated successfully!" in captured.out

    def test_save_config_to_file(
        self, temp_templates_dir, temp_output_dir, defaults_file
    ):
        """Test saving configuration to YAML file."""
        configurator = DeploymentConfigurator(
            templates_dir=temp_templates_dir,
            output_dir=temp_output_dir,
            defaults_file=defaults_file,
        )

        configurator.config = {
            "api_url": "https://api.example.com",
            "db_host": "localhost",
            "db_port": 5432,
        }

        config_file = temp_output_dir / "test-config.yaml"
        configurator.save_config_to_file(config_file)

        assert config_file.exists()

        with open(config_file) as f:
            saved_config = yaml.safe_load(f)

        assert saved_config == configurator.config
        assert saved_config["api_url"] == "https://api.example.com"

    def test_write_secrets_creates_directory(
        self, temp_templates_dir, temp_output_dir, defaults_file
    ):
        """Test write_secrets creates .secrets directory."""
        configurator = DeploymentConfigurator(
            templates_dir=temp_templates_dir,
            output_dir=temp_output_dir,
            defaults_file=defaults_file,
        )

        secrets = {
            "db_password": "secret123",
            "api_key": "key456",
        }

        configurator.write_secrets(secrets)

        secrets_dir = temp_output_dir / ".secrets"
        assert secrets_dir.exists()
        assert secrets_dir.is_dir()

    def test_write_secrets_creates_files(
        self, temp_templates_dir, temp_output_dir, defaults_file
    ):
        """Test write_secrets creates individual secret files."""
        configurator = DeploymentConfigurator(
            templates_dir=temp_templates_dir,
            output_dir=temp_output_dir,
            defaults_file=defaults_file,
        )

        secrets = {
            "db_password": "secret123",
            "api_key": "key456",
        }

        configurator.write_secrets(secrets)

        db_pass_file = temp_output_dir / ".secrets/db_password"
        api_key_file = temp_output_dir / ".secrets/api_key"

        assert db_pass_file.exists()
        assert api_key_file.exists()
        assert db_pass_file.read_text() == "secret123"
        assert api_key_file.read_text() == "key456"

    @patch("octopize_avatar_deploy.configure.RequiredConfigStep")
    @patch("octopize_avatar_deploy.configure.EmailStep")
    @patch("octopize_avatar_deploy.configure.TelemetryStep")
    @patch("octopize_avatar_deploy.configure.DatabaseStep")
    @patch("octopize_avatar_deploy.configure.StorageStep")
    def test_run_executes_all_steps(
        self,
        mock_storage,
        mock_database,
        mock_telemetry,
        mock_email,
        mock_required,
        temp_templates_dir,
        temp_output_dir,
        defaults_file,
    ):
        """Test run method executes all deployment steps."""
        # Setup mocks
        for mock_step_class in [
            mock_required,
            mock_email,
            mock_telemetry,
            mock_database,
            mock_storage,
        ]:
            mock_step = MagicMock()
            mock_step.collect_config.return_value = {}
            mock_step.generate_secrets.return_value = {}
            mock_step.validate.return_value = True
            mock_step.description = "Test Step"
            mock_step.name = "test_step"
            mock_step_class.return_value = mock_step

        configurator = DeploymentConfigurator(
            templates_dir=temp_templates_dir,
            output_dir=temp_output_dir,
            defaults_file=defaults_file,
        )

        configurator.run(interactive=False)

        # Verify all steps were called
        mock_required.assert_called_once()
        mock_email.assert_called_once()
        mock_telemetry.assert_called_once()
        mock_database.assert_called_once()
        mock_storage.assert_called_once()

    @patch("octopize_avatar_deploy.configure.RequiredConfigStep")
    @patch("octopize_avatar_deploy.configure.EmailStep")
    @patch("octopize_avatar_deploy.configure.TelemetryStep")
    @patch("octopize_avatar_deploy.configure.DatabaseStep")
    @patch("octopize_avatar_deploy.configure.StorageStep")
    def test_run_loads_config_file(
        self,
        mock_storage,
        mock_database,
        mock_telemetry,
        mock_email,
        mock_required,
        temp_templates_dir,
        temp_output_dir,
        defaults_file,
    ):
        """Test run method loads configuration from file."""
        # Setup mocks
        for mock_step_class in [
            mock_required,
            mock_email,
            mock_telemetry,
            mock_database,
            mock_storage,
        ]:
            mock_step = MagicMock()
            mock_step.collect_config.return_value = {}
            mock_step.generate_secrets.return_value = {}
            mock_step.validate.return_value = True
            mock_step.description = "Test Step"
            mock_step.name = "test_step"
            mock_step_class.return_value = mock_step

        # Create config file
        config_file = temp_output_dir / "config.yaml"
        config_data = {"api_url": "https://api.example.com", "db_host": "localhost"}
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        configurator = DeploymentConfigurator(
            templates_dir=temp_templates_dir,
            output_dir=temp_output_dir,
            defaults_file=defaults_file,
        )

        configurator.run(interactive=False, config_file=config_file)

        # Config should be loaded
        assert configurator.config["api_url"] == "https://api.example.com"
        assert configurator.config["db_host"] == "localhost"

    @patch("octopize_avatar_deploy.configure.RequiredConfigStep")
    @patch("octopize_avatar_deploy.configure.EmailStep")
    @patch("octopize_avatar_deploy.configure.TelemetryStep")
    @patch("octopize_avatar_deploy.configure.DatabaseStep")
    @patch("octopize_avatar_deploy.configure.StorageStep")
    def test_run_saves_config_when_requested(
        self,
        mock_storage,
        mock_database,
        mock_telemetry,
        mock_email,
        mock_required,
        temp_templates_dir,
        temp_output_dir,
        defaults_file,
    ):
        """Test run method saves configuration when save_config=True."""
        # Setup mocks
        for mock_step_class in [
            mock_required,
            mock_email,
            mock_telemetry,
            mock_database,
            mock_storage,
        ]:
            mock_step = MagicMock()
            mock_step.collect_config.return_value = {"key": "value"}
            mock_step.generate_secrets.return_value = {}
            mock_step.validate.return_value = True
            mock_step.description = "Test Step"
            mock_step.name = "test_step"
            mock_step_class.return_value = mock_step

        configurator = DeploymentConfigurator(
            templates_dir=temp_templates_dir,
            output_dir=temp_output_dir,
            defaults_file=defaults_file,
        )

        configurator.run(interactive=False, save_config=True)

        # Config file should be created
        config_file = temp_output_dir / "deployment-config.yaml"
        assert config_file.exists()

    @patch("octopize_avatar_deploy.configure.RequiredConfigStep")
    @patch("octopize_avatar_deploy.configure.EmailStep")
    @patch("octopize_avatar_deploy.configure.TelemetryStep")
    @patch("octopize_avatar_deploy.configure.DatabaseStep")
    @patch("octopize_avatar_deploy.configure.StorageStep")
    def test_run_writes_secrets(
        self,
        mock_storage,
        mock_database,
        mock_telemetry,
        mock_email,
        mock_required,
        temp_templates_dir,
        temp_output_dir,
        defaults_file,
    ):
        """Test run method writes secrets from all steps."""
        # Setup mocks with secrets
        mock_required_instance = MagicMock()
        mock_required_instance.collect_config.return_value = {}
        mock_required_instance.generate_secrets.return_value = {"secret_key": "abc123"}
        mock_required_instance.validate.return_value = True
        mock_required_instance.description = "Required Config"
        mock_required_instance.name = "required"
        mock_required.return_value = mock_required_instance

        for mock_step_class in [
            mock_email,
            mock_telemetry,
            mock_database,
            mock_storage,
        ]:
            mock_step = MagicMock()
            mock_step.collect_config.return_value = {}
            mock_step.generate_secrets.return_value = {}
            mock_step.validate.return_value = True
            mock_step.description = "Test Step"
            mock_step.name = "test_step"
            mock_step_class.return_value = mock_step

        configurator = DeploymentConfigurator(
            templates_dir=temp_templates_dir,
            output_dir=temp_output_dir,
            defaults_file=defaults_file,
        )

        configurator.run(interactive=False)

        # Secret should be written
        secret_file = temp_output_dir / ".secrets/secret_key"
        assert secret_file.exists()
        assert secret_file.read_text() == "abc123"

    @patch("octopize_avatar_deploy.configure.RequiredConfigStep")
    @patch("octopize_avatar_deploy.configure.EmailStep")
    @patch("octopize_avatar_deploy.configure.TelemetryStep")
    @patch("octopize_avatar_deploy.configure.DatabaseStep")
    @patch("octopize_avatar_deploy.configure.StorageStep")
    def test_run_validation_failure_raises_error(
        self,
        mock_storage,
        mock_database,
        mock_telemetry,
        mock_email,
        mock_required,
        temp_templates_dir,
        temp_output_dir,
        defaults_file,
    ):
        """Test run method raises error when step validation fails."""
        # Setup mock with validation failure
        mock_required_instance = MagicMock()
        mock_required_instance.collect_config.return_value = {}
        mock_required_instance.generate_secrets.return_value = {}
        mock_required_instance.validate.return_value = False  # Validation fails
        mock_required_instance.description = "Required Config"
        mock_required_instance.name = "required_config"
        mock_required.return_value = mock_required_instance

        configurator = DeploymentConfigurator(
            templates_dir=temp_templates_dir,
            output_dir=temp_output_dir,
            defaults_file=defaults_file,
        )

        with pytest.raises(
            ValueError, match="Validation failed for step: required_config"
        ):
            configurator.run(interactive=False)

    @patch("octopize_avatar_deploy.configure.RequiredConfigStep")
    @patch("octopize_avatar_deploy.configure.EmailStep")
    @patch("octopize_avatar_deploy.configure.TelemetryStep")
    @patch("octopize_avatar_deploy.configure.DatabaseStep")
    @patch("octopize_avatar_deploy.configure.StorageStep")
    def test_run_passes_interactive_to_steps(
        self,
        mock_storage,
        mock_database,
        mock_telemetry,
        mock_email,
        mock_required,
        temp_templates_dir,
        temp_output_dir,
        defaults_file,
    ):
        """Test run method passes interactive parameter to steps."""
        # Setup mocks
        for mock_step_class in [
            mock_required,
            mock_email,
            mock_telemetry,
            mock_database,
            mock_storage,
        ]:
            mock_step = MagicMock()
            mock_step.collect_config.return_value = {}
            mock_step.generate_secrets.return_value = {}
            mock_step.validate.return_value = True
            mock_step.description = "Test Step"
            mock_step.name = "test_step"
            mock_step_class.return_value = mock_step

        configurator = DeploymentConfigurator(
            templates_dir=temp_templates_dir,
            output_dir=temp_output_dir,
            defaults_file=defaults_file,
        )

        configurator.run(interactive=True)

        # Verify steps were initialized with interactive=True
        mock_required.assert_called_once()
        args = mock_required.call_args[0]
        assert args[3] is True  # Fourth argument is interactive

    def test_jinja2_environment_configuration(
        self, temp_templates_dir, temp_output_dir, defaults_file
    ):
        """Test that Jinja2 environment is configured correctly."""
        configurator = DeploymentConfigurator(
            templates_dir=temp_templates_dir,
            output_dir=temp_output_dir,
            defaults_file=defaults_file,
        )

        assert configurator.env.variable_start_string == "{{"
        assert configurator.env.variable_end_string == "}}"
        assert configurator.env.trim_blocks is True
        assert configurator.env.lstrip_blocks is True

    @patch("octopize_avatar_deploy.configure.RequiredConfigStep")
    @patch("octopize_avatar_deploy.configure.EmailStep")
    @patch("octopize_avatar_deploy.configure.TelemetryStep")
    @patch("octopize_avatar_deploy.configure.DatabaseStep")
    @patch("octopize_avatar_deploy.configure.StorageStep")
    @patch("builtins.input")
    def test_run_resumes_from_interrupted_state(
        self,
        mock_input,
        mock_storage,
        mock_database,
        mock_telemetry,
        mock_email,
        mock_required,
        temp_templates_dir,
        temp_output_dir,
        defaults_file,
    ):
        """Test resume functionality after interruption in middle of steps."""
        # Setup mocks for all steps
        step_mocks = []
        for mock_step_class, name in [
            (mock_required, "required"),
            (mock_email, "email"),
            (mock_telemetry, "telemetry"),
            (mock_database, "database"),
            (mock_storage, "storage"),
        ]:
            mock_step = MagicMock()
            mock_step.collect_config.return_value = {f"{name}_key": f"{name}_value"}
            mock_step.generate_secrets.return_value = {}
            mock_step.validate.return_value = True
            mock_step.description = f"{name.title()} Step"
            mock_step.name = name
            mock_step_class.return_value = mock_step
            step_mocks.append((mock_step_class, mock_step, name))

        # FIRST RUN: Complete 2 steps, then simulate interruption
        configurator1 = DeploymentConfigurator(
            templates_dir=temp_templates_dir,
            output_dir=temp_output_dir,
            defaults_file=defaults_file,
            use_state=True,
        )

        # Manually simulate completing first 2 steps
        configurator1.state.mark_step_completed("step_0_required")
        configurator1.state.update_config({"required_key": "required_value"})
        configurator1.state.mark_step_completed("step_1_email")
        configurator1.state.update_config({"email_key": "email_value"})

        # Verify state shows partial completion
        assert configurator1.state.has_started()
        assert not configurator1.state.is_complete()
        assert configurator1.state.is_step_completed("step_0_required")
        assert configurator1.state.is_step_completed("step_1_email")
        assert not configurator1.state.is_step_completed("step_2_telemetry")

        # SECOND RUN: User chooses to resume
        mock_input.return_value = "y"  # User chooses to resume

        configurator2 = DeploymentConfigurator(
            templates_dir=temp_templates_dir,
            output_dir=temp_output_dir,
            defaults_file=defaults_file,
            use_state=True,
        )

        # Run should resume from step 2 (telemetry)
        configurator2.run(interactive=True)

        # Verify resume prompt was shown
        mock_input.assert_called_once()

        # Verify first 2 steps were skipped (collect_config not called again)
        step_mocks[0][1].collect_config.assert_not_called()  # required
        step_mocks[1][1].collect_config.assert_not_called()  # email

        # Verify remaining steps were executed
        step_mocks[2][1].collect_config.assert_called_once()  # telemetry
        step_mocks[3][1].collect_config.assert_called_once()  # database
        step_mocks[4][1].collect_config.assert_called_once()  # storage

        # Verify config from previous steps was loaded
        assert "required_key" in configurator2.config
        assert "email_key" in configurator2.config

    @patch("octopize_avatar_deploy.configure.RequiredConfigStep")
    @patch("octopize_avatar_deploy.configure.EmailStep")
    @patch("octopize_avatar_deploy.configure.TelemetryStep")
    @patch("octopize_avatar_deploy.configure.DatabaseStep")
    @patch("octopize_avatar_deploy.configure.StorageStep")
    @patch("builtins.input")
    def test_run_restarts_when_user_chooses_fresh_start(
        self,
        mock_input,
        mock_storage,
        mock_database,
        mock_telemetry,
        mock_email,
        mock_required,
        temp_templates_dir,
        temp_output_dir,
        defaults_file,
    ):
        """Test restart functionality when user chooses to start fresh."""
        # Setup mocks
        for mock_step_class in [
            mock_required,
            mock_email,
            mock_telemetry,
            mock_database,
            mock_storage,
        ]:
            mock_step = MagicMock()
            mock_step.collect_config.return_value = {}
            mock_step.generate_secrets.return_value = {}
            mock_step.validate.return_value = True
            mock_step.description = "Test Step"
            mock_step.name = "test_step"
            mock_step_class.return_value = mock_step

        # Create initial state with some completed steps
        configurator1 = DeploymentConfigurator(
            templates_dir=temp_templates_dir,
            output_dir=temp_output_dir,
            defaults_file=defaults_file,
            use_state=True,
        )
        configurator1.state.mark_step_completed("step_0_required")
        configurator1.state.update_config({"old_key": "old_value"})

        # User chooses to start fresh
        mock_input.return_value = "n"

        configurator2 = DeploymentConfigurator(
            templates_dir=temp_templates_dir,
            output_dir=temp_output_dir,
            defaults_file=defaults_file,
            use_state=True,
        )

        configurator2.run(interactive=True)

        # Verify all steps were executed (not skipped)
        mock_required.return_value.collect_config.assert_called_once()
        mock_email.return_value.collect_config.assert_called_once()
        mock_telemetry.return_value.collect_config.assert_called_once()
        mock_database.return_value.collect_config.assert_called_once()
        mock_storage.return_value.collect_config.assert_called_once()

    @patch("octopize_avatar_deploy.configure.RequiredConfigStep")
    @patch("octopize_avatar_deploy.configure.EmailStep")
    @patch("octopize_avatar_deploy.configure.TelemetryStep")
    @patch("octopize_avatar_deploy.configure.DatabaseStep")
    @patch("octopize_avatar_deploy.configure.StorageStep")
    def test_run_non_interactive_resumes_automatically(
        self,
        mock_storage,
        mock_database,
        mock_telemetry,
        mock_email,
        mock_required,
        temp_templates_dir,
        temp_output_dir,
        defaults_file,
    ):
        """Test non-interactive mode automatically resumes from state."""
        # Setup mocks
        step_mocks = []
        for mock_step_class, name in [
            (mock_required, "required"),
            (mock_email, "email"),
            (mock_telemetry, "telemetry"),
            (mock_database, "database"),
            (mock_storage, "storage"),
        ]:
            mock_step = MagicMock()
            mock_step.collect_config.return_value = {}
            mock_step.generate_secrets.return_value = {}
            mock_step.validate.return_value = True
            mock_step.description = f"{name.title()} Step"
            mock_step.name = name
            mock_step_class.return_value = mock_step
            step_mocks.append((mock_step_class, mock_step))

        # Create initial state
        configurator1 = DeploymentConfigurator(
            templates_dir=temp_templates_dir,
            output_dir=temp_output_dir,
            defaults_file=defaults_file,
            use_state=True,
        )
        configurator1.state.mark_step_completed("step_0_required")
        configurator1.state.mark_step_completed("step_1_email")
        configurator1.state.update_config({"saved_key": "saved_value"})

        # Run in non-interactive mode
        configurator2 = DeploymentConfigurator(
            templates_dir=temp_templates_dir,
            output_dir=temp_output_dir,
            defaults_file=defaults_file,
            use_state=True,
        )

        configurator2.run(interactive=False)

        # Verify first 2 steps were skipped
        step_mocks[0][1].collect_config.assert_not_called()  # required
        step_mocks[1][1].collect_config.assert_not_called()  # email

        # Verify remaining steps were executed
        step_mocks[2][1].collect_config.assert_called_once()  # telemetry
        step_mocks[3][1].collect_config.assert_called_once()  # database
        step_mocks[4][1].collect_config.assert_called_once()  # storage

        # Verify saved config was loaded
        assert "saved_key" in configurator2.config
        assert configurator2.config["saved_key"] == "saved_value"

    @patch("octopize_avatar_deploy.configure.RequiredConfigStep")
    @patch("octopize_avatar_deploy.configure.EmailStep")
    @patch("octopize_avatar_deploy.configure.TelemetryStep")
    @patch("octopize_avatar_deploy.configure.DatabaseStep")
    @patch("octopize_avatar_deploy.configure.StorageStep")
    @patch("builtins.input")
    def test_run_invalid_resume_choice_starts_fresh(
        self,
        mock_input,
        mock_storage,
        mock_database,
        mock_telemetry,
        mock_email,
        mock_required,
        temp_templates_dir,
        temp_output_dir,
        defaults_file,
    ):
        """Test invalid resume choice defaults to starting fresh."""
        # Setup mocks
        for mock_step_class in [
            mock_required,
            mock_email,
            mock_telemetry,
            mock_database,
            mock_storage,
        ]:
            mock_step = MagicMock()
            mock_step.collect_config.return_value = {}
            mock_step.generate_secrets.return_value = {}
            mock_step.validate.return_value = True
            mock_step.description = "Test Step"
            mock_step.name = "test_step"
            mock_step_class.return_value = mock_step

        # Create initial state
        configurator1 = DeploymentConfigurator(
            templates_dir=temp_templates_dir,
            output_dir=temp_output_dir,
            defaults_file=defaults_file,
            use_state=True,
        )
        configurator1.state.mark_step_completed("step_0_required")

        # User gives invalid input (not 'y' or 'n')
        mock_input.return_value = "maybe"

        configurator2 = DeploymentConfigurator(
            templates_dir=temp_templates_dir,
            output_dir=temp_output_dir,
            defaults_file=defaults_file,
            use_state=True,
        )

        configurator2.run(interactive=True)

        # Verify all steps were executed (started fresh)
        mock_required.return_value.collect_config.assert_called_once()
        mock_email.return_value.collect_config.assert_called_once()

    @patch("octopize_avatar_deploy.configure.RequiredConfigStep")
    @patch("octopize_avatar_deploy.configure.EmailStep")
    @patch("octopize_avatar_deploy.configure.TelemetryStep")
    @patch("octopize_avatar_deploy.configure.DatabaseStep")
    @patch("octopize_avatar_deploy.configure.StorageStep")
    def test_run_no_prompt_when_no_previous_state(
        self,
        mock_storage,
        mock_database,
        mock_telemetry,
        mock_email,
        mock_required,
        temp_templates_dir,
        temp_output_dir,
        defaults_file,
        capsys,
    ):
        """Test no resume prompt shown when no previous state exists."""
        # Setup mocks
        for mock_step_class in [
            mock_required,
            mock_email,
            mock_telemetry,
            mock_database,
            mock_storage,
        ]:
            mock_step = MagicMock()
            mock_step.collect_config.return_value = {}
            mock_step.generate_secrets.return_value = {}
            mock_step.validate.return_value = True
            mock_step.description = "Test Step"
            mock_step.name = "test_step"
            mock_step_class.return_value = mock_step

        # Fresh configurator with no previous state
        configurator = DeploymentConfigurator(
            templates_dir=temp_templates_dir,
            output_dir=temp_output_dir,
            defaults_file=defaults_file,
            use_state=True,
        )

        configurator.run(interactive=True)

        # Verify no resume prompt was shown
        captured = capsys.readouterr()
        assert "Resume from where you left off?" not in captured.out
