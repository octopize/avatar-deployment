"""
Shared pytest configuration and fixtures for integration tests.
"""

import contextlib
import os
import tempfile
from pathlib import Path

import pytest

from octopize_avatar_deploy.download_templates import LocalTemplateProvider


@pytest.fixture(scope="session")
def fixtures_dir():
    """Get the fixtures directory path."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def docker_templates_dir():
    """
    Get the path to actual production templates in docker/templates/ directory.

    This allows tests to use real production templates instead of mocks.
    """
    return Path(__file__).parent.parent.parent / "docker" / "templates"


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


@pytest.fixture
def mock_docker_source(docker_templates_dir):
    """
    Create a temporary copy of the actual docker source directory structure.

    This fixture copies the real production templates from docker/templates/
    to a temporary location, allowing tests to use actual production templates
    while maintaining isolation. This ensures tests exercise the real template
    content and will catch issues with actual templates.

    Yields:
        Path: Path to copied docker/templates/ directory (suitable for LocalTemplateProvider)
    """
    import shutil

    with tempfile.TemporaryDirectory() as tmpdir:
        # Copy the entire docker directory structure to temp location
        real_docker_dir = docker_templates_dir.parent  # docker/templates/ -> docker/
        temp_docker_dir = Path(tmpdir) / "docker"

        # Copy the entire docker directory
        shutil.copytree(real_docker_dir, temp_docker_dir)

        # Yield the templates_dir which LocalTemplateProvider expects as source_dir
        yield temp_docker_dir / "templates"


@pytest.fixture
def temp_templates_dir(mock_docker_source):
    """
    Create a temporary templates directory provisioned with all required files.

    This fixture uses LocalTemplateProvider to copy all required template and
    docker files from mock_docker_source to a temporary location, ensuring
    tests use the same provisioning logic as production code.

    Yields:
        Path: Path to provisioned templates directory (flat structure with all files)
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        templates_dir = Path(tmpdir)

        # Use LocalTemplateProvider to provision all files
        provider = LocalTemplateProvider(source_dir=mock_docker_source, verbose=False)
        success = provider.provide_all(templates_dir)

        if not success:
            raise RuntimeError("Failed to provision test templates using LocalTemplateProvider")

        yield templates_dir


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
        shutil.copytree(
            output_dir,
            expected_dir,
            ignore=shutil.ignore_patterns("*.log", "__pycache__", ".avatar-templates"),
        )
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
    actual_files = {
        p.relative_to(actual_dir)
        for p in actual_dir.rglob("*")
        if p.is_file() and not p.name.endswith(".log") and ".avatar-templates" not in str(p)
    }
    expected_files = {p.relative_to(expected_dir) for p in expected_dir.rglob("*") if p.is_file()}

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

        # Skip binary files (images, etc.) - just verify they exist
        if rel_path.suffix in {".png", ".ico", ".jpg", ".jpeg", ".gif"}:
            continue

        # For secrets files, only verify they exist and are not empty
        if ".secrets" in str(rel_path):
            actual_content = actual_file.read_text().strip()
            expected_content = expected_file.read_text().strip()

            # Allow both to be empty (placeholder secrets like telemetry credentials)
            if not actual_content and not expected_content:
                continue
            # Fail if only one is empty
            elif not actual_content:
                print(f"\n❌ Secret file is empty: {rel_path}")
                all_match = False
            elif not expected_content:
                print(f"\n❌ Expected secret file is empty: {rel_path}")
                all_match = False
            # Don't compare actual content since secrets are randomly generated
            continue

        actual_content = actual_file.read_text()
        expected_content = expected_file.read_text()

        # Normalize random values in .deployment-state.yaml, deployment-config.yaml,
        # blueprint template, and .env file
        if rel_path.name in [
            ".deployment-state.yaml",
            "deployment-config.yaml",
            "octopize-avatar-blueprint.yaml",
            ".env",
        ]:
            import re

            def normalize_both(pattern: str, replacement: str) -> None:
                """Apply regex substitution to both actual and expected content."""
                nonlocal actual_content, expected_content
                actual_content = re.sub(pattern, replacement, actual_content)
                expected_content = re.sub(pattern, replacement, expected_content)

            # Normalize random OAuth2 client ID/secret patterns
            normalize_both(r"AVATAR_AUTHENTIK_BLUEPRINT_CLIENT_ID: [0-9a-f]+", "AVATAR_AUTHENTIK_BLUEPRINT_CLIENT_ID: RANDOM_ID")
            normalize_both(r"AVATAR_AUTHENTIK_BLUEPRINT_CLIENT_SECRET: [0-9a-f]+", "AVATAR_AUTHENTIK_BLUEPRINT_CLIENT_SECRET: RANDOM_SECRET")

            # Normalize 64-char hex client IDs/secrets in blueprint (OAuth provider)
            # Support both single and double quotes
            normalize_both(r"client_id: '[0-9a-f]{64}'", "client_id: 'RANDOM_CLIENT_ID'")
            normalize_both(r'client_id: "[0-9a-f]{64}"', 'client_id: "RANDOM_CLIENT_ID"')
            normalize_both(r"client_secret: '[0-9a-f]{64}'", "client_secret: 'RANDOM_CLIENT_SECRET'")
            normalize_both(r'client_secret: "[0-9a-f]{64}"', 'client_secret: "RANDOM_CLIENT_SECRET"')

            # Normalize 64-char hex in comments (blueprint template header)
            normalize_both(
                r"#   [0-9a-f]{64}             - OAuth2 Client ID",
                "#   RANDOM_CLIENT_ID             - OAuth2 Client ID",
            )
            normalize_both(
                r"#   [0-9a-f]{64}         - OAuth2 Client Secret",
                "#   RANDOM_CLIENT_SECRET         - OAuth2 Client Secret",
            )

            # Normalize SSO credentials in .env file
            normalize_both(r"SSO_CLIENT_ID=[0-9a-f]{64}", "SSO_CLIENT_ID=RANDOM_CLIENT_ID")
            normalize_both(r"SSO_CLIENT_SECRET=[0-9a-f]{64}", "SSO_CLIENT_SECRET=RANDOM_CLIENT_SECRET")

            # Normalize AVATAR_AUTHENTIK_BLUEPRINT_* credentials in .env file
            normalize_both(
                r"AVATAR_AUTHENTIK_BLUEPRINT_CLIENT_ID=[0-9a-f]{64}",
                "AVATAR_AUTHENTIK_BLUEPRINT_CLIENT_ID=RANDOM_CLIENT_ID",
            )
            normalize_both(
                r"AVATAR_AUTHENTIK_BLUEPRINT_CLIENT_SECRET=[0-9a-f]{64}",
                "AVATAR_AUTHENTIK_BLUEPRINT_CLIENT_SECRET=RANDOM_CLIENT_SECRET",
            )

            # Normalize Authentik bootstrap credentials (base64-urlsafe format: [A-Za-z0-9_-]{43})
            normalize_both(
                r"AUTHENTIK_BOOTSTRAP_PASSWORD=[A-Za-z0-9_-]{43}",
                "AUTHENTIK_BOOTSTRAP_PASSWORD=RANDOM_PASSWORD",
            )
            normalize_both(
                r"AUTHENTIK_BOOTSTRAP_PASSWORD: [A-Za-z0-9_-]{43}",
                "AUTHENTIK_BOOTSTRAP_PASSWORD: RANDOM_PASSWORD",
            )
            normalize_both(
                r"AUTHENTIK_BOOTSTRAP_TOKEN=[A-Za-z0-9_-]{43}",
                "AUTHENTIK_BOOTSTRAP_TOKEN=RANDOM_TOKEN",
            )
            normalize_both(
                r"AUTHENTIK_BOOTSTRAP_TOKEN: [A-Za-z0-9_-]{43}",
                "AUTHENTIK_BOOTSTRAP_TOKEN: RANDOM_TOKEN",
            )

        if actual_content != expected_content:
            print(f"\n❌ File mismatch: {rel_path}")
            # Show diff for debugging
            import difflib

            diff = difflib.unified_diff(
                expected_content.splitlines(keepends=True),
                actual_content.splitlines(keepends=True),
                fromfile=str(expected_file),
                tofile=str(actual_file),
                lineterm="",
            )
            print("".join(list(diff)[:50]))  # Show first 50 lines of diff
            all_match = False

    return all_match
