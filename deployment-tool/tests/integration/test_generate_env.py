"""Integration tests for generate-env subcommand."""

import pytest
import yaml

from octopize_avatar_deploy.generate_env import GenerateEnvRunner
from octopize_avatar_deploy.input_gatherer import MockInputGatherer
from octopize_avatar_deploy.printer import SilentPrinter


def _assert_no_deployment_assets(output_dir):
    assert not (output_dir / ".env").exists()
    assert not (output_dir / "docker-compose.yml").exists()
    assert not (output_dir / "nginx" / "nginx.conf").exists()
    assert not (output_dir / "authentik" / "octopize-avatar-blueprint.yaml").exists()


class TestGenerateEnvWebOnly:
    """Test generating web .env file only."""

    def test_web_env_interactive(self, docker_templates_dir, temp_deployment_dir):
        """Interactive web generation prompts for target URLs directly."""
        runner = GenerateEnvRunner(
            output_dir=temp_deployment_dir,
            components=["web"],
            template_from=str(docker_templates_dir),
            printer=SilentPrinter(),
            input_gatherer=MockInputGatherer(
                {
                    "required_config.public_url": "myapp.example.com",
                    "required_config.env_name": "test-local",
                    "required_config.organization_name": "TestOrg",
                    "target_env.api_url": "https://myapp.example.com/api",
                    "target_env.storage_public_url": "https://myapp.example.com/storage",
                    "target_env.storage_internal_url": "https://myapp.example.com/storage",
                    "target_env.sso_url": "https://myapp.example.com/sso",
                    "target_env.db_host": "localhost",
                }
            ),
        )

        runner.run(interactive=True)

        web_env = temp_deployment_dir / "web" / ".env"
        assert web_env.exists()

        content = web_env.read_text()
        assert "AVATAR_API_URL=https://myapp.example.com/api" in content
        assert "AVATAR_STORAGE_ENDPOINT_PUBLIC_URL=https://myapp.example.com/storage" in content
        assert "SSO_PROVIDER_URL=https://myapp.example.com/sso" in content
        assert not (temp_deployment_dir / "api" / ".env").exists()
        _assert_no_deployment_assets(temp_deployment_dir)

    def test_web_env_non_interactive_defaults(self, docker_templates_dir, temp_deployment_dir):
        """Non-interactive web generation uses TargetEnvironmentStep defaults."""
        config_file = temp_deployment_dir / "cfg.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "PUBLIC_URL": "test.example.com",
                    "ENV_NAME": "test",
                    "ORGANIZATION_NAME": "TestOrg",
                }
            )
        )

        runner = GenerateEnvRunner(
            output_dir=temp_deployment_dir,
            components=["web"],
            template_from=str(docker_templates_dir),
            printer=SilentPrinter(),
            input_gatherer=MockInputGatherer({}),
        )

        runner.run(interactive=False, config_file=config_file)

        content = (temp_deployment_dir / "web" / ".env").read_text()
        assert "AVATAR_API_URL=http://localhost:8000" in content
        assert "AVATAR_STORAGE_ENDPOINT_PUBLIC_URL=http://localhost:8333" in content
        assert "SSO_PROVIDER_URL=http://localhost:9000/sso" in content
        _assert_no_deployment_assets(temp_deployment_dir)


