#!/usr/bin/env python3
"""
Pre-commit hook to verify version bumps when templates or scripts are modified.

This script ensures:
1. If templates in docker/templates/ are modified, .template-version must be bumped
2. If deployment-tool source code is modified, SCRIPT_VERSION must be bumped

Usage:
    python scripts/check-version-bump.py

Exit codes:
    0 - Success (version bumps are correct or not required)
    1 - Failure (version bump required but missing)
"""

import re
import subprocess
import sys
from pathlib import Path


def run_git_command(args: list[str]) -> str:
    """Run a git command and return the output."""
    try:
        result = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error running git command: {e}", file=sys.stderr)
        return ""


def get_staged_files() -> list[str]:
    """Get list of staged files."""
    output = run_git_command(["diff", "--cached", "--name-only", "--diff-filter=ACM"])
    if not output:
        return []
    return output.split("\n")


def get_file_diff(filepath: str) -> str:
    """Get the diff for a specific file."""
    return run_git_command(["diff", "--cached", filepath])


def extract_version_from_file(filepath: Path) -> str | None:
    """Extract version from a file."""
    if not filepath.exists():
        return None

    content = filepath.read_text()

    # For .template-version files (first line is the version)
    if filepath.name == ".template-version":
        lines = content.strip().split("\n")
        if lines:
            return lines[0].strip()

    # For Python files with SCRIPT_VERSION
    match = re.search(r'SCRIPT_VERSION\s*=\s*["\']([^"\']+)["\']', content)
    if match:
        return match.group(1)

    return None


def is_version_changed(filepath: Path, diff: str) -> bool:
    """Check if the version in a file has changed in the diff."""
    # Look for version changes in the diff
    if filepath.name == ".template-version":
        # Check if the first line changed
        for line in diff.split("\n"):
            if line.startswith("+") and not line.startswith("+++"):
                # Check if it looks like a version number
                version_match = re.match(r'\+(\d+\.\d+\.\d+)', line)
                if version_match:
                    return True
    else:
        # For Python files, look for SCRIPT_VERSION changes
        for line in diff.split("\n"):
            if line.startswith("+") and "SCRIPT_VERSION" in line:
                return True

    return False


def check_template_version_bump(staged_files: list[str]) -> tuple[bool, str | None]:
    """
    Check if template version needs to be bumped.

    Returns:
        (needs_bump, error_message)
    """
    template_files = [
        f for f in staged_files
        if f.startswith("docker/templates/") and not f.endswith(".template-version")
    ]

    if not template_files:
        return True, None

    version_file = Path("docker/templates/.template-version")
    version_file_in_staged = "docker/templates/.template-version" in staged_files

    if not version_file_in_staged:
        return False, (
            f"Template files modified but .template-version not updated:\n"
            f"  Modified: {', '.join(template_files)}\n"
            f"  Please bump the version in docker/templates/.template-version"
        )

    # Check if the version was actually changed
    diff = get_file_diff("docker/templates/.template-version")
    if not is_version_changed(version_file, diff):
        return False, (
            f"Template files modified but .template-version not bumped:\n"
            f"  Modified: {', '.join(template_files)}\n"
            f"  Please increment the version in docker/templates/.template-version"
        )

    return True, None


def check_script_version_bump(staged_files: list[str]) -> tuple[bool, str | None]:
    """
    Check if script version needs to be bumped.

    Returns:
        (needs_bump, error_message)
    """
    script_files = [
        f for f in staged_files
        if f.startswith("docker/deployment-tool/src/")
        and f.endswith(".py")
        and "version_compat.py" not in f
        and "__pycache__" not in f
    ]

    if not script_files:
        return True, None

    version_file = Path("docker/deployment-tool/src/octopize_avatar_deploy/version_compat.py")
    version_file_path = str(version_file)

    if version_file_path not in staged_files:
        return False, (
            f"Deployment tool source modified but SCRIPT_VERSION not updated:\n"
            f"  Modified: {', '.join(script_files)}\n"
            f"  Please bump SCRIPT_VERSION in {version_file}"
        )

    # Check if SCRIPT_VERSION was actually changed
    diff = get_file_diff(version_file_path)
    if not is_version_changed(version_file, diff):
        return False, (
            f"Deployment tool source modified but SCRIPT_VERSION not bumped:\n"
            f"  Modified: {', '.join(script_files)}\n"
            f"  Please increment SCRIPT_VERSION in {version_file}"
        )

    return True, None


def main() -> int:
    """Main function."""
    # Get staged files
    staged_files = get_staged_files()

    if not staged_files:
        print("No staged files to check")
        return 0

    errors = []

    # Check template version
    template_ok, template_error = check_template_version_bump(staged_files)
    if not template_ok and template_error:
        errors.append(template_error)

    # Check script version
    script_ok, script_error = check_script_version_bump(staged_files)
    if not script_ok and script_error:
        errors.append(script_error)

    if errors:
        print("\n❌ Version bump check failed!\n", file=sys.stderr)
        for error in errors:
            print(error, file=sys.stderr)
            print("", file=sys.stderr)
        return 1

    print("✓ Version bump check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
