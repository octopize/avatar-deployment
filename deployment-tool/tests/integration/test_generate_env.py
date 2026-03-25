"""Integration tests for generate-env subcommand."""

import pytest
import yaml

from octopize_avatar_deploy.generate_env import GenerateEnvRunner
from octopize_avatar_deploy.input_gatherer import MockInputGatherer
from octopize_avatar_deploy.printer import FilePrinter, SilentPrinter


def _assert_no_deployment_assets(output_dir):
    assert not (output_dir / ".env").exists()
    assert not (output_dir / "docker-compose.yml").exists()
    assert not (output_dir / "nginx" / "nginx.conf").exists()
    assert not (output_dir / "authentik" / "octopize-avatar-blueprint.yaml").exists()


def _read_env_file(path):
    values = {}
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, value = line.split("=", 1)
        values[key] = value
    return values


def _component_env_path(output_dir, component):
    path = output_dir / component / ".env"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _with_output_paths(output_dir, config, *components, extra_paths=None):
    output_paths = {}
    for component in components:
        output_paths[component] = str(_component_env_path(output_dir, component))
    if extra_paths:
        output_paths.update(extra_paths)

    return {
        **config,
        "generate_env": {
            "output_paths": output_paths,
        },
    }


def _assert_web_env_contract(path, expected_values):
    assert _read_env_file(path) == expected_values


def _assert_python_client_env_contract(path, expected_values):
    assert _read_env_file(path) == expected_values


def _assert_api_env_contains(path, expected_values):
    values = _read_env_file(path)
    for key, value in expected_values.items():
        assert values.get(key) == value


def _assert_api_env_excludes(path, excluded_keys):
    values = _read_env_file(path)
    for key in excluded_keys:
        assert key not in values


def _assert_api_env_has_keys(path, expected_keys):
    values = _read_env_file(path)
    for key in expected_keys:
        assert key in values


API_ENV_EXCLUDED_KEYS = {
    "AVATAR_STORAGE_ENDPOINT_PUBLIC_URL",
    "AVATAR_STORAGE_ENDPOINT_INTERNAL_URL",
    "AVATAR_AUTHENTIK_BLUEPRINT_DOMAIN",
    "AVATAR_AUTHENTIK_BLUEPRINT_CLIENT_ID",
    "AVATAR_AUTHENTIK_BLUEPRINT_CLIENT_SECRET",
    "AVATAR_AUTHENTIK_BLUEPRINT_API_REDIRECT_URI",
    "AVATAR_AUTHENTIK_BLUEPRINT_SELF_SERVICE_LICENSE",
}


