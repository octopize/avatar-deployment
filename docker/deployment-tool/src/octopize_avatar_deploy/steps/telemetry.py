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

        sentry_enabled = (
            self.prompt_yes_no(
                "Enable Sentry error monitoring?",
                default=self.defaults["application"]["sentry_enabled"] == "true",
            )
            if self.interactive
            else self.defaults["application"]["sentry_enabled"] == "true"
        )

        config["IS_SENTRY_ENABLED"] = "true" if sentry_enabled else "false"

        enable_telemetry = (
            self.prompt_yes_no(
                "Enable usage telemetry?",
                default=self.defaults["telemetry"]["enabled"],
            )
            if self.interactive
            else self.defaults["telemetry"]["enabled"]
        )

        if enable_telemetry:
            config["TELEMETRY_S3_ENDPOINT_URL"] = self.defaults["telemetry"][
                "endpoint_url"
            ]
            config["TELEMETRY_S3_REGION"] = self.defaults["telemetry"]["region"]
        else:
            config["TELEMETRY_S3_ENDPOINT_URL"] = ""
            config["TELEMETRY_S3_REGION"] = ""

        return config

    def generate_secrets(self) -> dict[str, str]:
        """Generate monitoring-related secrets."""
        return {}
