"""
Download deployment templates from GitHub repository.

This module handles downloading necessary template files from the
avatar-deployment repository to avoid bundling them in the package.
"""

import urllib.request
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


class TemplateDownloader:
    """Downloads deployment templates from GitHub."""

    def __init__(self, branch: str = DEFAULT_BRANCH, verbose: bool = False):
        """
        Initialize template downloader.

        Args:
            branch: Git branch to download from (default: main)
            verbose: Print download progress
        """
        self.branch = branch
        self.verbose = verbose
        self.base_url = f"{GITHUB_RAW_BASE}/{branch}/docker"

    def download_file(self, filename: str, destination: Path) -> bool:
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

    def download_all(self, output_dir: Path) -> bool:
        """
        Download all required template files.

        Args:
            output_dir: Directory where files should be saved

        Returns:
            True if all files downloaded successfully
        """
        output_dir = Path(output_dir)
        success = True

        if self.verbose:
            print(f"\nDownloading templates to {output_dir}/")
            print("=" * 60)

        for filename in REQUIRED_FILES:
            destination = output_dir / filename
            if not self.download_file(filename, destination):
                success = False
                print(f"⚠ Warning: Failed to download {filename}")

        if self.verbose:
            if success:
                print("\n✓ All templates downloaded successfully")
            else:
                print("\n⚠ Some templates failed to download")

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
    downloader = TemplateDownloader(branch=branch, verbose=verbose)

    # Check if already cached
    if not force and downloader.check_cached_templates(output_dir):
        if verbose:
            print(f"Templates already cached in {output_dir}/")
        return True

    # Download
    return downloader.download_all(output_dir)
