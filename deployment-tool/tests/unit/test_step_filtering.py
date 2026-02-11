"""Tests for deployment mode step filtering."""

import pytest

from octopize_avatar_deploy.configure import DeploymentConfigurator
from octopize_avatar_deploy.deployment_mode import DeploymentMode
from octopize_avatar_deploy.steps import (
    AuthentikStep,
    DatabaseStep,
    DeploymentStep,
    EmailStep,
    LocalSourceStep,
    RequiredConfigStep,
    TelemetryStep,
)


class MockStep(DeploymentStep):
    """Mock step for testing."""

    name = "mock_step"
    description = "Mock step for testing"
    required = True

    def collect_config(self):
        return {}

    def generate_secrets(self):
        return {}


class MockDevOnlyStep(DeploymentStep):
    """Mock step that only runs in dev mode."""

    name = "mock_dev_only"
    description = "Dev-only mock step"
    required = True
    modes = [DeploymentMode.DEV]

    def collect_config(self):
        return {}

    def generate_secrets(self):
        return {}


class MockProductionOnlyStep(DeploymentStep):
    """Mock step that only runs in production mode."""

    name = "mock_production_only"
    description = "Production-only mock step"
    required = True
    modes = [DeploymentMode.PRODUCTION]

    def collect_config(self):
        return {}

    def generate_secrets(self):
        return {}


class TestStepFiltering:
    """Test that DeploymentConfigurator filters steps based on deployment mode."""

    @pytest.fixture
    def tmp_templates_dir(self, tmp_path):
        """Create a temporary templates directory with required files."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()

        # Create minimal required templates
        (templates_dir / ".env.template").write_text("# Test template\n")
        (templates_dir / "docker-compose.yml.template").write_text("services:\n")
        (templates_dir / "nginx.conf.template").write_text("# nginx config\n")

        # Create authentik subdirectory with required files
        authentik_dir = templates_dir / "authentik"
        authentik_dir.mkdir()
        (authentik_dir / "octopize-avatar-blueprint.yaml").write_text("# blueprint\n")

        return templates_dir

    @pytest.fixture
    def mock_defaults(self, tmp_path):
        """Create mock defaults file."""
        defaults_file = tmp_path / "defaults.yaml"
        defaults_file.write_text("""
application:
  db_name: test
email:
  provider: smtp
telemetry:
  enabled: false
""")
        return defaults_file

    def test_production_mode_filters_out_dev_steps(
        self, tmp_path, tmp_templates_dir, mock_defaults
    ):
        """Test that production mode excludes dev-only steps."""
        step_classes = [
            MockStep,
            MockDevOnlyStep,
            MockProductionOnlyStep,
        ]

        configurator = DeploymentConfigurator(
            templates_dir=tmp_templates_dir,
            output_dir=tmp_path / "output",
            defaults_file=mock_defaults,
            step_classes=step_classes,
            mode=DeploymentMode.PRODUCTION,
            use_state=False,
        )

        # Check that filtering happened correctly
        assert len(configurator.step_classes) == 2
        assert MockStep in configurator.step_classes
        assert MockProductionOnlyStep in configurator.step_classes
        assert MockDevOnlyStep not in configurator.step_classes

    def test_dev_mode_filters_out_production_steps(
        self, tmp_path, tmp_templates_dir, mock_defaults
    ):
        """Test that dev mode excludes production-only steps."""
        step_classes = [
            MockStep,
            MockDevOnlyStep,
            MockProductionOnlyStep,
        ]

        configurator = DeploymentConfigurator(
            templates_dir=tmp_templates_dir,
            output_dir=tmp_path / "output",
            defaults_file=mock_defaults,
            step_classes=step_classes,
            mode=DeploymentMode.DEV,
            use_state=False,
        )

        # Check that filtering happened correctly
        assert len(configurator.step_classes) == 2
        assert MockStep in configurator.step_classes
        assert MockDevOnlyStep in configurator.step_classes
        assert MockProductionOnlyStep not in configurator.step_classes

    def test_local_source_step_only_in_dev_mode(self, tmp_path, tmp_templates_dir, mock_defaults):
        """Test that LocalSourceStep is filtered out in production mode."""
        # Test with actual default steps including LocalSourceStep
        from octopize_avatar_deploy.configure import DeploymentConfigurator

        configurator_prod = DeploymentConfigurator(
            templates_dir=tmp_templates_dir,
            output_dir=tmp_path / "output_prod",
            defaults_file=mock_defaults,
            mode=DeploymentMode.PRODUCTION,
            use_state=False,
        )

        configurator_dev = DeploymentConfigurator(
            templates_dir=tmp_templates_dir,
            output_dir=tmp_path / "output_dev",
            defaults_file=mock_defaults,
            mode=DeploymentMode.DEV,
            use_state=False,
        )

        # LocalSourceStep should not be in production steps
        assert LocalSourceStep not in configurator_prod.step_classes

        # LocalSourceStep should be in dev steps
        assert LocalSourceStep in configurator_dev.step_classes

    def test_all_default_steps_run_in_both_modes_except_local_source(
        self, tmp_path, tmp_templates_dir, mock_defaults
    ):
        """Test that all default steps (except LocalSourceStep) run in both modes."""
        from octopize_avatar_deploy.configure import DeploymentConfigurator

        configurator_prod = DeploymentConfigurator(
            templates_dir=tmp_templates_dir,
            output_dir=tmp_path / "output_prod",
            defaults_file=mock_defaults,
            mode=DeploymentMode.PRODUCTION,
            use_state=False,
        )

        configurator_dev = DeploymentConfigurator(
            templates_dir=tmp_templates_dir,
            output_dir=tmp_path / "output_dev",
            defaults_file=mock_defaults,
            mode=DeploymentMode.DEV,
            use_state=False,
        )

        # Get step classes that are common to both modes
        common_steps = set(configurator_prod.step_classes) & set(configurator_dev.step_classes)

        # All these steps should run in both modes
        expected_common = {
            RequiredConfigStep,
            DatabaseStep,
            AuthentikStep,
            EmailStep,
            TelemetryStep,
        }

        # At least these should be in common (there may be more)
        assert expected_common.issubset(common_steps)

        # LocalSourceStep should only be in dev
        dev_only_steps = set(configurator_dev.step_classes) - set(configurator_prod.step_classes)
        assert LocalSourceStep in dev_only_steps

    def test_deployment_mode_added_to_config(self, tmp_path, tmp_templates_dir, mock_defaults):
        """Test that deployment_mode is added to config early."""
        configurator = DeploymentConfigurator(
            templates_dir=tmp_templates_dir,
            output_dir=tmp_path / "output",
            defaults_file=mock_defaults,
            mode=DeploymentMode.DEV,
            use_state=False,
        )

        # deployment_mode should be in config
        assert "deployment_mode" in configurator.config
        assert configurator.config["deployment_mode"] == "dev"

    def test_mode_attribute_set_correctly(self, tmp_path, tmp_templates_dir, mock_defaults):
        """Test that mode attribute is set on configurator."""
        configurator_prod = DeploymentConfigurator(
            templates_dir=tmp_templates_dir,
            output_dir=tmp_path / "output",
            defaults_file=mock_defaults,
            mode=DeploymentMode.PRODUCTION,
            use_state=False,
        )

        configurator_dev = DeploymentConfigurator(
            templates_dir=tmp_templates_dir,
            output_dir=tmp_path / "output",
            defaults_file=mock_defaults,
            mode=DeploymentMode.DEV,
            use_state=False,
        )

        assert configurator_prod.mode == DeploymentMode.PRODUCTION
        assert configurator_dev.mode == DeploymentMode.DEV
