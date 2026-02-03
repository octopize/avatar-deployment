"""
Provide deployment templates from various sources.

This module handles obtaining necessary template files either from GitHub
or from a local directory (for testing).
"""

import shutil
import urllib.request
from abc import ABC, abstractmethod
from pathlib import Path

# GitHub raw content URL base
GITHUB_RAW_BASE = "https://raw.githubusercontent.com/octopize/avatar-deployment"
DEFAULT_BRANCH = "main"

# Hardcoded manifest of required files with source roots and categories.
# The configurator should stay opaque and rely on provider verification.
REQUIRED_FILE_MANIFEST: dict[str, dict[str, object]] = {
    "templates": {
        "category": "template",
        "files": [
            ".env.template",
            "nginx.conf.template",
            "docker-compose.yml",
            ".template-version",
            "authentik/octopize-avatar-blueprint.yaml.j2",
        ],
    },
    "docker": {
        "category": "docker",
        "files": [
            "authentik/custom-templates/email_account_confirmation.html",
            "authentik/custom-templates/email_account_exists.html",
            "authentik/custom-templates/email_account_invitation.html",
            "authentik/custom-templates/email_forgotten_password.html",
            "authentik/custom-templates/email_password_changed.html",
            "authentik/custom-templates/email_password_reset.html",
            "authentik/branding/favicon.ico",
            "authentik/branding/logo.png",
            "authentik/branding/background.png",
        ],
    },
}


def iter_required_files():
    """Iterate required files with source keys and category names."""
    for source_key, entry in REQUIRED_FILE_MANIFEST.items():
        category = str(entry["category"])
        for filename in entry["files"]:
            yield {
                "source_key": source_key,
                "category": category,
                "path": str(filename),
            }


def verify_required_files(output_dir: Path) -> tuple[bool, str | None, int]:
    """
    Verify all required files exist in output_dir.

    Returns:
        (is_valid, error_message, total_files)
    """
    output_dir = Path(output_dir)
    missing_by_category: dict[str, list[str]] = {}
    total_files = 0

    for entry in iter_required_files():
        total_files += 1
        destination = output_dir / entry["path"]
        if not destination.exists():
            missing_by_category.setdefault(entry["category"], []).append(entry["path"])

    if not missing_by_category:
        return True, None, total_files

    details = []
    for category, files in missing_by_category.items():
        details.append(f"{category}: {', '.join(files)}")

    message = "Missing required template files: " + "; ".join(details)
    return False, message, total_files