class TestGenerateEnvWebOnly:
    """Test generating web .env file only."""

    def test_web_env_interactive_external_topology(self, docker_templates_dir, temp_deployment_dir):
        """Interactive generation asks topology questions and derives shared public URLs."""
        runner = GenerateEnvRunner(
            output_dir=temp_deployment_dir,
            components=["web"],
            template_from=str(docker_templates_dir),
            printer=SilentPrinter(),
            input_gatherer=MockInputGatherer(
                {
                    "generate_env.output_paths.web": str(
                        _component_env_path(temp_deployment_dir, "web")
                    ),
                    "required_config.env_name": "test-external",
                    "required_config.organization_name": "TestOrg",
                    "target_env.web_runtime": "host",
                    "target_env.api_location": "external",
                    "target_env.storage_location": "external",
                    "target_env.sso_location": "external",
                    "target_env.public_base_url": "https://myapp.example.com",
                    "target_env.customize_urls": False,
                    "target_env.db_host": "localhost",
                }
            ),
        )

        runner.run(interactive=True)

        web_env = temp_deployment_dir / "web" / ".env"
        assert web_env.exists()

        _assert_web_env_contract(
            web_env,
            {
                "AVATAR_API_PUBLIC_URL": "https://myapp.example.com/api",
                "AVATAR_API_INTERNAL_URL": "https://myapp.example.com/api",
                "AVATAR_STORAGE_ENDPOINT_INTERNAL_URL": "https://myapp.example.com/storage",
                "AVATAR_STORAGE_ENDPOINT_PUBLIC_URL": "https://myapp.example.com/storage",
                "AVATAR_WEB_CLIENT_URL": "https://myapp.example.com/web",
                "AVATAR_SSO_URL": "https://myapp.example.com/api/login/sso",
                "AVATAR_AUTHENTIK_URL": "https://myapp.example.com/sso",
                "AVATAR_SSO_ENABLED": "true",
                "ENV_NAME": "test-external",
            },
        )
        assert not (temp_deployment_dir / "api" / ".env").exists()
        _assert_no_deployment_assets(temp_deployment_dir)

    def test_web_env_non_interactive_local_defaults(
        self, docker_templates_dir, temp_deployment_dir
    ):
        """Non-interactive generation uses local defaults, including host-web localhost."""
        config_file = temp_deployment_dir / "cfg.yaml"
        config_file.write_text(
            yaml.dump(
                _with_output_paths(
                    temp_deployment_dir,
                    {
                        "ENV_NAME": "test",
                        "ORGANIZATION_NAME": "TestOrg",
                    },
                    "web",
                )
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

        _assert_web_env_contract(
            temp_deployment_dir / "web" / ".env",
            {
                "AVATAR_API_PUBLIC_URL": "http://localhost:8080/api",
                "AVATAR_API_INTERNAL_URL": "http://localhost:8080/api",
                "AVATAR_STORAGE_ENDPOINT_INTERNAL_URL": "http://localhost:8333",
                "AVATAR_STORAGE_ENDPOINT_PUBLIC_URL": "http://localhost:8333",
                "AVATAR_WEB_CLIENT_URL": "http://localhost:3000",
                "AVATAR_SSO_URL": "http://localhost:8080/api/login/sso",
                "AVATAR_AUTHENTIK_URL": "http://localhost:8080/sso",
                "AVATAR_SSO_ENABLED": "true",
                "ENV_NAME": "test",
            },
        )
        _assert_no_deployment_assets(temp_deployment_dir)

    def test_web_env_non_interactive_host_web_with_docker_dependencies(
        self, docker_templates_dir, temp_deployment_dir
    ):
        """Host web keeps its localhost entrypoint when dependencies run in Docker."""
        config_file = temp_deployment_dir / "cfg.yaml"
        config_file.write_text(
            yaml.dump(
                _with_output_paths(
                    temp_deployment_dir,
                    {
                        "ENV_NAME": "test-docker-deps",
                        "ORGANIZATION_NAME": "TestOrg",
                        "web_runtime": "host",
                        "api_location": "docker",
                        "storage_location": "docker",
                        "sso_location": "docker",
                    },
                    "web",
                )
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

        _assert_web_env_contract(
            temp_deployment_dir / "web" / ".env",
            {
                "AVATAR_API_PUBLIC_URL": "http://localhost:8080/api",
                "AVATAR_API_INTERNAL_URL": "http://localhost:8080/api",
                "AVATAR_STORAGE_ENDPOINT_INTERNAL_URL": "http://localhost:8080/storage",
                "AVATAR_STORAGE_ENDPOINT_PUBLIC_URL": "http://localhost:8080/storage",
                "AVATAR_WEB_CLIENT_URL": "http://localhost:3000",
                "AVATAR_SSO_URL": "http://localhost:8080/api/login/sso",
                "AVATAR_AUTHENTIK_URL": "http://localhost:8080/sso",
                "AVATAR_SSO_ENABLED": "true",
                "ENV_NAME": "test-docker-deps",
            },
        )
        _assert_no_deployment_assets(temp_deployment_dir)

    def test_web_env_non_interactive_host_web_with_external_dependencies(
        self, docker_templates_dir, temp_deployment_dir
    ):
        """Host web derives shared public URLs when its dependencies are external."""
        config_file = temp_deployment_dir / "cfg.yaml"
        config_file.write_text(
            yaml.dump(
                _with_output_paths(
                    temp_deployment_dir,
                    {
                        "ENV_NAME": "test-public-deps",
                        "ORGANIZATION_NAME": "TestOrg",
                        "web_runtime": "host",
                        "api_location": "external",
                        "storage_location": "external",
                        "sso_location": "external",
                        "public_base_url": "https://myapp.example.com",
                    },
                    "web",
                )
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

        _assert_web_env_contract(
            temp_deployment_dir / "web" / ".env",
            {
                "AVATAR_API_PUBLIC_URL": "https://myapp.example.com/api",
                "AVATAR_API_INTERNAL_URL": "https://myapp.example.com/api",
                "AVATAR_STORAGE_ENDPOINT_INTERNAL_URL": "https://myapp.example.com/storage",
                "AVATAR_STORAGE_ENDPOINT_PUBLIC_URL": "https://myapp.example.com/storage",
                "AVATAR_WEB_CLIENT_URL": "https://myapp.example.com/web",
                "AVATAR_SSO_URL": "https://myapp.example.com/api/login/sso",
                "AVATAR_AUTHENTIK_URL": "https://myapp.example.com/sso",
                "AVATAR_SSO_ENABLED": "true",
                "ENV_NAME": "test-public-deps",
            },
        )
        _assert_no_deployment_assets(temp_deployment_dir)


class TestGenerateEnvApiOnly:
    """Test generating API .env file only."""

    def test_api_env_non_interactive_local_defaults(
        self, docker_templates_dir, temp_deployment_dir
    ):
        """API env generation keeps runtime URLs and omits deploy-only variables."""
        config_file = temp_deployment_dir / "cfg.yaml"
        config_file.write_text(
            yaml.dump(
                _with_output_paths(
                    temp_deployment_dir,
                    {
                        "ENV_NAME": "test",
                        "ORGANIZATION_NAME": "TestOrg",
                    },
                    "api",
                )
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

        _assert_api_env_contains(
            api_env,
            {
                "AVATAR_API_URL": "http://localhost:8080/api",
                "AVATAR_WEB_CLIENT_URL": "http://localhost:3000",
                "SSO_PROVIDER_APP_NAME": "avatar-api",
                "SSO_PROVIDER_URL": "http://localhost:8080/sso",
            },
        )
        _assert_api_env_has_keys(
            api_env,
            {
                "SSO_CLIENT_ID",
                "SSO_CLIENT_SECRET",
                "USE_CONSOLE_LOGGING",
                "IS_SENTRY_ENABLED",
                "LOG_LEVEL",
                "MAIL_PROVIDER",
                "USE_EMAIL_AUTHENTICATION",
            },
        )
        content = api_env.read_text()
        assert "TELEMETRY_S3_ENDPOINT_URL" in content
        assert "TELEMETRY_S3_REGION" in content
        _assert_api_env_excludes(
            api_env,
            API_ENV_EXCLUDED_KEYS,
        )
        assert not (temp_deployment_dir / "web" / ".env").exists()
        _assert_no_deployment_assets(temp_deployment_dir)

    def test_api_env_with_explicit_config_values(self, docker_templates_dir, temp_deployment_dir):
        """Explicit config values still override derived defaults."""
        config_file = temp_deployment_dir / "cfg.yaml"
        config_file.write_text(
            yaml.dump(
                _with_output_paths(
                    temp_deployment_dir,
                    {
                        "ENV_NAME": "test-api",
                        "ORGANIZATION_NAME": "TestOrg",
                        "AVATAR_API_URL": "https://api.example.com/api",
                        "AVATAR_STORAGE_ENDPOINT_PUBLIC_URL": "https://api.example.com/storage",
                        "AVATAR_STORAGE_ENDPOINT_INTERNAL_URL": "http://db.internal/storage",
                        "SSO_PROVIDER_URL": "https://api.example.com/sso",
                        "DB_HOST": "db.example.com",
                    },
                    "api",
                )
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
        _assert_api_env_contains(
            api_env,
            {
                "AVATAR_API_URL": "https://api.example.com/api",
                "AVATAR_WEB_CLIENT_URL": "https://api.example.com/web",
                "SSO_PROVIDER_URL": "https://api.example.com/sso",
            },
        )
        _assert_api_env_excludes(
            api_env,
            API_ENV_EXCLUDED_KEYS,
        )


class TestGenerateEnvBothComponents:
    """Test generating both api and web .env files."""

    def test_both_components_non_interactive(self, docker_templates_dir, temp_deployment_dir):
        """Both selected components receive env files using the shared derived defaults."""
        config_file = temp_deployment_dir / "cfg.yaml"
        config_file.write_text(
            yaml.dump(
                _with_output_paths(
                    temp_deployment_dir,
                    {
                        "ENV_NAME": "test-both",
                        "ORGANIZATION_NAME": "TestOrg",
                    },
                    "api",
                    "web",
                )
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

        api_env = temp_deployment_dir / "api" / ".env"
        web_env = temp_deployment_dir / "web" / ".env"
        _assert_api_env_contains(
            api_env,
            {
                "AVATAR_API_URL": "http://localhost:8080/api",
                "AVATAR_WEB_CLIENT_URL": "http://localhost:3000",
            },
        )
        _assert_api_env_excludes(
            api_env,
            API_ENV_EXCLUDED_KEYS,
        )
        _assert_web_env_contract(
            web_env,
            {
                "AVATAR_API_PUBLIC_URL": "http://localhost:8080/api",
                "AVATAR_API_INTERNAL_URL": "http://localhost:8080/api",
                "AVATAR_STORAGE_ENDPOINT_INTERNAL_URL": "http://localhost:8333",
                "AVATAR_STORAGE_ENDPOINT_PUBLIC_URL": "http://localhost:8333",
                "AVATAR_WEB_CLIENT_URL": "http://localhost:3000",
                "AVATAR_SSO_URL": "http://localhost:8080/api/login/sso",
                "AVATAR_AUTHENTIK_URL": "http://localhost:8080/sso",
                "AVATAR_SSO_ENABLED": "true",
                "ENV_NAME": "test-both",
            },
        )
        _assert_no_deployment_assets(temp_deployment_dir)

    def test_both_components_with_target(self, docker_templates_dir, temp_deployment_dir):
        """Named targets keep their precedence over derived defaults."""
        config_file = temp_deployment_dir / "envs.yaml"
        config_file.write_text(
            yaml.dump(
                _with_output_paths(
                    temp_deployment_dir,
                    {
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
                    },
                    "api",
                    "web",
                )
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

        api_env = temp_deployment_dir / "api" / ".env"
        web_env = temp_deployment_dir / "web" / ".env"
        _assert_api_env_contains(
            api_env,
            {
                "AVATAR_API_URL": "https://staging.example.com/api",
                "AVATAR_WEB_CLIENT_URL": "https://staging.example.com/web",
                "SSO_PROVIDER_URL": "https://staging.example.com/sso",
            },
        )
        _assert_api_env_excludes(
            api_env,
            API_ENV_EXCLUDED_KEYS,
        )
        _assert_web_env_contract(
            web_env,
            {
                "AVATAR_API_PUBLIC_URL": "https://staging.example.com/api",
                "AVATAR_API_INTERNAL_URL": "https://staging.example.com/api",
                "AVATAR_STORAGE_ENDPOINT_INTERNAL_URL": "https://staging.example.com/internal-storage",
                "AVATAR_STORAGE_ENDPOINT_PUBLIC_URL": "https://staging.example.com/storage",
                "AVATAR_WEB_CLIENT_URL": "https://staging.example.com/web",
                "AVATAR_SSO_URL": "https://staging.example.com/api/login/sso",
                "AVATAR_AUTHENTIK_URL": "https://staging.example.com/sso",
                "AVATAR_SSO_ENABLED": "true",
                "ENV_NAME": "test-staging",
            },
        )


class TestGenerateEnvOverrides:
    """Test inline override behavior."""

    def test_inline_api_override_beats_target(self, docker_templates_dir, temp_deployment_dir):
        """CLI overrides still win over named presets."""
        config_file = temp_deployment_dir / "cfg.yaml"
        config_file.write_text(
            yaml.dump(
                _with_output_paths(
                    temp_deployment_dir,
                    {
                        "ENV_NAME": "test",
                        "ORGANIZATION_NAME": "TestOrg",
                        "environments": {
                            "prod": {
                                "api_url": "https://prod.example.com/api",
                                "storage_public_url": "https://prod.example.com/storage",
                                "sso_url": "https://prod.example.com/sso",
                            }
                        },
                    },
                    "web",
                )
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

        _assert_web_env_contract(
            temp_deployment_dir / "web" / ".env",
            {
                "AVATAR_API_PUBLIC_URL": "http://override:1234/api",
                "AVATAR_API_INTERNAL_URL": "http://override:1234/api",
                "AVATAR_STORAGE_ENDPOINT_INTERNAL_URL": "http://localhost:8333",
                "AVATAR_STORAGE_ENDPOINT_PUBLIC_URL": "https://prod.example.com/storage",
                "AVATAR_WEB_CLIENT_URL": "http://override:1234/web",
                "AVATAR_SSO_URL": "http://override:1234/api/login/sso",
                "AVATAR_AUTHENTIK_URL": "https://prod.example.com/sso",
                "AVATAR_SSO_ENABLED": "true",
                "ENV_NAME": "test",
            },
        )


class TestGenerateEnvPythonClient:
    """Test generating python_client .env only."""

    def test_python_client_env_non_interactive_local_host_api(
        self, docker_templates_dir, temp_deployment_dir
    ):
        """Python client should point at direct host storage for host-local API."""
        config_file = temp_deployment_dir / "cfg.yaml"
        config_file.write_text(
            yaml.dump(
                _with_output_paths(
                    temp_deployment_dir,
                    {
                        "ENV_NAME": "test-python-client",
                        "ORGANIZATION_NAME": "TestOrg",
                    },
                    "python_client",
                )
            )
        )

        runner = GenerateEnvRunner(
            output_dir=temp_deployment_dir,
            components=["python_client"],
            template_from=str(docker_templates_dir),
            printer=SilentPrinter(),
            input_gatherer=MockInputGatherer({}),
        )

        runner.run(interactive=False, config_file=config_file)

        python_client_env = temp_deployment_dir / "python_client" / ".env"
        assert python_client_env.exists()

        _assert_python_client_env_contract(
            python_client_env,
            {
                "AVATAR_STORAGE_ENDPOINT_URL": "http://localhost:8333",
                "AVATAR_BASE_API_URL": "http://localhost:8080/api",
            },
        )
        assert not (temp_deployment_dir / "api" / ".env").exists()
        assert not (temp_deployment_dir / "web" / ".env").exists()
        _assert_no_deployment_assets(temp_deployment_dir)

    def test_python_client_env_non_interactive_docker_backed_api(
        self, docker_templates_dir, temp_deployment_dir
    ):
        """Python client should use the gateway storage URL for docker-backed API."""
        config_file = temp_deployment_dir / "cfg.yaml"
        config_file.write_text(
            yaml.dump(
                _with_output_paths(
                    temp_deployment_dir,
                    {
                        "ENV_NAME": "test-python-client-docker",
                        "ORGANIZATION_NAME": "TestOrg",
                        "api_runtime": "docker",
                    },
                    "python_client",
                )
            )
        )

        runner = GenerateEnvRunner(
            output_dir=temp_deployment_dir,
            components=["python_client"],
            template_from=str(docker_templates_dir),
            printer=SilentPrinter(),
            input_gatherer=MockInputGatherer({}),
        )

        runner.run(interactive=False, config_file=config_file)

        _assert_python_client_env_contract(
            temp_deployment_dir / "python_client" / ".env",
            {
                "AVATAR_STORAGE_ENDPOINT_URL": "http://localhost:8080/storage",
                "AVATAR_BASE_API_URL": "http://localhost:8080/api",
            },
        )
        _assert_no_deployment_assets(temp_deployment_dir)

    def test_python_client_env_non_interactive_external_public_base(
        self, docker_templates_dir, temp_deployment_dir
    ):
        """Python client should derive both URLs from the shared public base."""
        config_file = temp_deployment_dir / "cfg.yaml"
        config_file.write_text(
            yaml.dump(
                _with_output_paths(
                    temp_deployment_dir,
                    {
                        "ENV_NAME": "test-python-client-public",
                        "ORGANIZATION_NAME": "TestOrg",
                        "api_location": "external",
                        "storage_location": "external",
                        "sso_location": "external",
                        "public_base_url": "https://myapp.example.com",
                    },
                    "python_client",
                )
            )
        )

        runner = GenerateEnvRunner(
            output_dir=temp_deployment_dir,
            components=["python_client"],
            template_from=str(docker_templates_dir),
            printer=SilentPrinter(),
            input_gatherer=MockInputGatherer({}),
        )

        runner.run(interactive=False, config_file=config_file)

        _assert_python_client_env_contract(
            temp_deployment_dir / "python_client" / ".env",
            {
                "AVATAR_STORAGE_ENDPOINT_URL": "https://myapp.example.com/storage",
                "AVATAR_BASE_API_URL": "https://myapp.example.com/api",
            },
        )
        _assert_no_deployment_assets(temp_deployment_dir)


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
                _with_output_paths(
                    temp_deployment_dir,
                    {
                        "ENV_NAME": "test",
                        "ORGANIZATION_NAME": "TestOrg",
                        "environments": {"prod": {"api_url": "https://prod.example.com/api"}},
                    },
                    "web",
                )
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


class TestGenerateEnvOutputPaths:
    """Test configurable output path resolution behavior."""

    def test_relative_paths_resolve_from_config_directory(
        self, docker_templates_dir, temp_deployment_dir
    ):
        """Relative configured paths should resolve from the config file directory."""
        config_dir = temp_deployment_dir / "configs"
        config_dir.mkdir()
        relative_env_dir = config_dir / "relative-envs"
        relative_env_dir.mkdir()
        config_file = config_dir / "cfg.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "ENV_NAME": "test-relative",
                    "ORGANIZATION_NAME": "TestOrg",
                    "generate_env": {
                        "output_paths": {
                            "web": "relative-envs/web.env",
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

        runner.run(interactive=False, config_file=config_file)

        web_env = config_dir / "relative-envs" / "web.env"
        assert web_env.exists()
        _assert_web_env_contract(
            web_env,
            {
                "AVATAR_API_PUBLIC_URL": "http://localhost:8080/api",
                "AVATAR_API_INTERNAL_URL": "http://localhost:8080/api",
                "AVATAR_STORAGE_ENDPOINT_INTERNAL_URL": "http://localhost:8333",
                "AVATAR_STORAGE_ENDPOINT_PUBLIC_URL": "http://localhost:8333",
                "AVATAR_WEB_CLIENT_URL": "http://localhost:3000",
                "AVATAR_SSO_URL": "http://localhost:8080/api/login/sso",
                "AVATAR_AUTHENTIK_URL": "http://localhost:8080/sso",
                "AVATAR_SSO_ENABLED": "true",
                "ENV_NAME": "test-relative",
            },
        )

    def test_interactive_prompt_persists_only_missing_selected_components(
        self, docker_templates_dir, temp_deployment_dir
    ):
        """Interactive runs should prompt for selected missing paths and write them back."""
        config_dir = temp_deployment_dir / "configs"
        config_dir.mkdir()
        relative_env_dir = config_dir / "envs"
        relative_env_dir.mkdir()
        prompted_dir = config_dir / "prompted"
        prompted_dir.mkdir()
        config_file = config_dir / "cfg.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "ENV_NAME": "test-prompted",
                    "ORGANIZATION_NAME": "TestOrg",
                    "api_runtime": "host",
                    "web_runtime": "host",
                    "storage_location": "host",
                    "sso_location": "host",
                    "AVATAR_API_URL": "http://localhost:8080/api",
                    "AVATAR_STORAGE_ENDPOINT_PUBLIC_URL": "http://localhost:8333",
                    "SSO_PROVIDER_URL": "http://localhost:8080/sso",
                    "generate_env": {
                        "output_paths": {
                            "web": "envs/web.env",
                            "future_component": "envs/future.env",
                        }
                    },
                }
            )
        )

        runner = GenerateEnvRunner(
            output_dir=temp_deployment_dir,
            components=["python_client", "web"],
            template_from=str(docker_templates_dir),
            printer=SilentPrinter(),
            input_gatherer=MockInputGatherer(
                {
                    "generate_env.output_paths.python_client": "prompted/python-client.env",
                }
            ),
        )

        runner.run(interactive=True, config_file=config_file)

        assert (config_dir / "prompted" / "python-client.env").exists()
        assert (config_dir / "envs" / "web.env").exists()

        persisted = yaml.safe_load(config_file.read_text())
        assert (
            persisted["generate_env"]["output_paths"]["python_client"]
            == "prompted/python-client.env"
        )
        assert persisted["generate_env"]["output_paths"]["web"] == "envs/web.env"
        assert persisted["generate_env"]["output_paths"]["future_component"] == "envs/future.env"

    def test_non_interactive_fails_when_selected_component_lacks_path(
        self, docker_templates_dir, temp_deployment_dir
    ):
        """Non-interactive runs should fail clearly for missing selected component paths."""
        config_file = temp_deployment_dir / "cfg.yaml"
        config_file.write_text(
            yaml.dump(
                _with_output_paths(
                    temp_deployment_dir,
                    {
                        "ENV_NAME": "test-missing-path",
                        "ORGANIZATION_NAME": "TestOrg",
                    },
                    "api",
                )
            )
        )

        runner = GenerateEnvRunner(
            output_dir=temp_deployment_dir,
            components=["api", "web"],
            template_from=str(docker_templates_dir),
            printer=SilentPrinter(),
            input_gatherer=MockInputGatherer({}),
        )

        with pytest.raises(
            ValueError, match="Missing output path for selected component\\(s\\): web"
        ):
            runner.run(interactive=False, config_file=config_file)

    def test_missing_parent_directory_is_rejected(self, docker_templates_dir, temp_deployment_dir):
        """Configured output paths must point into existing parent directories."""
        config_file = temp_deployment_dir / "cfg.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "ENV_NAME": "test-missing-parent",
                    "ORGANIZATION_NAME": "TestOrg",
                    "generate_env": {
                        "output_paths": {
                            "web": str(temp_deployment_dir / "missing" / "web.env"),
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

        with pytest.raises(ValueError, match="Output path parent directory does not exist"):
            runner.run(interactive=False, config_file=config_file)

    def test_unknown_configured_components_are_ignored_when_not_selected(
        self, docker_templates_dir, temp_deployment_dir
    ):
        """Unknown configured component names should not trigger generation on their own."""
        config_file = temp_deployment_dir / "cfg.yaml"
        config_file.write_text(
            yaml.dump(
                _with_output_paths(
                    temp_deployment_dir,
                    {
                        "ENV_NAME": "test-unknown-config",
                        "ORGANIZATION_NAME": "TestOrg",
                    },
                    "web",
                    extra_paths={"future_component": str(temp_deployment_dir / "future.env")},
                )
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

        assert (temp_deployment_dir / "web" / ".env").exists()
        assert not (temp_deployment_dir / "future.env").exists()

    def test_output_path_overrides_beat_configured_paths(
        self, docker_templates_dir, temp_deployment_dir
    ):
        """Runner path overrides should win over configured output paths."""
        configured_path = _component_env_path(temp_deployment_dir, "web")
        override_dir = temp_deployment_dir / "override"
        override_dir.mkdir()
        override_path = override_dir / "web.env"
        config_file = temp_deployment_dir / "cfg.yaml"
        config_file.write_text(
            yaml.dump(
                _with_output_paths(
                    temp_deployment_dir,
                    {
                        "ENV_NAME": "test-override-path",
                        "ORGANIZATION_NAME": "TestOrg",
                    },
                    "web",
                )
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
            output_path_overrides={"web": override_path},
        )

        assert override_path.exists()
        assert not configured_path.exists()


class TestGenerateEnvOutputMessages:
    """Test generate-env completion messaging."""

    def test_generate_env_omits_deploy_completion_footer(
        self, docker_templates_dir, temp_deployment_dir
    ):
        """generate-env should not print deploy-specific footer text."""
        config_file = temp_deployment_dir / "cfg.yaml"
        config_file.write_text(
            yaml.dump(
                _with_output_paths(
                    temp_deployment_dir,
                    {
                        "ENV_NAME": "test-output",
                        "ORGANIZATION_NAME": "TestOrg",
                    },
                    "web",
                )
            )
        )
        log_file = temp_deployment_dir / "generate-env.log"

        runner = GenerateEnvRunner(
            output_dir=temp_deployment_dir,
            components=["web"],
            template_from=str(docker_templates_dir),
            printer=FilePrinter(log_file),
            input_gatherer=MockInputGatherer({}),
        )

        runner.run(interactive=False, config_file=config_file)

        output = log_file.read_text()
        assert "Next steps:" not in output
        assert "Configuration files generated in:" not in output
        assert "Generate-env Complete!" in output
