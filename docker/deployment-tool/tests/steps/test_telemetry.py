#!/usr/bin/env python3
"""Tests for telemetry configuration step."""

import pytest

from octopize_avatar_deploy.steps import TelemetryStep


class TestTelemetryStep:
    """Test the TelemetryStep."""

    @pytest.fixture
    def defaults(self):
        """Provide telemetry defaults."""
        return {
            "application": {
                "sentry_enabled": "false",
                "use_console_logging": True,
                "log_level": "INFO",
            },
            "telemetry": {
                "enabled": False,
                "endpoint_url": "",
                "region": "",
            },
        }

    @pytest.fixture
    def defaults_enabled(self):
        """Provide telemetry defaults with telemetry enabled."""
        return {
            "application": {
                "sentry_enabled": "true",
                "use_console_logging": True,
                "log_level": "DEBUG",
            },
            "telemetry": {
                "enabled": True,
                "endpoint_url": "https://telemetry.example.com",
                "region": "us-east-1",
            },
        }

    @pytest.fixture
    def step(self, tmp_path, defaults):
        """Create a TelemetryStep instance."""
        config = {}
        return TelemetryStep(tmp_path, defaults, config, interactive=False)

    @pytest.fixture
    def step_enabled(self, tmp_path, defaults_enabled):
        """Create a TelemetryStep instance with telemetry enabled."""
        config = {}
        return TelemetryStep(tmp_path, defaults_enabled, config, interactive=False)

    def test_collect_config(self, step):
        """Test telemetry configuration collection."""
        config = step.collect_config()

        assert "IS_SENTRY_ENABLED" in config
        assert "LOG_LEVEL" in config

    def test_collect_config_values_disabled(self, step):
        """Test telemetry configuration when disabled."""
        config = step.collect_config()

        assert config["IS_SENTRY_ENABLED"] == "false"
        assert config["LOG_LEVEL"] == "INFO"

    def test_collect_config_values_enabled(self, step_enabled):
        """Test telemetry configuration when enabled."""
        config = step_enabled.collect_config()

        assert config["IS_SENTRY_ENABLED"] == "true"
        assert config["TELEMETRY_S3_ENDPOINT_URL"] == "https://telemetry.example.com"
        assert config["TELEMETRY_S3_REGION"] == "us-east-1"
        assert config["LOG_LEVEL"] == "DEBUG"

    def test_collect_config_custom_values(self, tmp_path, defaults):
        """Test that custom values override defaults."""
        config = {
            "IS_SENTRY_ENABLED": "true",
            "LOG_LEVEL": "WARNING",
            "TELEMETRY_S3_ENDPOINT_URL": "https://custom.telemetry.com",
        }
        step = TelemetryStep(tmp_path, defaults, config, interactive=False)

        result = step.collect_config()

        assert result["IS_SENTRY_ENABLED"] == "true"
        assert result["LOG_LEVEL"] == "WARNING"

    def test_collect_config_console_logging(self, step):
        """Test console logging configuration."""
        config = step.collect_config()

        assert "USE_CONSOLE_LOGGING" in config
        assert config["USE_CONSOLE_LOGGING"] is True

    def test_generate_secrets_non_interactive(self, step):
        """Test secret generation in non-interactive mode."""
        secrets_dict = step.generate_secrets()

        # Non-interactive mode should not prompt for secrets
        assert isinstance(secrets_dict, dict)

    def test_step_metadata(self, step):
        """Test step metadata."""
        assert step.name == "telemetry"
        assert step.required is False  # Telemetry is optional
        assert (
            "telemetry" in step.description.lower()
            or "monitoring" in step.description.lower()
        )
