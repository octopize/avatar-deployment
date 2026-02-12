"""Local source configuration step for development mode."""

from pathlib import Path
from typing import Any

from octopize_avatar_deploy.deployment_mode import DeploymentMode

from .base import DeploymentStep, ValidationError, ValidationSuccess


class WebLocalSourceStep(DeploymentStep):
    """Handles local Web source directory configuration for development."""

    name = "web_local_source"
    description = "Configure Web source code directories for development"

    modes = [DeploymentMode.DEV]  # Only runs in dev mode

    def collect_config(self) -> dict[str, Any]:
        """Collect local source paths for development bind mounts."""
        config: dict[str, Any] = {}

        self.printer.print("\n--- Local Source Configuration ---")
        self.printer.print(
            "In dev mode, source code is bind-mounted for live reloading.\n"
            "Provide absolute paths to your local source directories."
        )

        # Web service source path
        web_source_default = self.get_default_value("local_source.web_source_path")

        web_source_path = self.get_config_or_prompt(
            "WEB_SOURCE_PATH",
            "Path to avatar-website source directory",
            web_source_default,
            prompt_key="local_source.web_source_path",
            validate=self._validate_directory_path,
        )

        # Validate the path exists
        if not Path(web_source_path).expanduser().exists():
            raise ValueError(
                f"Web source directory does not exist: {web_source_path}\n"
                f"Please ensure the path is correct and accessible."
            )

        config["WEB_SOURCE_PATH"] = web_source_path

        # NPM RC file path for build secrets
        npmrc_default = self.get_default_value("local_source.npmrc_path")

        npmrc_path = self.get_config_or_prompt(
            "NPMRC_PATH",
            "Path to .npmrc file (for private npm packages)",
            npmrc_default,
            prompt_key="local_source.npmrc_path",
            validate=self._validate_file_path,
        )

        # Validate the path exists
        if not Path(npmrc_path).expanduser().exists():
            raise ValueError(
                f"NPM RC file does not exist: {npmrc_path}\n"
                f"Please ensure the path is correct and accessible."
            )

        config["NPMRC_PATH"] = npmrc_path

        return config

    def generate_secrets(self) -> dict[str, str]:
        """No secrets generated for local source configuration."""
        return {}

    @staticmethod
    def _validate_directory_path(value: str) -> ValidationSuccess[str] | ValidationError:
        """Validate that a path is a directory and exists."""
        path = Path(value).expanduser()
        if not path.exists():
            return ValidationError(f"Directory does not exist: {value}")
        if not path.is_dir():
            return ValidationError(f"Path is not a directory: {value}")
        return ValidationSuccess(value)

    @staticmethod
    def _validate_file_path(value: str) -> ValidationSuccess[str] | ValidationError:
        """Validate that a path is a file and exists."""
        path = Path(value).expanduser()
        if not path.exists():
            return ValidationError(f"File does not exist: {value}")
        if not path.is_file():
            return ValidationError(f"Path is not a file: {value}")
        return ValidationSuccess(value)
