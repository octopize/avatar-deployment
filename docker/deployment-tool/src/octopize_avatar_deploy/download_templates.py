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

# Files to download from the docker/ directory
REQUIRED_FILES = [
    ".env.template",
    "nginx.conf.template",
    "docker-compose.yml",
]


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
    def provide_file(self, filename: str, destination: Path) -> bool:
        """
        Provide a single file to the destination.

        Args:
            filename: Name of file to provide
            destination: Local path where file should be saved

        Returns:
            True if successful, False otherwise
        """
        pass

    def provide_all(self, output_dir: Path) -> bool:
        """
        Provide all required template files.

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

        for filename in REQUIRED_FILES:
            destination = output_dir / filename
            if not self.provide_file(filename, destination):
                success = False
                print(f"⚠ Warning: Failed to provide {filename}")

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
        for filename in REQUIRED_FILES:
            if not (output_dir / filename).exists():
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
        self.base_url = f"{GITHUB_RAW_BASE}/{branch}/docker"

    def provide_file(self, filename: str, destination: Path) -> bool:
        """
        Download a single file from GitHub.

        Args:
            filename: Name of file to download (in docker/ directory)
            destination: Local path where file should be saved

        Returns:
            True if successful, False otherwise
        """
        url = f"{self.base_url}/{filename}"

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

    def check_cached_templates(self, output_dir: Path) -> bool:
        """
        Check if templates are already cached locally.

        Args:
            output_dir: Directory to check for cached templates

        Returns:
            True if all required files exist
        """
        output_dir = Path(output_dir)
        for filename in REQUIRED_FILES:
            if not (output_dir / filename).exists():
                return False
        return True


class LocalTemplateProvider(TemplateProvider):
    """Provides templates from a local directory (for testing)."""

    def __init__(self, source_dir: Path | str, verbose: bool = False):
        """
        Initialize local template provider.

        Args:
            source_dir: Local directory containing template files
            verbose: Print progress information
        """
        super().__init__(verbose=verbose)
        self.source_dir = Path(source_dir)

    def provide_file(self, filename: str, destination: Path) -> bool:
        """
        Copy a single file from source to destination.

        Args:
            filename: Name of file to copy
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