class TestGenerateEnvApiOnly:
    """Test generating API .env file only."""

    def test_api_env_non_interactive_defaults(self, docker_templates_dir, temp_deployment_dir):
        """API env generation should succeed with TargetEnvironmentStep defaults."""
        config_file = temp_deployment_dir / "cfg.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "PUBLIC_URL": "test.example.com",
                    "ENV_NAME": "test",
                    "ORGANIZATION_NAME": "TestOrg",
                }
            )
        )

        runner = GenerateEnvRunner(
            output_dir=temp_deployment_dir,
            components=["api"],
            template_from=str(docker_templates_dir),
            printer=SilentPrinter(),
            input_gatherer=MockInputGatherer({}),
        )

        runner.run(interactive=False, config_file=config_file)

        api_env = temp_deployment_dir / "api" / ".env"
        assert api_env.exists()

        content = api_env.read_text()
        assert "AVATAR_API_URL=http://localhost:8000" in content
        assert "AVATAR_STORAGE_ENDPOINT_PUBLIC_URL=http://localhost:8333" in content
        assert "AVATAR_STORAGE_ENDPOINT_INTERNAL_URL=http://localhost:8333" in content
        assert "SSO_PROVIDER_URL=http://localhost:9000/sso" in content
        assert "AVATAR_AUTHENTIK_BLUEPRINT_DOMAIN=test.example.com" in content
        assert not (temp_deployment_dir / "web" / ".env").exists()
        _assert_no_deployment_assets(temp_deployment_dir)

    def test_api_env_with_explicit_config_values(self, docker_templates_dir, temp_deployment_dir):
        """Top-level config values should override defaults."""
        config_file = temp_deployment_dir / "cfg.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "PUBLIC_URL": "api.example.com",
                    "ENV_NAME": "test-api",
                    "ORGANIZATION_NAME": "TestOrg",
                    "AVATAR_API_URL": "https://api.example.com/api",
                    "AVATAR_STORAGE_ENDPOINT_PUBLIC_URL": "https://api.example.com/storage",
                    "AVATAR_STORAGE_ENDPOINT_INTERNAL_URL": "http://db.internal/storage",
                    "SSO_PROVIDER_URL": "https://api.example.com/sso",
                    "DB_HOST": "db.example.com",
                }
            )
        )

        runner = GenerateEnvRunner(
            output_dir=temp_deployment_dir,
            components=["api"],
            template_from=str(docker_templates_dir),
            printer=SilentPrinter(),
            input_gatherer=MockInputGatherer({}),
        )

        runner.run(interactive=False, config_file=config_file)

        content = (temp_deployment_dir / "api" / ".env").read_text()
        assert "AVATAR_API_URL=https://api.example.com/api" in content
        assert "AVATAR_STORAGE_ENDPOINT_INTERNAL_URL=http://db.internal/storage" in content
        assert "SSO_PROVIDER_URL=https://api.example.com/sso" in content


class TestGenerateEnvBothComponents:
    """Test generating both api and web .env files."""

    def test_both_components_non_interactive(self, docker_templates_dir, temp_deployment_dir):
        """Both selected components should receive env files using shared defaults."""
        config_file = temp_deployment_dir / "cfg.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "PUBLIC_URL": "both.example.com",
                    "ENV_NAME": "test-both",
                    "ORGANIZATION_NAME": "TestOrg",
                }
            )
        )

        runner = GenerateEnvRunner(
            output_dir=temp_deployment_dir,
            components=["api", "web"],
            template_from=str(docker_templates_dir),
            printer=SilentPrinter(),
            input_gatherer=MockInputGatherer({}),
        )

        runner.run(interactive=False, config_file=config_file)

        api_content = (temp_deployment_dir / "api" / ".env").read_text()
        web_content = (temp_deployment_dir / "web" / ".env").read_text()
        assert "AVATAR_API_URL=http://localhost:8000" in api_content
        assert "AVATAR_API_URL=http://localhost:8000" in web_content
        _assert_no_deployment_assets(temp_deployment_dir)

    def test_both_components_with_target(self, docker_templates_dir, temp_deployment_dir):
        """Named targets should map from the example lower-snake-case config format."""
        config_file = temp_deployment_dir / "envs.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "PUBLIC_URL": "staging.example.com",
                    "ENV_NAME": "test-staging",
                    "ORGANIZATION_NAME": "TestOrg",
                    "environments": {
                        "staging": {
                            "api_url": "https://staging.example.com/api",
                            "storage_public_url": "https://staging.example.com/storage",
                            "storage_internal_url": "https://staging.example.com/internal-storage",
                            "sso_url": "https://staging.example.com/sso",
                            "db_host": "staging-db.example.com",
                        }
                    },
                }
            )
        )

        runner = GenerateEnvRunner(
            output_dir=temp_deployment_dir,
            components=["api", "web"],
            template_from=str(docker_templates_dir),
            printer=SilentPrinter(),
            input_gatherer=MockInputGatherer({}),
        )

        runner.run(interactive=False, config_file=config_file, target="staging")

        api_content = (temp_deployment_dir / "api" / ".env").read_text()
        web_content = (temp_deployment_dir / "web" / ".env").read_text()
        assert "AVATAR_API_URL=https://staging.example.com/api" in api_content
        assert (
            "AVATAR_STORAGE_ENDPOINT_INTERNAL_URL=https://staging.example.com/internal-storage"
            in api_content
        )
        assert "SSO_PROVIDER_URL=https://staging.example.com/sso" in web_content


