#!/usr/bin/env python3
# /// script
# requires-python = ">=3.8"
# dependencies = [
#     "pyyaml>=6.0",
#     "requests>=2.31.0",
# ]
# ///
"""
Update image versions in defaults.yaml with latest tags from registries.

This script queries container registries (quay.io, ghcr.io, docker.io) to find
the latest semantic version tags and updates the defaults.yaml file accordingly.

Usage:
    python scripts/update-image-versions.py [--check-only] [--verbose]

Options:
    --check-only    Only check if updates are available, don't modify files
    --verbose       Show detailed information about the update process
Authentication:
    For private repositories, set environment variables:
    - QUAY_TOKEN: Bearer token for quay.io private repositories
    - GITHUB_TOKEN: Personal access token for GitHub Container Registry

Example:
    export QUAY_TOKEN="your_quay_bearer_token"
    export GITHUB_TOKEN="your_github_token"
    python scripts/update-image-versions.py --verbose"""

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Optional, Tuple, dict, list

try:
    import requests
    import yaml
except ImportError:
    print("Error: Missing dependencies. Install with:", file=sys.stderr)
    print("  pip install pyyaml requests", file=sys.stderr)
    print("Or run with uv:", file=sys.stderr)
    print("  uv run scripts/update-image-versions.py", file=sys.stderr)
    sys.exit(1)


# Image configurations: registry, org/repo, version pattern
IMAGE_CONFIGS = {
    "api": {
        "registry": "quay.io",
        "repository": "octopize/services-api",
        "pattern": r"^\d+\.\d+\.\d+$",  # Semantic versioning only
    },
    "web": {
        "registry": "quay.io",
        "repository": "octopize/avatar-web",
        "pattern": r"^\d+\.\d+\.\d+$",
    },
    "pdfgenerator": {
        "registry": "quay.io",
        "repository": "octopize/pdfgenerator",
        "pattern": r"^\d+\.\d+\.\d+$",
    },
    "seaweedfs": {
        "registry": "quay.io",
        "repository": "octopize/seaweedfs-chart",
        "pattern": r"^\d+\.\d+\.\d+$",
    },
    "authentik": {
        "registry": "ghcr.io",
        "repository": "goauthentik/server",
        "pattern": r"^\d{4}\.\d+\.\d+$",  # Year.minor.patch format
    },
}


def parse_semver(version: str) -> Tuple[int, ...]:
    """Parse semantic version string into tuple of integers for comparison."""
    # Handle authentik's year.minor.patch format
    parts = version.split(".")
    return tuple(int(p) for p in parts)


