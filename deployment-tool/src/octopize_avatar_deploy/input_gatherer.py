"""
Input gathering abstraction for deployment tool.

Provides pluggable input gathering through Protocol pattern, enabling:
- Standard console input for production
- Mock input for testing
- Rich library input with enhanced features
"""

import os
import sys
from collections.abc import Callable
from typing import Protocol, runtime_checkable

from rich.console import Console
from rich.prompt import Confirm, IntPrompt, Prompt


@runtime_checkable
class InputGatherer(Protocol):
    """
    Protocol defining input gathering interface.

    This allows different implementations (console, mock, rich) while
    maintaining type safety through Protocol pattern.
    """

    def prompt(
        self,
        message: str,
        default: str | None = None,
        validate: Callable[[str], tuple[bool, str]] | None = None,
        key: str | None = None,
    ) -> str:
        """
        Prompt user for input with optional default value and validation.

        Args:
            message: The prompt message
            default: Default value to use if user presses Enter (None = required field)
            validate: Optional validation function that returns (is_valid, error_message)
            key: Unique key for this prompt (e.g., "email.smtp_password") - used in testing

        Returns:
            User's input or default value
        """
        ...

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
        ...

    def prompt_choice(
        self, message: str, choices: list[str], default: str | None = None, key: str | None = None
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
        ...


class ConsoleInputGatherer:
    """
    Standard console-based input gatherer using built-in input().

    This is the default implementation for production use.
    """

    def prompt(
        self,
        message: str,
        default: str | None = None,
        validate: Callable[[str], tuple[bool, str]] | None = None,
        key: str | None = None,
    ) -> str:
        """Prompt user for input with optional default value and validation."""
        # Debug logging
        if os.environ.get("AVATAR_DEPLOY_DEBUG_PROMPTS") == "1":
            debug_msg = f"[PROMPT] {message}"
            if default is not None:
                debug_msg += f" (default: {default!r})"
            if key is not None:
                debug_msg += f" [key: {key}]"
            print(debug_msg, file=sys.stderr)

        while True:
            if default is not None:  # Has a default (including empty string)
                prompt_text = (
                    f"{message} [{default}]: " if default else f"{message} [press Enter to skip]: "
                )
                response = input(prompt_text).strip()
                value = response if response else default
            else:  # No default - required field
                response = input(f"{message}: ").strip()
                if not response:
                    print("  ⚠ This value is required")
                    continue
                value = response

            # Validate if validator provided
            if validate:
                is_valid, error_msg = validate(value)
                if not is_valid:
                    print(f"  ⚠ {error_msg}")
                    continue

            return value

    def prompt_yes_no(self, message: str, default: bool = True, key: str | None = None) -> bool:
        """Prompt user for yes/no input."""
        default_str = "Y/n" if default else "y/N"
        response = input(f"{message} [{default_str}]: ").strip().lower()

        if not response:
            return default

        return response in ["y", "yes", "true", "1"]

    def prompt_choice(
        self, message: str, choices: list[str], default: str | None = None, key: str | None = None
    ) -> str:
        """Prompt user to choose from list of options."""
        print(f"\n{message}")
        for i, choice in enumerate(choices, 1):
            marker = " (default)" if choice == default else ""
            print(f"  {i}. {choice}{marker}")

        while True:
            response = input(f"\nSelect [1-{len(choices)}]: ").strip()

            if not response and default:
                return default

            try:
                choice_num = int(response)
                if 1 <= choice_num <= len(choices):
                    return choices[choice_num - 1]
                else:
                    print(f"  ⚠ Please enter a number between 1 and {len(choices)}")
            except ValueError:
                print("  ⚠ Please enter a valid number")


class MockInputGatherer:
    """
    Mock input gatherer for testing.

    Returns pre-configured responses based on keys. Useful for testing
    interactive flows without manual input.
    """

    def __init__(self, responses: dict[str, str | bool]):
        """
        Initialize mock input gatherer.

        Args:
            responses: Dictionary mapping prompt keys to responses
                      e.g., {"email.smtp_password": "", "telemetry.enable_sentry": true}
        """
        self.responses = responses
        self.used_keys: set[str] = set()

    def _get_response(self, key: str | None, default: str | bool | None = None) -> str | bool:
        """Get response for the given key."""
        if key is None:
            raise ValueError(
                "MockInputGatherer requires a 'key' parameter for all prompts. "
                "Please update the prompt call to include a unique key."
            )

        if key in self.used_keys:
            raise ValueError(
                f"MockInputGatherer: Key '{key}' has already been used. "
                "Each key should only be prompted once per test run."
            )

        self.used_keys.add(key)

        if key not in self.responses:
            raise KeyError(
                f"MockInputGatherer: No response configured for key '{key}'. "
                f"Available keys: {sorted(self.responses.keys())}"
            )

        return self.responses[key]

    def prompt(
        self,
        message: str,
        default: str | None = None,
        validate: Callable[[str], tuple[bool, str]] | None = None,
        key: str | None = None,
    ) -> str:
        """Return mocked response for the given key."""
        # Debug logging with response preview
        if os.environ.get("AVATAR_DEPLOY_DEBUG_PROMPTS") == "1":
            response_preview = (
                self.responses.get(key, f"<default: {default!r}>") if key else "<no key>"
            )
            print(
                f"[PROMPT] {message} [key: {key}] => {response_preview!r}",
                file=sys.stderr,
            )

        response = self._get_response(key, default)

        if isinstance(response, bool):
            raise TypeError(
                f"Expected string response for key '{key}', got bool: {response}. "
                "Use prompt_yes_no() for boolean prompts."
            )

        # Use default if response is empty string and default is provided
        value = response if response else (default if default is not None else response)

        # Validate if validator provided (for testing validation logic)
        if validate:
            is_valid, error_msg = validate(value)
            if not is_valid:
                raise ValueError(f"MockInputGatherer: Validation failed for '{value}': {error_msg}")

        return value

    def prompt_yes_no(self, message: str, default: bool = True, key: str | None = None) -> bool:
        """Return mocked boolean response for the given key."""
        response = self._get_response(key, default)
        if isinstance(response, str):
            # Convert string to boolean if needed
            return response.lower() in ["y", "yes", "true", "1"]
        return response

    def prompt_choice(
        self, message: str, choices: list[str], default: str | None = None, key: str | None = None
    ) -> str:
        """Return mocked choice response for the given key."""
        response = self._get_response(key, default)
        if isinstance(response, bool):
            raise TypeError(
                f"Expected string response for key '{key}', got bool: {response}. "
                "Choices must be strings."
            )

        # If response is empty and default is provided, return default
        if not response and default:
            return default

        # If response is a number, treat it as choice index (1-based)
        try:
            choice_num = int(response)
            if 1 <= choice_num <= len(choices):
                return choices[choice_num - 1]
        except (ValueError, TypeError):
            pass

        # Otherwise, return the response as-is (assuming it's a valid choice)
        return response


class RichInputGatherer:
    """
    Rich-based input gatherer with enhanced prompts.

    Uses the 'rich' library to provide beautiful interactive prompts with:
    - Styled prompts with colors
    - Better formatting
    - Input validation
    """

    def __init__(self):
        """Initialize RichInputGatherer with a Console instance."""
        self.console = Console()

    def prompt(
        self,
        message: str,
        default: str | None = None,
        validate: Callable[[str], tuple[bool, str]] | None = None,
        key: str | None = None,
    ) -> str:
        """Prompt user for input with optional default value and validation."""
        while True:
            if default is not None:  # Has a default (including empty string)
                if default:
                    result = Prompt.ask(f"[cyan]{message}[/cyan]", default=default)
                else:
                    # Empty string default - show skip hint
                    result = Prompt.ask(f"[cyan]{message} (press Enter to skip)[/cyan]", default="")
            else:  # No default - required field
                # Rich Prompt requires at least empty string, so we loop
                result = ""
                while not result:
                    result = Prompt.ask(f"[cyan]{message}[/cyan]").strip()
                    if not result:
                        self.console.print("[yellow]⚠ This value is required[/yellow]")

            # Validate if validator provided
            if validate:
                is_valid, error_msg = validate(result)
                if not is_valid:
                    self.console.print(f"[yellow]⚠ {error_msg}[/yellow]")
                    continue

            return result

    def prompt_yes_no(self, message: str, default: bool = True, key: str | None = None) -> bool:
        """Prompt user for yes/no input."""
        return Confirm.ask(f"[cyan]{message}[/cyan]", default=default)

    def prompt_choice(
        self, message: str, choices: list[str], default: str | None = None, key: str | None = None
    ) -> str:
        """Prompt user to choose from list of options."""
        self.console.print(f"\n[cyan]{message}[/cyan]")
        for i, choice in enumerate(choices, 1):
            marker = " [dim](default)[/dim]" if choice == default else ""
            self.console.print(f"  [bold]{i}[/bold]. {choice}{marker}")

        # Determine default index
        default_index = None
        if default and default in choices:
            default_index = choices.index(default) + 1

        while True:
            if default_index:
                choice_num = IntPrompt.ask(
                    f"\n[cyan]Select[/cyan] [dim]\\[1-{len(choices)}][/dim]",
                    default=default_index,
                )
            else:
                choice_num = IntPrompt.ask(f"\n[cyan]Select[/cyan] [dim]\\[1-{len(choices)}][/dim]")

            if 1 <= choice_num <= len(choices):
                return choices[choice_num - 1]
            else:
                self.console.print(
                    f"[yellow]⚠ Please enter a number between 1 and {len(choices)}[/yellow]"
                )