class TestGenerateEnvOverrides:
    """Test inline override behavior."""

    def test_inline_api_override_beats_target(self, docker_templates_dir, temp_deployment_dir):
        """CLI overrides should win over named presets."""
        config_file = temp_deployment_dir / "cfg.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "PUBLIC_URL": "override.example.com",
                    "ENV_NAME": "test",
                    "ORGANIZATION_NAME": "TestOrg",
                    "environments": {
                        "prod": {
                            "api_url": "https://prod.example.com/api",
                            "storage_public_url": "https://prod.example.com/storage",
                            "sso_url": "https://prod.example.com/sso",
                        }
                    },
                }
            )
        )

        runner = GenerateEnvRunner(
            output_dir=temp_deployment_dir,
            components=["web"],
            template_from=str(docker_templates_dir),
            printer=SilentPrinter(),
            input_gatherer=MockInputGatherer({}),
        )

        runner.run(
            interactive=False,
            config_file=config_file,
            target="prod",
            api_url="http://override:1234/api",
        )

        content = (temp_deployment_dir / "web" / ".env").read_text()
        assert "AVATAR_API_URL=http://override:1234/api" in content
        assert "AVATAR_STORAGE_ENDPOINT_PUBLIC_URL=https://prod.example.com/storage" in content


class TestGenerateEnvErrors:
    """Test error handling and validation."""

    def test_unknown_component_raises(self, docker_templates_dir, temp_deployment_dir):
        """Unknown component name should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown component"):
            GenerateEnvRunner(
                output_dir=temp_deployment_dir,
                components=["nonexistent"],
                template_from=str(docker_templates_dir),
                printer=SilentPrinter(),
            )

    def test_unknown_target_raises(self, docker_templates_dir, temp_deployment_dir):
        """Unknown target environment should raise ValueError."""
        config_file = temp_deployment_dir / "cfg.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "PUBLIC_URL": "example.com",
                    "ENV_NAME": "test",
                    "ORGANIZATION_NAME": "TestOrg",
                    "environments": {"prod": {"api_url": "https://prod.example.com/api"}},
                }
            )
        )

        runner = GenerateEnvRunner(
            output_dir=temp_deployment_dir,
            components=["web"],
            template_from=str(docker_templates_dir),
            printer=SilentPrinter(),
            input_gatherer=MockInputGatherer({}),
        )

        with pytest.raises(ValueError, match="Unknown target environment"):
            runner.run(interactive=False, config_file=config_file, target="nonexistent")

    def test_empty_public_url_raises(self, docker_templates_dir, temp_deployment_dir):
        """PUBLIC_URL remains required and must not be empty."""
        config_file = temp_deployment_dir / "cfg.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "PUBLIC_URL": "",
                    "ENV_NAME": "test",
                    "ORGANIZATION_NAME": "TestOrg",
                }
            )
        )

        runner = GenerateEnvRunner(
            output_dir=temp_deployment_dir,
            components=["web"],
            template_from=str(docker_templates_dir),
            printer=SilentPrinter(),
            input_gatherer=MockInputGatherer({}),
        )

        with pytest.raises(ValueError, match="PUBLIC_URL is required"):
            runner.run(interactive=False, config_file=config_file)