class TemplateProvider(ABC):
    """Abstract base class for template providers."""

    def __init__(self, verbose: bool = False):
        """
        Initialize template provider.

        Args:
            verbose: Print progress information
        """
        self.verbose = verbose

    @abstractmethod
    def provide_template_file(self, filename: str, destination: Path) -> bool:
        """
        Provide a single template file to the destination.

        Args:
            filename: Name of file to provide (from docker/templates/)
            destination: Local path where file should be saved

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def provide_docker_file(self, filename: str, destination: Path) -> bool:
        """
        Provide a single docker file to the destination.

        Args:
            filename: Name of file to provide (from docker/)
            destination: Local path where file should be saved

        Returns:
            True if successful, False otherwise
        """
        pass

    def provide_all(self, output_dir: Path) -> bool:
        """
        Provide all required template and docker files.

        Args:
            output_dir: Directory where files should be saved

        Returns:
            True if all files provided successfully
        """
        output_dir = Path(output_dir)
        success = True

        if self.verbose:
            print(f"\nProviding templates to {output_dir}/")
            print("=" * 60)

        for entry in iter_required_files():
            destination = output_dir / entry["path"]
            if entry["source_key"] == "templates":
                provided = self.provide_template_file(entry["path"], destination)
            elif entry["source_key"] == "docker":
                provided = self.provide_docker_file(entry["path"], destination)
            else:
                provided = False

            if not provided:
                success = False
                print(
                    f"⚠ Warning: Failed to provide {entry['path']} "
                    f"({entry['category']})"
                )

        if self.verbose:
            if success:
                print("\n✓ All templates provided successfully")
            else:
                print("\n⚠ Some templates failed")

        return success

    def check_cached_templates(self, output_dir: Path) -> bool:
        """
        Check if templates are already cached locally.

        Args:
            output_dir: Directory to check for cached templates

        Returns:
            True if all required files exist
        """
        output_dir = Path(output_dir)
        for entry in iter_required_files():
            if not (output_dir / entry["path"]).exists():
                return False
        return True


class GitHubTemplateProvider(TemplateProvider):
    """Downloads deployment templates from GitHub."""

    def __init__(self, branch: str = DEFAULT_BRANCH, verbose: bool = False):
        """
        Initialize GitHub template provider.

        Args:
            branch: Git branch to download from (default: main)
            verbose: Print download progress
        """
        super().__init__(verbose=verbose)
        self.branch = branch
        self.templates_base_url = f"{GITHUB_RAW_BASE}/{branch}/docker/templates"
        self.docker_base_url = f"{GITHUB_RAW_BASE}/{branch}/docker"

    def provide_template_file(self, filename: str, destination: Path) -> bool:
        """
        Download a single template file from GitHub.

        Args:
            filename: Name of file to download (in docker/templates/ directory)
            destination: Local path where file should be saved

        Returns:
            True if successful, False otherwise
        """
        url = f"{self.templates_base_url}/{filename}"

        if self.verbose:
            print(f"Downloading {filename}...")
            print(f"  URL: {url}")
            print(f"  Destination: {destination}")

        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                content = response.read()

            # Ensure parent directory exists
            destination.parent.mkdir(parents=True, exist_ok=True)

            # Write file
            destination.write_bytes(content)

            if self.verbose:
                print(f"  ✓ Downloaded {len(content)} bytes")

            return True

        except Exception as e:
            if self.verbose:
                print(f"  ✗ Failed: {e}")
            return False

    def provide_docker_file(self, filename: str, destination: Path) -> bool:
        """
        Download a single docker file from GitHub.

        Args:
            filename: Name of file to download (in docker/ directory)
            destination: Local path where file should be saved

        Returns:
            True if successful, False otherwise
        """
        url = f"{self.docker_base_url}/{filename}"

        if self.verbose:
            print(f"Downloading {filename}...")
            print(f"  URL: {url}")
            print(f"  Destination: {destination}")

        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                content = response.read()

            # Ensure parent directory exists
            destination.parent.mkdir(parents=True, exist_ok=True)

            # Write file
            destination.write_bytes(content)

            if self.verbose:
                print(f"  ✓ Downloaded {len(content)} bytes")

            return True

        except Exception as e:
            if self.verbose:
                print(f"  ✗ Failed: {e}")
            return False


class LocalTemplateProvider(TemplateProvider):
    """Provides templates from a local directory (for testing)."""

    def __init__(self, source_dir: Path | str, verbose: bool = False):
        """
        Initialize local template provider.

        Args:
            source_dir: Local directory containing template files (docker/templates/)
            verbose: Print progress information
        """
        super().__init__(verbose=verbose)
        self.source_dir = Path(source_dir)
        # Parent of templates is docker/
        self.docker_dir = self.source_dir.parent

    def provide_template_file(self, filename: str, destination: Path) -> bool:
        """
        Copy a single template file from source to destination.

        Args:
            filename: Name of file to copy (from docker/templates/)
            destination: Local path where file should be saved

        Returns:
            True if successful, False otherwise
        """
        source = self.source_dir / filename

        if self.verbose:
            print(f"Copying {filename}...")
            print(f"  Source: {source}")
            print(f"  Destination: {destination}")

        try:
            if not source.exists():
                raise FileNotFoundError(f"Source file not found: {source}")

            # Ensure parent directory exists
            destination.parent.mkdir(parents=True, exist_ok=True)

            # Copy file
            shutil.copy2(source, destination)

            if self.verbose:
                print(f"  ✓ Copied {source.stat().st_size} bytes")

            return True

        except Exception as e:
            if self.verbose:
                print(f"  ✗ Failed: {e}")
            return False

    def provide_docker_file(self, filename: str, destination: Path) -> bool:
        """
        Copy a single docker file from source to destination.

        Args:
            filename: Name of file to copy (from docker/)
            destination: Local path where file should be saved

        Returns:
            True if successful, False otherwise
        """
        source = self.docker_dir / filename

        if self.verbose:
            print(f"Copying {filename}...")
            print(f"  Source: {source}")
            print(f"  Destination: {destination}")

        try:
            if not source.exists():
                raise FileNotFoundError(f"Source file not found: {source}")

            # Ensure parent directory exists
            destination.parent.mkdir(parents=True, exist_ok=True)

            # Copy file
            shutil.copy2(source, destination)

            if self.verbose:
                print(f"  ✓ Copied {source.stat().st_size} bytes")

            return True

        except Exception as e:
            if self.verbose:
                print(f"  ✗ Failed: {e}")
            return False


def download_templates(
    output_dir: Path,
    force: bool = False,
    branch: str = DEFAULT_BRANCH,
    verbose: bool = False,
) -> bool:
    """
    Download deployment templates from GitHub.

    Args:
        output_dir: Directory where templates should be saved
        force: Force download even if files already exist
        branch: Git branch to download from
        verbose: Print progress information

    Returns:
        True if successful
    """
    provider = GitHubTemplateProvider(branch=branch, verbose=verbose)

    # Check if already cached
    if not force and provider.check_cached_templates(output_dir):
        if verbose:
            print(f"Templates already cached in {output_dir}/")
        return True

    # Download
    return provider.provide_all(output_dir)
