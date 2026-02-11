"""Local source configuration step for development mode."""

from pathlib import Path
from typing import Any

from octopize_avatar_deploy.deployment_mode import DeploymentMode

from .base import DeploymentStep


class LocalSourceStep(DeploymentStep):
    """Handles local source directory configuration for development."""

    name = "local_source"
    description = "Configure local source code directories for development"

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

        web_source_path = self.config.get(
            "WEB_SOURCE_PATH",
            self.prompt(
                "Path to avatar-website source directory",
                default=web_source_default,
                validate=self._validate_directory_path,
                key="local_source.web_source_path",
            )
            if self.interactive
            else web_source_default,
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

        npmrc_path = self.config.get(
            "NPMRC_PATH",
            self.prompt(
                "Path to .npmrc file (for private npm packages)",
                default=npmrc_default,
                validate=self._validate_file_path,
                key="local_source.npmrc_path",
            )
            if self.interactive
            else npmrc_default,
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
    def _validate_directory_path(value: str) -> tuple[bool, str]:
        """Validate that a path is a directory and exists."""
        path = Path(value).expanduser()
        if not path.exists():
            return False, f"Directory does not exist: {value}"
        if not path.is_dir():
            return False, f"Path is not a directory: {value}"
        return True, ""

    @staticmethod
    def _validate_file_path(value: str) -> tuple[bool, str]:
        """Validate that a path is a file and exists."""
        path = Path(value).expanduser()
        if not path.exists():
            return False, f"File does not exist: {value}"
        if not path.is_file():
            return False, f"Path is not a file: {value}"
        return True, ""
