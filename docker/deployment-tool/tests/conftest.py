"""
Shared pytest configuration and fixtures for integration tests.
"""

import contextlib
import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def fixtures_dir():
    """Get the fixtures directory path."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def docker_templates_dir():
    """
    Get the path to actual production templates in docker/ directory.

    This allows tests to use real production templates instead of mocks.
    """
    return Path(__file__).parent.parent.parent.parent / "docker"


@pytest.fixture
def temp_deployment_dir():
    """
    Create a temporary directory for deployment output.

    This fixture is function-scoped and creates a new temp directory
    for each test, ensuring test isolation.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def log_file(temp_deployment_dir):
    """
    Create a log file path in the temp deployment directory.

    Returns the path to output.log that will be used by CLITestHarness.
    """
    return temp_deployment_dir / "output.log"


def normalize_output(output: str, temp_dir: Path) -> str:
    """
    Normalize output by replacing temporary directory paths with placeholder.

    Args:
        output: The output text to normalize
        temp_dir: The temporary directory path to replace

    Returns:
        Normalized output with {{OUTPUT_DIR}} placeholder
    """
    return output.replace(str(temp_dir), "{{OUTPUT_DIR}}")


def compare_output(log_file: Path, temp_dir: Path, fixture_name: str, fixture_manager):
    """
    Helper to read, normalize, and compare output against expected fixture.

    Args:
        log_file: Path to the log file to read
        temp_dir: Temporary directory for path normalization
        fixture_name: Name of the fixture to compare against
        fixture_manager: FixtureManager instance

    Returns:
        bool: True if output matches expected fixture
    """
    actual_output = normalize_output(log_file.read_text(), temp_dir)
    expected_output = fixture_manager.load_expected_output(fixture_name)
    return fixture_manager.compare_output(actual_output, expected_output, fixture_name=fixture_name)


def compare_generated_files(output_dir: Path, fixture_name: str, fixtures_dir: Path) -> bool:
    """
    Compare generated configuration files against expected fixtures.

    Args:
        output_dir: Directory containing generated files
        fixture_name: Name of the fixture scenario
        fixtures_dir: Base fixtures directory

    Returns:
        bool: True if all files match or if updating fixtures
    """
    import shutil

    from tests.fixtures import should_update_fixtures

    expected_dir = fixtures_dir / fixture_name / "expected"

    # If updating fixtures, copy generated files to expected directory
    if should_update_fixtures():
        if expected_dir.exists():
            shutil.rmtree(expected_dir)
        shutil.copytree(output_dir, expected_dir,
                       ignore=shutil.ignore_patterns('*.log', '__pycache__', '.avatar-templates'))
        print(f"\n✓ Updated expected files for: {fixture_name}")
        return True

    # Compare files
    if not expected_dir.exists():
        raise FileNotFoundError(f"Expected files not found: {expected_dir}")

    return _compare_directories(output_dir, expected_dir)


def _compare_directories(actual_dir: Path, expected_dir: Path) -> bool:
    """
    Recursively compare two directory trees.

    Args:
        actual_dir: Directory with actual generated files
        expected_dir: Directory with expected files

    Returns:
        bool: True if directories match
    """
    # Get all files relative to their respective roots
    actual_files = {p.relative_to(actual_dir) for p in actual_dir.rglob('*')
                    if p.is_file() and not p.name.endswith('.log')
                    and '.avatar-templates' not in str(p)}
    expected_files = {p.relative_to(expected_dir) for p in expected_dir.rglob('*') if p.is_file()}

    # Check for missing or extra files
    missing = expected_files - actual_files
    extra = actual_files - expected_files

    if missing or extra:
        if missing:
            print(f"\n❌ Missing files: {missing}")
        if extra:
            print(f"\n❌ Extra files: {extra}")
        return False

    # Compare file contents
    all_match = True
    for rel_path in actual_files:
        actual_file = actual_dir / rel_path
        expected_file = expected_dir / rel_path

        # For secrets files, only verify they exist and are not empty
        if '.secrets' in str(rel_path):
            actual_content = actual_file.read_text().strip()
            expected_content = expected_file.read_text().strip()

            if not actual_content:
                print(f"\n❌ Secret file is empty: {rel_path}")
                all_match = False
            elif not expected_content:
                print(f"\n❌ Expected secret file is empty: {rel_path}")
                all_match = False
            # Don't compare actual content since secrets are randomly generated
            continue

        actual_content = actual_file.read_text()
        expected_content = expected_file.read_text()

        if actual_content != expected_content:
            print(f"\n❌ File mismatch: {rel_path}")
            # Show diff for debugging
            import difflib
            diff = difflib.unified_diff(
                expected_content.splitlines(keepends=True),
                actual_content.splitlines(keepends=True),
                fromfile=str(expected_file),
                tofile=str(actual_file),
                lineterm=''
            )
            print(''.join(list(diff)[:50]))  # Show first 50 lines of diff
            all_match = False

    return all_match
