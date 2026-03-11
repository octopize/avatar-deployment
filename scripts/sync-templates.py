#!/usr/bin/env python3
"""
sync-templates.py
Synchronizes authentik assets from common/ source of truth to deployment targets.

Syncs:
  - Email templates (*.html files)
  - Branding assets (favicon.ico, logo.png, background.png)
  - Blueprint (octopize-avatar-blueprint.yaml)

Usage:
  ./sync-templates.py [--dry-run] [--verbose]

This script ensures that the Helm chart, Docker compose, and deployment-tool
directories stay synchronized with the common/ source of truth.
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


# ── Email Templates ──────────────────────────────────────────────────────────
EMAIL_SOURCE_DIR = "common/authentik-templates"
EMAIL_TARGETS = {
    "Helm chart":     "services-api-helm-chart/static/emails",
    "Docker Compose": "docker/authentik/custom-templates",
}

# ── Branding Assets ──────────────────────────────────────────────────────────
BRANDING_SOURCE_DIR = "common/authentik-branding"
BRANDING_TARGETS = {
    "Helm chart":     "services-api-helm-chart/static/branding",
    "Docker Compose": "docker/authentik/branding",
}

# ── Blueprint ────────────────────────────────────────────────────────────────
BLUEPRINT_SOURCE_DIR = "common/authentik-blueprint"
BLUEPRINT_TARGETS = {
    "Helm chart":         "services-api-helm-chart/static/blueprint",
    "Docker (templates)": "docker/templates/authentik",
}


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Synchronizes authentik assets from source of truth to deployment targets.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be copied without making changes",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show detailed output",
    )
    return parser.parse_args()


def get_files_by_patterns(directory: Path, patterns: list[str]) -> list[Path]:
    """Get all files matching any of the given glob patterns in a directory (non-recursive)."""
    if not directory.exists():
        return []
    files: list[Path] = []
    for pattern in patterns:
        files.extend(directory.glob(pattern))
    return sorted(set(files))


def sync_with_rsync(
    source: Path,
    target: Path,
    include_patterns: list[str],
    dry_run: bool = False,
    verbose: bool = False,
) -> bool:
    """Sync files using rsync if available."""
    if not shutil.which("rsync"):
        return False

    rsync_opts = ["rsync", "-av", "--delete"]

    for pattern in include_patterns:
        rsync_opts.append(f"--include={pattern}")
    rsync_opts.append("--exclude=*")

    if dry_run:
        rsync_opts.append("--dry-run")
    if not verbose:
        rsync_opts.append("--quiet")

    rsync_opts.extend([f"{source}/", f"{target}/"])

    try:
        subprocess.run(rsync_opts, check=True)
        return True
    except subprocess.CalledProcessError:
        return False


def sync_manual(
    source: Path,
    target: Path,
    patterns: list[str],
    dry_run: bool = False,
) -> None:
    """Fallback sync using manual copy."""
    if dry_run:
        return

    source_files = get_files_by_patterns(source, patterns)
    target_files = get_files_by_patterns(target, patterns)

    # Remove old files from target that match the patterns
    for old_file in target_files:
        old_file.unlink()

    # Copy new files
    for file_path in source_files:
        shutil.copy2(file_path, target / file_path.name)


def sync_to_target(
    source: Path,
    target: Path,
    target_name: str,
    include_patterns: list[str],
    dry_run: bool = False,
    verbose: bool = False,
) -> None:
    """Sync to a target directory."""
    if verbose:
        print(f"  → Syncing to {target_name}...")

    if not sync_with_rsync(source, target, include_patterns, dry_run, verbose):
        sync_manual(source, target, include_patterns, dry_run)


# ── Asset category descriptor ───────────────────────────────────────────────
class AssetCategory:
    """Describes one category of files to sync."""

    def __init__(
        self,
        label: str,
        emoji: str,
        source_dir: str,
        targets: dict[str, str],
        file_patterns: list[str],
    ):
        self.label = label
        self.emoji = emoji
        self.source_dir = source_dir
        self.targets = targets
        self.file_patterns = file_patterns


ASSET_CATEGORIES = [
    AssetCategory(
        label="Email Templates",
        emoji="📧",
        source_dir=EMAIL_SOURCE_DIR,
        targets=EMAIL_TARGETS,
        file_patterns=["*.html"],
    ),
    AssetCategory(
        label="Branding Assets",
        emoji="🎨",
        source_dir=BRANDING_SOURCE_DIR,
        targets=BRANDING_TARGETS,
        file_patterns=["*.ico", "*.png"],
    ),
    AssetCategory(
        label="Blueprint",
        emoji="📋",
        source_dir=BLUEPRINT_SOURCE_DIR,
        targets=BLUEPRINT_TARGETS,
        file_patterns=["*.yaml"],
    ),
]


def main() -> int:
    """Main execution function."""
    args = parse_args()

    # Resolve paths relative to repo root (script lives in scripts/)
    repo_root = Path(__file__).parent.parent.resolve()

    # Validate source directories exist
    for category in ASSET_CATEGORIES:
        source_path = repo_root / category.source_dir
        if not source_path.is_dir():
            print(f"❌ ERROR: {category.label} source directory not found: {source_path}")
            print(f"   Expected: {category.source_dir}/")
            return 1

    # Ensure target directories exist
    for category in ASSET_CATEGORIES:
        for target_name, target_dir in category.targets.items():
            target_path = repo_root / target_dir
            if not target_path.exists():
                if args.dry_run:
                    if args.verbose:
                        print(f"📁 Would create directory: {target_dir}")
                else:
                    target_path.mkdir(parents=True, exist_ok=True)
                    if args.verbose:
                        print(f"📁 Created directory: {target_dir}")

    # Print summary header
    if args.verbose:
        print("🔄 Synchronizing authentik assets...")
        print()
        for category in ASSET_CATEGORIES:
            source_path = repo_root / category.source_dir
            source_files = get_files_by_patterns(source_path, category.file_patterns)
            print(f"{category.emoji} {category.label}:")
            print(f"   Source: {category.source_dir}/ ({len(source_files)} files)")
            print("   Targets:")
            for target_name, target_dir in category.targets.items():
                print(f"     • {target_dir}/ ({target_name})")
            print()

        if args.dry_run:
            print("🔍 DRY RUN MODE - No files will be modified")
            print()

    # Perform sync for each category
    for category in ASSET_CATEGORIES:
        source_path = repo_root / category.source_dir
        source_files = get_files_by_patterns(source_path, category.file_patterns)

        if not source_files:
            if args.verbose:
                print(f"⚠️  WARNING: No matching files found in {category.source_dir}")
            continue

        for target_name, target_dir in category.targets.items():
            target_path = repo_root / target_dir
            sync_to_target(
                source_path,
                target_path,
                f"{target_name} ({category.label.lower()})",
                category.file_patterns,
                args.dry_run,
                args.verbose,
            )

    # Report results
    if not args.dry_run and args.verbose:
        print("✅ Successfully synchronized files:")
        for category in ASSET_CATEGORIES:
            for target_name, target_dir in category.targets.items():
                target_path = repo_root / target_dir
                count = len(get_files_by_patterns(target_path, category.file_patterns))
                print(f"   • {category.label} → {target_name}: {count} files")

        print()
        for category in ASSET_CATEGORIES:
            print(f"{category.emoji} Synchronized {category.label.lower()}:")
            first_target = repo_root / next(iter(category.targets.values()))
            for f in get_files_by_patterns(first_target, category.file_patterns):
                print(f"  ✓ {f.name}")
            print()

    # Show next steps
    if not args.dry_run and args.verbose:
        print()
        print("━" * 80)
        print("✅ Synchronization complete!")
        print()
        print("Next steps:")
        print("  Commit all changes:")
        print("    git add services-api-helm-chart/static/ docker/authentik/ docker/templates/authentik/")
        print("    git commit -m 'sync: update authentik assets'")
        print("━" * 80)

    return 0


if __name__ == "__main__":
    sys.exit(main())
