"""API local source configuration step for development mode."""

from pathlib import Path
from typing import Any

from octopize_avatar_deploy.deployment_mode import DeploymentMode

from .base import DeploymentStep, ValidationError, ValidationSuccess


class ApiLocalSourceStep(DeploymentStep):
    """Handles local API source directory configuration for development."""

    name = "api_local_source"
    description = "Configure API source code directories for development"

    modes = [DeploymentMode.DEV]  # Only runs in dev mode

    def collect_config(self) -> dict[str, Any]:
        """Collect local API source path and derive additional context paths."""
        config: dict[str, Any] = {}

        self.printer.print("\n--- API Local Source Configuration ---")
        self.printer.print(
            "In dev mode, API source code is bind-mounted for live reloading.\n"
            "Provide the absolute path to your API source directory.\n"
            "Additional contexts (avatar, core, dp) will be derived automatically."
        )

        # API service source path
        api_source_default = self.get_default_value("local_source.api_source_path")

        api_source_path = self.get_config_or_prompt(
            "API_SOURCE_PATH",
            "Path to avatar API source directory (e.g., /path/to/avatar/services/api)",
            api_source_default,
            prompt_key="local_source.api_source_path",
            validate=self._validate_directory_path,
        )

        # Validate the API path exists
        api_path = Path(api_source_path).expanduser()
        if not api_path.exists():
            raise ValueError(
                f"API source directory does not exist: {api_source_path}\n"
                f"Please ensure the path is correct and accessible."
            )

        if not api_path.is_dir():
            raise ValueError(
                f"API source path is not a directory: {api_source_path}\n"
                f"Please provide a valid directory path."
            )

        config["API_SOURCE_PATH"] = str(api_path)

        # Derive additional contexts from parent directory structure
        # Expected structure: /path/to/avatar_git_repo/services/api
        # Where avatar_git_repo contains: avatar/, core/, dp/, services/
        parent = api_path.parent  # services/
        parent_parent = parent.parent  # avatar_git_repo/

        avatar_context = parent_parent / "avatar"
        core_context = parent_parent / "core"
        dp_context = parent_parent / "dp"

        # Validate all additional contexts exist
        for context_name, context_path in [
            ("avatar", avatar_context),
            ("core", core_context),
            ("dp", dp_context),
        ]:
            if not context_path.exists():
                raise ValueError(
                    f"Required context directory '{context_name}' does not exist: {context_path}\n"
                    f"Expected to find it at: {context_path}\n"
                    f"Please ensure your API source path follows the monorepo structure:\n"
                    f"  <repo>/services/api (your API source)\n"
                    f"  <repo>/avatar (additional context)\n"
                    f"  <repo>/core (additional context)\n"
                    f"  <repo>/dp (additional context)"
                )

            if not context_path.is_dir():
                raise ValueError(
                    f"Context path '{context_name}' is not a directory: {context_path}"
                )

        config["API_CONTEXT_AVATAR"] = str(avatar_context)
        config["API_CONTEXT_CORE"] = str(core_context)
        config["API_CONTEXT_DP"] = str(dp_context)

        return config

    def generate_secrets(self) -> dict[str, str]:
        """No secrets generated for API local source configuration."""
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
