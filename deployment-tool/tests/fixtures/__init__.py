"""
Fixture utilities for integration testing.

Provides utilities for loading fixture files, comparing outputs,
and updating expected outputs when needed.
"""

import difflib
import os
from pathlib import Path
from typing import Any

import yaml


class FixtureManager:
    """Manages test fixtures including input responses and expected outputs."""

    def __init__(self, fixtures_dir: Path | str):
        """
        Initialize the fixture manager.

        Args:
            fixtures_dir: Path to the fixtures directory
        """
        self.fixtures_dir = Path(fixtures_dir)

    def load_input_fixture(self, name: str) -> list[str | bool]:
        """
        Load input fixture file containing test responses.

        Args:
            name: Name of the fixture (scenario subdirectory)

        Returns:
            List of responses (strings or booleans)

        Raises:
            FileNotFoundError: If fixture file doesn't exist
            ValueError: If fixture file is invalid
        """
        fixture_path = self.fixtures_dir / name / "input.yaml"

        if not fixture_path.exists():
            raise FileNotFoundError(f"Input fixture not found: {fixture_path}")

        with open(fixture_path) as f:
            data = yaml.safe_load(f)

        if not isinstance(data, dict) or "responses" not in data:
            raise ValueError(
                f"Invalid fixture format: {fixture_path}. Expected dict with 'responses' key"
            )

        return data["responses"]

    def get_config_fixture_path(self, name: str) -> Path | None:
        """
        Get path to config fixture file if it exists.

        Args:
            name: Name of the fixture (scenario subdirectory)

        Returns:
            Path to config.yaml, or None if it doesn't exist
        """
        fixture_path = self.fixtures_dir / name / "config.yaml"
        return fixture_path if fixture_path.exists() else None

    def load_expected_output(self, name: str) -> str:
        """
        Load expected output fixture file.

        Args:
            name: Name of the fixture (scenario subdirectory)

        Returns:
            Expected output as string

        Raises:
            FileNotFoundError: If fixture file doesn't exist and not updating fixtures
        """
        fixture_path = self.fixtures_dir / name / "output.txt"

        if not fixture_path.exists():
            if should_update_fixtures():
                # When updating fixtures, return empty string if file doesn't exist
                # It will be created during compare_output
                return ""
            raise FileNotFoundError(f"Output fixture not found: {fixture_path}")

        return fixture_path.read_text()

    def save_output(self, name: str, output: str) -> None:
        """
        Save output to fixture file (for updating expected outputs).

        Args:
            name: Name of the fixture (scenario subdirectory)
            output: Output content to save
        """
        fixture_path = self.fixtures_dir / name / "output.txt"
        fixture_path.parent.mkdir(parents=True, exist_ok=True)
        # Ensure trailing newline for pre-commit end-of-file-fixer
        content = output if output.endswith("\n") else output + "\n"
        fixture_path.write_text(content)

    def compare_output(
        self,
        actual: str,
        expected: str,
        context_lines: int = 3,
        fixture_name: str | None = None,
    ) -> bool:
        """
        Compare actual output with expected output.

        Args:
            actual: Actual output from test
            expected: Expected output from fixture
            context_lines: Number of context lines in diff (default: 3)
            fixture_name: Name of the fixture to save if updating (optional)

        Returns:
            bool: True if outputs match, False otherwise

        Note:
            If AVATAR_DEPLOY_UPDATE_FIXTURES is set and fixture_name is provided,
            this will save the actual output to the fixture file and return True.
        """
        # If updating fixtures and we have a name, save and pass
        if should_update_fixtures() and fixture_name:
            self.save_output(fixture_name, actual)
            print(f"\n✓ Updated fixture: {fixture_name}")
            return True

        actual_lines = actual.splitlines(keepends=True)
        expected_lines = expected.splitlines(keepends=True)

        if actual_lines == expected_lines:
            return True

        # Generate unified diff
        diff = difflib.unified_diff(
            expected_lines,
            actual_lines,
            fromfile="expected",
            tofile="actual",
            lineterm="",
            n=context_lines,
        )

        diff_str = "\n".join(diff)

        # Print diff for debugging
        print(f"\n❌ Output mismatch:\n{diff_str}")

        return False


def should_update_fixtures() -> bool:
    """
    Check if fixtures should be updated.

    Returns True if AVATAR_DEPLOY_UPDATE_FIXTURES environment variable is set.

    Usage:
        AVATAR_DEPLOY_UPDATE_FIXTURES=1 pytest tests/integration/
    """
    return os.environ.get("AVATAR_DEPLOY_UPDATE_FIXTURES", "").lower() in (
        "1",
        "true",
        "yes",
    )


def normalize_output(output: str) -> str:
    """
    Normalize output for comparison.

    Removes timing-specific or environment-specific variations that
    shouldn't cause test failures.

    Args:
        output: Raw output string

    Returns:
        Normalized output string
    """
    # Remove trailing whitespace from each line
    lines = [line.rstrip() for line in output.splitlines()]

    # Remove empty lines at the end
    while lines and not lines[-1]:
        lines.pop()

    return "\n".join(lines)
