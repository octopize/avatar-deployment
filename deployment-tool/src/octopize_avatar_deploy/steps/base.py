"""
Base class for deployment configuration steps.

Each step is a modular component that handles configuration and secrets
for a specific part of the deployment (email, telemetry, storage, etc.).
"""

import base64
import secrets
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

from octopize_avatar_deploy.deployment_mode import DeploymentMode

if TYPE_CHECKING:
    from octopize_avatar_deploy.input_gatherer import InputGatherer
    from octopize_avatar_deploy.printer import Printer
from octopize_avatar_deploy.input_gatherer import ConsoleInputGatherer
from octopize_avatar_deploy.printer import ConsolePrinter

_DEFAULT_VALUE_SENTINEL = (
    object()
)  # Sentinel for distinguishing between None and no default provided

# Generic type for config values
T = TypeVar("T")

# Type alias for new-style validators
Validator = Callable[[str], "ValidationSuccess[Any] | ValidationError"]
TemplateRenderer = Callable[[str, str], None]


@dataclass(frozen=True)
class DefaultKey:
    """
    Wrapper to distinguish a defaults.yaml lookup key from a literal value.

    Usage:
        # Inline literal value
        self.get_config("DB_NAME", "authentik")

        # Lookup in defaults.yaml
        self.get_config("DB_NAME", DefaultKey("database.name"))
    """

    key: str


@dataclass
class ValidationError:
    """Represents a validation error with a message."""

    message: str


@dataclass
class ValidationSuccess[T]:
    """Represents a successful validation with a typed value."""

    value: T


# Type alias for validation results
ValidationResult = ValidationSuccess[T] | ValidationError


# Standard parser/validator functions


def parse_bool(value: Any) -> ValidationResult[bool]:
    """
    Parse and validate a boolean value from various input types.

    Accepts: bool, str ("true"/"false"/"yes"/"no"/"1"/"0"), int (0/1)

    Returns:
        ValidationSuccess with bool value or ValidationError
    """
    if isinstance(value, bool):
        return ValidationSuccess(value)
    if isinstance(value, str):
        lower = value.lower().strip()
        if lower in ("true", "yes", "1", "on", "enabled"):
            return ValidationSuccess(True)
        if lower in ("false", "no", "0", "off", "disabled"):
            return ValidationSuccess(False)
    if isinstance(value, int):
        if value in (0, 1):
            return ValidationSuccess(bool(value))
    return ValidationError(f"Cannot parse as boolean: {value}")


def parse_int(value: Any) -> ValidationResult[int]:
    """
    Parse and validate an integer value.

    Returns:
        ValidationSuccess with int value or ValidationError
    """
    if isinstance(value, int):
        return ValidationSuccess(value)
    if isinstance(value, str):
        try:
            return ValidationSuccess(int(value.strip()))
        except ValueError:
            return ValidationError(f"Cannot parse as integer: {value}")
    return ValidationError(f"Cannot parse as integer: {value}")


def parse_str(value: Any) -> ValidationResult[str]:
    """
    Parse and validate a string value (converts to string).

    Returns:
        ValidationSuccess with str value
    """
    return ValidationSuccess(str(value))


def make_path_validator(
    must_exist: bool = True, must_be_dir: bool = False, must_be_file: bool = False
) -> Callable[[Any], ValidationResult[str]]:
    """
    Create a path validator with specific requirements.

    Args:
        must_exist: If True, path must exist
        must_be_dir: If True, path must be a directory
        must_be_file: If True, path must be a file

    Returns:
        Validator function that returns ValidationResult[str]
    """

    def validate_path(value: Any) -> ValidationResult[str]:
        path_str = str(value)
        path = Path(path_str).expanduser()

        if must_exist and not path.exists():
            return ValidationError(f"Path does not exist: {path_str}")
        if must_be_dir and path.exists() and not path.is_dir():
            return ValidationError(f"Path is not a directory: {path_str}")
        if must_be_file and path.exists() and not path.is_file():
            return ValidationError(f"Path is not a file: {path_str}")

        return ValidationSuccess(path_str)

    return validate_path