def get_quay_tags(repository: str, verbose: bool = False) -> list[str]:
    """Fetch all tags for a repository from quay.io."""
    url = f"https://quay.io/api/v1/repository/{repository}/tag/"
    params = {"limit": 100, "onlyActiveTags": True}

    # Get token from environment if available (for private repos)
    headers = {}
    quay_token = os.environ.get("QUAY_TOKEN")
    if quay_token:
        headers["Authorization"] = f"Bearer {quay_token}"

    tags = []
    page = 1

    if verbose:
        print(f"  Fetching tags from quay.io/{repository}...")
        if quay_token:
            print("  Using authentication token")

    while True:
        params["page"] = page
        try:
            response = requests.get(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()

            tags.extend([tag["name"] for tag in data.get("tags", [])])

            if not data.get("has_additional"):
                break
            page += 1
        except requests.RequestException as e:
            if verbose:
                print(f"  Warning: Failed to fetch tags from quay.io: {e}", file=sys.stderr)
            # If authentication failed, suggest setting QUAY_TOKEN
            if "401" in str(e) or "UNAUTHORIZED" in str(e):
                if not quay_token and verbose:
                    print("  Hint: Set QUAY_TOKEN environment variable for private repos", file=sys.stderr)
            return []

    if verbose:
        print(f"  Found {len(tags)} tags")

    return tags


def get_ghcr_tags(repository: str, verbose: bool = False) -> list[str]:
    """Fetch all tags for a repository from ghcr.io (GitHub Container Registry)."""
    # GitHub Container Registry uses GitHub Packages API
    # We need to extract org/repo from the repository string
    org, repo = repository.split("/", 1)

    # Use GitHub API to get package versions
    url = f"https://api.github.com/orgs/{org}/packages/container/{repo}/versions"
    headers = {"Accept": "application/vnd.github.v3+json"}

    # Get token from environment if available
    github_token = os.environ.get("GITHUB_TOKEN")
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"

    if verbose:
        print(f"  Fetching tags from ghcr.io/{repository}...")
        if github_token:
            print("  Using authentication token")

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()

        # Extract tags from metadata
        tags = []
        for version in data:
            if "metadata" in version and "container" in version["metadata"]:
                tags.extend(version["metadata"]["container"].get("tags", []))

        if verbose:
            print(f"  Found {len(tags)} tags")

        return list(set(tags))  # Remove duplicates
    except requests.RequestException as e:
        if verbose:
            print(f"  Warning: Failed to fetch tags from ghcr.io: {e}", file=sys.stderr)
            if "401" in str(e) or "Unauthorized" in str(e):
                if not github_token:
                    print("  Hint: Set GITHUB_TOKEN environment variable for private repos", file=sys.stderr)
        return []


def get_latest_version(image_name: str, config: dict, verbose: bool = False) -> Optional[str]:
    """Get the latest version tag for an image from its registry."""
    registry = config["registry"]
    repository = config["repository"]
    pattern = re.compile(config["pattern"])

    if verbose:
        print(f"\n{image_name}:")

    # Fetch tags based on registry
    if registry == "quay.io":
        tags = get_quay_tags(repository, verbose)
    elif registry == "ghcr.io":
        tags = get_ghcr_tags(repository, verbose)
    else:
        print(f"  Unsupported registry: {registry}", file=sys.stderr)
        return None

    if not tags:
        print(f"  Warning: No tags found for {repository}", file=sys.stderr)
        return None

    # Filter tags matching version pattern
    valid_tags = [tag for tag in tags if pattern.match(tag)]

    if not valid_tags:
        print(f"  Warning: No valid version tags found for {repository}", file=sys.stderr)
        if verbose:
            print(f"  Pattern: {config['pattern']}")
            print(f"  Sample tags: {tags[:5]}")
        return None

    # Sort by semantic version and get latest
    valid_tags.sort(key=parse_semver, reverse=True)
    latest = valid_tags[0]

    if verbose:
        print(f"  Latest version: {latest}")
        print(f"  (from {len(valid_tags)} matching tags)")

    return latest


def load_defaults_yaml(defaults_path: Path) -> dict:
    """Load the defaults.yaml file."""
    with open(defaults_path, "r") as f:
        return yaml.safe_load(f)


def save_defaults_yaml(defaults_path: Path, data: dict) -> None:
    """Save the defaults.yaml file preserving comments and structure."""
    with open(defaults_path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


def update_image_versions(
    defaults_path: Path,
    check_only: bool = False,
    verbose: bool = False
) -> Tuple[bool, list[str]]:
    """
    Update image versions in defaults.yaml.

    Returns:
        Tuple of (has_updates, list of update messages)
    """
    if verbose:
        print(f"Loading defaults from: {defaults_path}")

    data = load_defaults_yaml(defaults_path)
    current_versions = data.get("images", {})

    updates = []
    has_changes = False

    print("\nChecking for image updates...")

    for image_name, config in IMAGE_CONFIGS.items():
        current_version = current_versions.get(image_name)

        if not current_version:
            if verbose:
                print(f"\n{image_name}: Not found in defaults.yaml, skipping")
            continue

        latest_version = get_latest_version(image_name, config, verbose)

        if not latest_version:
            continue

        if latest_version != current_version:
            message = f"  {image_name}: {current_version} → {latest_version}"
            updates.append(message)
            has_changes = True

            if not check_only:
                data["images"][image_name] = latest_version
        else:
            if verbose:
                print(f"  {image_name}: {current_version} (up to date)")

    if updates:
        print("\nUpdates available:")
        for update in updates:
            print(update)

        if not check_only:
            save_defaults_yaml(defaults_path, data)
            print(f"\n✓ Updated {defaults_path}")
        else:
            print("\n(Run without --check-only to apply updates)")
    else:
        print("\n✓ All image versions are up to date")

    return has_changes, updates


def main():
    parser = argparse.ArgumentParser(
        description="Update image versions in defaults.yaml from registries"
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Only check for updates, don't modify files"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed information"
    )

    args = parser.parse_args()

    # Find defaults.yaml relative to script location
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    defaults_path = repo_root / "docker" / "deployment-tool" / "defaults.yaml"

    if not defaults_path.exists():
        print(f"Error: defaults.yaml not found at {defaults_path}", file=sys.stderr)
        sys.exit(1)

    try:
        has_changes, updates = update_image_versions(
            defaults_path,
            check_only=args.check_only,
            verbose=args.verbose
        )

        # Exit with code 1 if there are uncommitted changes (for pre-commit)
        if has_changes and not args.check_only:
            print("\n⚠ Image versions were updated. Please review and commit the changes.")
            sys.exit(1)

        sys.exit(0)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
