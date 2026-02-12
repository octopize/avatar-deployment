"""Logging configuration step."""

from typing import Any

from .base import DefaultKey, DeploymentStep


class LoggingStep(DeploymentStep):
    """Handles application logging configuration."""

    name = "logging"
    description = "Configure application logging settings"
    required = False

    def collect_config(self) -> dict[str, Any]:
        """Collect logging configuration."""
        config = {}

        # Console logging
        if "USE_CONSOLE_LOGGING" not in self.config:
            config["USE_CONSOLE_LOGGING"] = self.get_default_value(
                "application.use_console_logging"
            )

        # Log level
        config["LOG_LEVEL"] = self.get_config("LOG_LEVEL", DefaultKey("application.log_level"))

        return config

    def generate_secrets(self) -> dict[str, str]:
        """No secrets needed for logging."""
        return {}