@dataclass
class PromptConfig[T]:
    """
    Configuration for prompting user input with type safety.

    This encapsulates all parameters needed to get a config value from:
    1. Pre-loaded config (highest priority)
    2. Interactive user prompt (if interactive mode)
    3. Default value (if non-interactive)

    Type Parameters:
        T: The expected type of the configuration value

    Attributes:
        config_key: Key to look up in self.config (e.g., "SMTP_HOST")
        prompt_message: Message to show when prompting user
        default_value: Default value to use (shown in prompt and used in non-interactive mode)
        prompt_key: Optional key for prompt (e.g., "email.smtp_host") - used in testing
        prompt_function: Function to use for prompting (prompt, prompt_yes_no, prompt_choice)
        parse_and_validate: Optional function to parse/validate value and return typed result

    Examples:
        >>> # Simple string prompt
        >>> config = PromptConfig(
        ...     config_key="SMTP_HOST",
        ...     prompt_message="SMTP host",
        ...     default_value="smtp.example.com",
        ...     prompt_key="email.smtp_host",
        ... )
        >>>
        >>> # Boolean prompt with custom validation
        >>> config = PromptConfig(
        ...     config_key="NGINX_TLS_ENABLED",
        ...     prompt_message="Enable TLS for Nginx?",
        ...     default_value=True,
        ...     prompt_key="nginx_tls.enabled",
        ...     prompt_function=lambda msg, default, key: (
        ...         step.prompt_yes_no(msg, default, key)
        ...     ),
        ...     parse_and_validate=parse_bool,
        ... )
    """

    config_key: str
    prompt_message: str
    default_value: T
    prompt_key: str | None = None
    prompt_function: Callable[..., Any] | None = None
    parse_and_validate: Callable[[Any], ValidationResult[T]] | None = None


