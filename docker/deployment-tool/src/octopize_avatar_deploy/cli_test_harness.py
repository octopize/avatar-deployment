#!/usr/bin/env python3
"""
CLI Test Harness for Avatar Deployment Tool

Allows testing the CLI with pre-configured responses instead of manual input.
This enables automated end-to-end testing of the entire CLI workflow.
"""

import os
import sys
from pathlib import Path

from octopize_avatar_deploy.configure import main
from octopize_avatar_deploy.input_gatherer import MockInputGatherer
from octopize_avatar_deploy.printer import FilePrinter, SilentPrinter


class CLITestHarness:
    """
    Test harness for running CLI with mocked input/output.

    This allows automated testing of the complete CLI workflow by:
    1. Injecting pre-configured responses via MockInputGatherer
    2. Optionally capturing output via SilentPrinter or FilePrinter
    3. Setting command-line arguments programmatically
    """

    def __init__(
        self,
        responses: list[str | bool],
        args: list[str] | None = None,
        silent: bool = False,
        log_file: Path | str | None = None,
    ):
        """
        Initialize CLI test harness.

        Args:
            responses: List of pre-configured responses for MockInputGatherer
            args: Command-line arguments to pass (default: [])
            silent: Whether to suppress output completely (default: False)
            log_file: Optional path to log file for capturing output
                     If provided, overrides silent=True
        """
        self.responses = responses
        self.args = args or []
        self.silent = silent
        self.log_file = log_file
        self._original_argv = None
        self._original_env: dict[str, str | None] = {}

    def __enter__(self):
        """Set up test environment."""
        # Save original argv
        self._original_argv = sys.argv.copy()

        # Set new argv (program name + args)
        sys.argv = ["octopize-avatar-deploy"] + self.args

        # Save and set environment variables
        env_vars = [
            "AVATAR_DEPLOY_TEST_MODE",
            "AVATAR_DEPLOY_TEST_RESPONSES",
            "AVATAR_DEPLOY_TEST_SILENT",
            "AVATAR_DEPLOY_TEST_LOG_FILE",
        ]
        for var in env_vars:
            self._original_env[var] = os.environ.get(var)

        os.environ["AVATAR_DEPLOY_TEST_MODE"] = "1"
        os.environ["AVATAR_DEPLOY_TEST_RESPONSES"] = self.serialize_responses(
            self.responses
        )

        if self.log_file:
            os.environ["AVATAR_DEPLOY_TEST_LOG_FILE"] = str(self.log_file)
        elif self.silent:
            os.environ["AVATAR_DEPLOY_TEST_SILENT"] = "1"

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Clean up test environment."""
        # Restore original argv
        sys.argv = self._original_argv

        # Restore environment
        for var, value in self._original_env.items():
            if value is not None:
                os.environ[var] = value
            else:
                os.environ.pop(var, None)

    def run(self) -> int:
        """
        Run the CLI with test configuration.

        Returns:
            Exit code (0 for success, non-zero for failure)
        """

        try:
            with self:
                main()
            return 0
        except SystemExit as e:
            # e.code can be int, str, or None
            if e.code is None:
                return 0
            if isinstance(e.code, int):
                return e.code
            # If it's a string or other type, return 1
            return 1
        except Exception as e:
            if not self.silent and not self.log_file:
                print(f"CLI test failed with exception: {e}", file=sys.stderr)
            return 1

    @staticmethod
    def serialize_responses(responses: list[str | bool]) -> str:
        """Serialize responses to string format."""
        serialized = []
        for r in responses:
            if isinstance(r, bool):
                serialized.append("__BOOL_TRUE__" if r else "__BOOL_FALSE__")
            else:
                # Escape delimiter
                serialized.append(str(r).replace("|||", "\\|||"))
        return "|||".join(serialized)

    @staticmethod
    def deserialize_responses(serialized: str) -> list[str | bool]:
        """Deserialize responses from string format."""
        if not serialized:
            return []

        responses: list[str | bool] = []
        for r in serialized.split("|||"):
            # Unescape delimiter
            r = r.replace("\\|||", "|||")

            # Convert bool markers back to bool
            if r == "__BOOL_TRUE__":
                responses.append(True)
            elif r == "__BOOL_FALSE__":
                responses.append(False)
            else:
                responses.append(r)
        return responses


def get_test_input_gatherer():
    """
    Get MockInputGatherer if in test mode, otherwise None.

    This function is called by configure.py to inject test responses.
    """
    if os.environ.get("AVATAR_DEPLOY_TEST_MODE") != "1":
        return None

    serialized = os.environ.get("AVATAR_DEPLOY_TEST_RESPONSES", "")
    responses = CLITestHarness.deserialize_responses(serialized)

    if not responses:
        return None

    return MockInputGatherer(responses)


def get_test_printer():
    """
    Get appropriate printer for test mode.

    Returns FilePrinter if log file specified, SilentPrinter if silent mode,
    otherwise None.
    """
    log_file = os.environ.get("AVATAR_DEPLOY_TEST_LOG_FILE")
    if log_file:
        return FilePrinter(log_file)

    if os.environ.get("AVATAR_DEPLOY_TEST_SILENT") == "1":
        return SilentPrinter()

    return None


# Convenience function for quick testing
def run_cli_test(
    responses: list[str | bool],
    args: list[str] | None = None,
    silent: bool = False,
    log_file: Path | str | None = None,
) -> int:
    """
    Convenience function to run a CLI test.

    Args:
        responses: Pre-configured responses
        args: Command-line arguments
        silent: Whether to suppress output completely
        log_file: Optional path to log file (overrides silent)

    Returns:
        Exit code (0 for success)

    Example:
        >>> # Test with file logging
        >>> exit_code = run_cli_test(
        ...     responses=["https://api.example.com", False, False],
        ...     args=["--output-dir", "/tmp/test"],
        ...     log_file="/tmp/test/deployment.log"
        ... )
        >>> # Check log file if test failed
        >>> if exit_code != 0:
        ...     with open("/tmp/test/deployment.log") as f:
        ...         print(f.read())
    """
    harness = CLITestHarness(responses, args, silent, log_file)
    return harness.run()
