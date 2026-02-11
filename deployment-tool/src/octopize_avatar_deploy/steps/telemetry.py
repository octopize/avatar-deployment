"""Telemetry and monitoring configuration step."""

from typing import Any

from .base import DeploymentStep


class TelemetryStep(DeploymentStep):
    """Handles telemetry and Sentry monitoring configuration."""

    name = "telemetry"
    description = "Configure telemetry and monitoring (Sentry, usage analytics)"
    required = False

    def collect_config(self) -> dict[str, Any]:
        """Collect telemetry configuration."""
        config = {}

        default_sentry_enabled = self.get_default_value("application.sentry_enabled")
        sentry_enabled = (
            self.prompt_yes_no(
                "Enable Sentry error monitoring?",
                default=default_sentry_enabled == "true",
                key="telemetry.enable_sentry",
            )
            if self.interactive
            else default_sentry_enabled == "true"
        )

        config["IS_SENTRY_ENABLED"] = "true" if sentry_enabled else "false"

        default_telemetry_enabled = self.get_default_value("telemetry.enabled")
        enable_telemetry = (
            self.prompt_yes_no(
                "Enable usage telemetry?",
                default=default_telemetry_enabled,
                key="telemetry.enable_telemetry",
            )
            if self.interactive
            else default_telemetry_enabled
        )

        if enable_telemetry:
            config["TELEMETRY_S3_ENDPOINT_URL"] = self.get_default_value("telemetry.endpoint_url")
            config["TELEMETRY_S3_REGION"] = self.get_default_value("telemetry.region")
        else:
            config["TELEMETRY_S3_ENDPOINT_URL"] = ""
            config["TELEMETRY_S3_REGION"] = ""

        self.config.update(config)

        return config

    def generate_secrets(self) -> dict[str, str]:
        """Generate telemetry-related secrets."""
        # Only generate secrets if telemetry is enabled

        # The user will have to provide these if telemetry is enabled
        return {
            "telemetry_s3_access_key_id": "",
            "telemetry_s3_secret_access_key": "",
        }
        return {}
