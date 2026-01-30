"""
Base class for deployment configuration steps.

Each step is a modular component that handles configuration and secrets
for a specific part of the deployment (email, telemetry, storage, etc.).
"""

import base64
import secrets
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from octopize_avatar_deploy.input_gatherer import InputGatherer
    from octopize_avatar_deploy.printer import Printer


class DeploymentStep(ABC):
    """
    Base class for all deployment configuration steps.

    Each step handles a specific aspect of the deployment configuration.
    Subclasses should implement collect_config() and generate_secrets().
    """

    # Step metadata
    name: str = "base_step"
    description: str = "Base configuration step"
    required: bool = True  # Whether this step is required

    def __init__(
        self,
        output_dir: Path,
        defaults: dict[str, Any],
        config: dict[str, Any] | None = None,
        interactive: bool = True,
        printer: "Printer | None" = None,
        input_gatherer: "InputGatherer | None" = None,
    ):
        """
        Initialize the step.

        Args:
            output_dir: Directory where files will be generated
            defaults: Default configuration from defaults.yaml
            config: Pre-loaded configuration (for non-interactive mode)
            interactive: Whether to prompt user interactively
            printer: Optional printer for output
        """
        self.output_dir = Path(output_dir)
        self.defaults = defaults
        self.config: dict[str, Any] = config or {}
        self.secrets: dict[str, str] = {}
        self.interactive = interactive

        # Import here to avoid circular dependency
        if printer is None:
            from octopize_avatar_deploy.printer import ConsolePrinter

            printer = ConsolePrinter()

        self.printer: Printer = printer

        if input_gatherer is None:
            from octopize_avatar_deploy.input_gatherer import ConsoleInputGatherer

            input_gatherer = ConsoleInputGatherer()

        self.input_gatherer: InputGatherer = input_gatherer

    @abstractmethod
    def collect_config(self) -> dict[str, Any]:
        """
        Collect configuration for this step.

        Returns:
            dictionary of configuration values
        """
        pass

    @abstractmethod
    def generate_secrets(self) -> dict[str, str]:
        """
        Generate secrets for this step.

        Returns:
            dictionary of {filename: secret_value} for .secrets/ directory
        """
        pass

    def can_skip(self) -> bool:
        """
        Determine if this step can be skipped.

        Returns:
            True if step can be skipped (optional and user chooses to skip)
        """
        return False

    def validate(self) -> bool:
        """
        Validate configuration before proceeding.

        Returns:
            True if validation passes

        Raises:
            ValueError: If validation fails
        """
        return True

    def get_summary(self) -> str:
        """
        Get a summary of the configuration for review.

        Returns:
            Human-readable summary string
        """
        return f"{self.name}: Configured"

    # Helper methods for prompting user input

    def prompt(self, message: str, default: str = "") -> str:
        """
        Prompt user for input with optional default value.

        Args:
            message: The prompt message
            default: Default value to use if user presses Enter

        Returns:
            User's input or default value
        """
        return self.input_gatherer.prompt(message, default)

    def prompt_yes_no(self, message: str, default: bool = True) -> bool:
        """
        Prompt user for yes/no input.

        Args:
            message: The prompt message
            default: Default value if user presses Enter

        Returns:
            True for yes, False for no
        """
        return self.input_gatherer.prompt_yes_no(message, default)

    def prompt_choice(
        self, message: str, choices: list, default: str | None = None
    ) -> str:
        """
        Prompt user to choose from list of options.

        Args:
            message: The prompt message
            choices: List of valid choices
            default: Default choice if user presses Enter

        Returns:
            Selected choice
        """
        return self.input_gatherer.prompt_choice(message, choices, default)


    def get_config_value(self, key: str, default: Any = None) -> Any:
        ret =  self.config.get(key, default)
        if ret is None:
            raise ValueError(f"Configuration key '{key}' is required but not set.")
        return ret

    # Utility methods for generating secrets

    @staticmethod
    def generate_secret_token() -> str:
        """Generate a secure random token (hex-encoded)."""
        return secrets.token_hex()

    @staticmethod
    def generate_secret_urlsafe(nbytes: int = 32) -> str:
        """Generate a URL-safe random token."""
        return secrets.token_urlsafe(nbytes)

    @staticmethod
    def generate_encryption_key() -> str:
        """Generate a URL-safe base64-encoded encryption key."""
        return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("utf-8")

    @staticmethod
    def generate_base64_key(nbytes: int = 32) -> str:
        """Generate a base64-encoded random key."""
        return base64.b64encode(secrets.token_bytes(nbytes)).decode("utf-8")