class DeploymentStep(ABC):
    """
    Base class for all deployment configuration steps.

    Each step handles a specific aspect of the deployment configuration.
    Subclasses should implement collect_config() and generate_secrets().

    Class Variables:
        modes: List of deployment modes this step should run in.
               Default is [DeploymentMode.PRODUCTION, DeploymentMode.DEV] (runs in all modes).
               Override to limit step to specific modes (e.g., modes = [DeploymentMode.DEV]).
    """

    # Step metadata
    name: str = "base_step"
    description: str = "Base configuration step"
    required: bool = True  # Whether this step is required
    modes: list[DeploymentMode] = [
        DeploymentMode.PRODUCTION,
        DeploymentMode.DEV,
    ]  # Deployment modes this step runs in

    def __init__(
        self,
        output_dir: Path,
        defaults: dict[str, Any],
        config: dict[str, Any] | None = None,
        interactive: bool = True,
        printer: "Printer | None" = None,
        input_gatherer: "InputGatherer | None" = None,
    ) -> None:
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
        # Use the provided config dict directly (by reference) so all steps share the same dict
        # This allows steps to access config values set by previous steps
        if config is None:
            config = {}
        self.config: dict[str, Any] = config
        self.secrets: dict[str, str] = {}
        self.interactive = interactive

        # Import here to avoid circular dependency
        if printer is None:
            printer = ConsolePrinter()

        self.printer: Printer = printer

        if input_gatherer is None:
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

    def after_config_generation(self, render_template: TemplateRenderer) -> None:
        """
        Run optional follow-up work after the main configuration files are generated.

        Steps should keep ``collect_config()`` focused on gathering values. Side effects
        such as rendering additional files belong here.

        Args:
            render_template: Callback for rendering a template to an output path.
        """
        return None

    # Helper methods for prompting user input

    def prompt(
        self,
        message: str,
        default: str | None = None,
        validate: "Validator | None" = None,
        key: str | None = None,
    ) -> str:
        """
        Prompt user for input with optional default value and validation.

        Args:
            message: The prompt message
            default: Default value to use if user presses Enter (None = required field)
            validate: Optional validation function that returns ValidationSuccess | ValidationError
            key: Unique key for this prompt (e.g., "email.smtp_password") - used in testing

        Returns:
            User's input or default value
        """
        return self.input_gatherer.prompt(message, default, validate, key)

    def prompt_yes_no(self, message: str, default: bool = True, key: str | None = None) -> bool:
        """
        Prompt user for yes/no input.

        Args:
            message: The prompt message
            default: Default value if user presses Enter
            key: Unique key for this prompt (e.g., "telemetry.enable_sentry") - used in testing

        Returns:
            True for yes, False for no
        """
        return self.input_gatherer.prompt_yes_no(message, default, key)

    def prompt_choice(
        self, message: str, choices: list, default: str | None = None, key: str | None = None
    ) -> str:
        """
        Prompt user to choose from list of options.

        Args:
            message: The prompt message
            choices: List of valid choices
            default: Default choice if user presses Enter
            key: Unique key for this prompt (e.g., "email.mail_provider") - used in testing

        Returns:
            Selected choice
        """
        return self.input_gatherer.prompt_choice(message, choices, default, key)

    def get_config(self, config_key: str, default: Any | DefaultKey) -> Any:
        """
        Get value from config, or use default (either literal or from defaults.yaml).

        Supports both inline defaults and defaults.yaml lookups via DefaultKey wrapper.

        Args:
            config_key: Key to look up in self.config (e.g., "SMTP_USE_TLS")
            default_value: Either a literal value or DefaultKey("path.to.default")

        Returns:
            Value from config or the resolved default

        Examples:
            >>> # Inline literal default
            >>> db_name = self.get_config("DB_NAME", "authentik")

            >>> # Lookup in defaults.yaml
            >>> use_tls = self.get_config(
            ...     "SMTP_USE_TLS", DefaultKey("email.smtp.use_tls")
            ... )
        """
        if config_key in self.config:
            return self.config[config_key]

        # Resolve default value
        if isinstance(default, DefaultKey):
            return self.get_default_value(default.key)
        return default

    def get_default_value(self, key: str, default: Any = _DEFAULT_VALUE_SENTINEL) -> Any:
        """Get the value defined in the defaults (possible nested), with a fallback default.

        Args:
            key: Dot-separated key to look up in defaults (e.g., "email.smtp_password")
            default: Fallback default value if not found in defaults

        Returns:
            Value from defaults or the provided fallback default

        Raises:
            ValueError: If the key is not found in defaults and no fallback default is provided
        """

        keys = key.split(".")
        value = self.defaults.copy()
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                if default is _DEFAULT_VALUE_SENTINEL:
                    raise ValueError(f"Default value for key '{key}' not found in defaults.")
                return default
        return value

    def get_config_or_prompt_generic(self, config: PromptConfig[T]) -> T:
        """
        Generic method to get config value with type-safe parsing and validation.

        This unified method handles all prompt patterns:
        1. Check if value exists in pre-loaded config
        2. If interactive, prompt user with appropriate prompt function
        3. If non-interactive, use default value
        4. Parse and validate the value if parser provided

        Args:
            config: PromptConfig dataclass with all configuration parameters

        Returns:
            Typed configuration value

        Raises:
            ValueError: If validation fails

        Examples:
            >>> # Simple string prompt
            >>> smtp_host = step.get_config_or_prompt_generic(
            ...     PromptConfig(
            ...         config_key="SMTP_HOST",
            ...         prompt_message="SMTP host",
            ...         default_value="smtp.example.com",
            ...         prompt_key="email.smtp_host",
            ...     )
            ... )
            >>>
            >>> # Boolean prompt with validation
            >>> tls_enabled = step.get_config_or_prompt_generic(
            ...     PromptConfig(
            ...         config_key="NGINX_TLS_ENABLED",
            ...         prompt_message="Enable TLS?",
            ...         default_value=True,
            ...         prompt_key="nginx_tls.enabled",
            ...         prompt_function=lambda msg, default, key: (
            ...             step.prompt_yes_no(msg, default, key)
            ...         ),
            ...         parse_and_validate=parse_bool,
            ...     )
            ... )
        """
        # Step 1: Check if already in config
        if config.config_key in self.config:
            value = self.config[config.config_key]
            # Parse and validate if parser provided
            if config.parse_and_validate:
                result = config.parse_and_validate(value)
                if isinstance(result, ValidationError):
                    raise ValueError(
                        f"Invalid config value for '{config.config_key}': {result.message}"
                    )
                return result.value
            return value

        # Step 2: If interactive, prompt user
        if self.interactive:
            # Use provided prompt function or default to self.prompt
            if config.prompt_function is None:
                # Capture the parsed value to avoid parsing twice
                parsed_value: Any = None

                if config.parse_and_validate:
                    # Capture validator in closure
                    validator = config.parse_and_validate

                    def new_style_validator(value: str) -> ValidationSuccess[Any] | ValidationError:
                        nonlocal parsed_value
                        result = validator(value)
                        if isinstance(result, ValidationError):
                            return result
                        # Capture the parsed value so we don't need to parse again
                        parsed_value = result.value
                        return result

                    # Pass new-style validator directly to prompt
                    self.prompt(
                        config.prompt_message,
                        str(config.default_value),
                        key=config.prompt_key,
                        validate=new_style_validator,
                    )
                    # Return the already-parsed value from validation
                    return parsed_value  # type: ignore[return-value]
                else:
                    # No validator, return raw value from prompt
                    raw_value = self.prompt(
                        config.prompt_message,
                        str(config.default_value),
                        key=config.prompt_key,
                        validate=None,
                    )
                    return raw_value  # type: ignore[return-value]
            else:
                value = config.prompt_function(
                    config.prompt_message, config.default_value, config.prompt_key
                )
                # For custom prompt functions, we still need to parse
                if config.parse_and_validate:
                    result = config.parse_and_validate(value)
                    if isinstance(result, ValidationError):
                        raise ValueError(f"Invalid value after prompt: {result.message}")
                    return result.value
                return value

        # Step 3: Non-interactive, use default
        default = config.default_value
        # Parse and validate default if parser provided
        if config.parse_and_validate:
            result = config.parse_and_validate(default)
            if isinstance(result, ValidationError):
                raise ValueError(
                    f"Invalid default value for '{config.config_key}': {result.message}"
                )
            return result.value
        return default

    def get_config_or_prompt(
        self,
        config_key: str,
        prompt_message: str,
        default_value: Any | DefaultKey,
        prompt_key: str | None = None,
        parse_and_validate: "Callable[[Any], ValidationResult[Any]] | None" = None,
        validate: "Validator | None" = None,  # Deprecated: use parse_and_validate
    ) -> Any:
        """
        Get value from config, or prompt user if interactive, or use default if non-interactive.

        Supports both inline defaults and defaults.yaml lookups via DefaultKey wrapper.

        Args:
            config_key: Key to look up in self.config (e.g., "SMTP_HOST")
            prompt_message: Message to show when prompting user
            default_value: Default value - either literal or DefaultKey("path.in.defaults")
            prompt_key: Optional key for prompt (e.g., "email.smtp_host") - used in testing
            parse_and_validate: Optional validator (parse_str, parse_int, custom validator, etc.)
            validate: Deprecated alias for parse_and_validate (for backwards compatibility)

        Returns:
            Value from config, user input, or resolved default value

        Examples:
            >>> # Inline literal default
            >>> smtp_host = self.get_config_or_prompt(
            ...     "SMTP_HOST",
            ...     "SMTP host",
            ...     "smtp.example.com",
            ...     prompt_key="email.smtp_host"
            ... )

            >>> # Lookup in defaults.yaml with type conversion
            >>> smtp_port = self.get_config_or_prompt(
            ...     "SMTP_PORT",
            ...     "SMTP port",
            ...     DefaultKey("email.smtp.port"),
            ...     prompt_key="email.smtp_port",
            ...     parse_and_validate=parse_str
            ... )
        """
        # Resolve default value if it's a DefaultKey
        resolved_default = (
            self.get_default_value(default_value.key)
            if isinstance(default_value, DefaultKey)
            else default_value
        )

        # Use the provided validator (now all validators are new-style)
        validator = parse_and_validate if parse_and_validate is not None else validate

        return self.get_config_or_prompt_generic(
            PromptConfig(
                config_key=config_key,
                prompt_message=prompt_message,
                default_value=resolved_default,
                prompt_key=prompt_key,
                parse_and_validate=validator,
            )
        )

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
