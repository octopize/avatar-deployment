#!/usr/bin/env python3
"""
sync-templates.py
Synchronizes authentik email templates from source of truth to deployment targets

Usage:
  ./sync-templates.py [--dry-run] [--verbose]

This script ensures that both the Helm chart's templates-files/ directory
and the Docker compose custom-templates/ directory stay synchronized
with the common/authentik-templates/ source of truth.
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List

# Configuration
SOURCE_DIR = "common/authentik-templates"
HELM_TARGET_DIR = "services-api-helm-chart/templates-files"
DOCKER_TARGET_DIR = "docker/authentik/custom-templates"


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Synchronizes authentik email templates from source of truth to Helm chart.",
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


def get_html_files(directory: Path) -> List[Path]:
    """Get all .html files in a directory (non-recursive)."""
    if not directory.exists():
        return []
    return sorted(directory.glob("*.html"))


def sync_with_rsync(
    source: Path,
    target: Path,
    dry_run: bool = False,
    verbose: bool = False,
) -> bool:
    """Sync files using rsync if available."""
    if not shutil.which("rsync"):
        return False
    
    rsync_opts = [
        "rsync",
        "-av",
        "--delete",
        "--include=*.html",
        "--exclude=*",
    ]
    
    if dry_run:
        rsync_opts.append("--dry-run")
    
    if not verbose:
        rsync_opts.append("--quiet")
    
    # Add trailing slashes to paths for rsync
    rsync_opts.extend([f"{source}/", f"{target}/"])
    
    try:
        subprocess.run(rsync_opts, check=True)
        return True
    except subprocess.CalledProcessError:
        return False


def sync_manual(source: Path, target: Path, dry_run: bool = False) -> None:
    """Fallback sync using manual copy."""
    if not dry_run:
        # Remove old HTML files from target
        for html_file in get_html_files(target):
            html_file.unlink()
        
        # Copy new HTML files
        for html_file in get_html_files(source):
            shutil.copy2(html_file, target / html_file.name)


def sync_to_target(
    source: Path,
    target: Path,
    target_name: str,
    dry_run: bool = False,
    verbose: bool = False,
) -> None:
    """Sync to a target directory."""
    if verbose:
        print(f"→ Syncing to {target_name}...")
    
    # Try rsync first, fall back to manual copy
    if not sync_with_rsync(source, target, dry_run, verbose):
        sync_manual(source, target, dry_run)


def main() -> int:
    """Main execution function."""
    args = parse_args()
    
    # Resolve paths relative to script location
    script_dir = Path(__file__).parent.resolve()
    source_path = script_dir / SOURCE_DIR
    helm_target_path = script_dir / HELM_TARGET_DIR
    docker_target_path = script_dir / DOCKER_TARGET_DIR
    
    # Validate source directory exists
    if not source_path.is_dir():
        print(f"❌ ERROR: Source directory not found: {source_path}")
        print(f"   Expected: {SOURCE_DIR}/")
        return 1
    
    # Create target directories if they don't exist
    for target_path in [helm_target_path, docker_target_path]:
        if not target_path.exists():
            if args.dry_run:
                print(f"📁 Would create directory: {target_path}")
            else:
                target_path.mkdir(parents=True, exist_ok=True)
                print(f"📁 Created directory: {target_path}")
    
    # Count source files
    source_files = get_html_files(source_path)
    source_file_count = len(source_files)
    
    if source_file_count == 0:
        print("⚠️  WARNING: No .html files found in source directory")
        print(f"   Source: {source_path}")
        return 0
    
    print("🔄 Synchronizing authentik email templates...")
    print(f"   Source: {SOURCE_DIR}/ ({source_file_count} files)")
    print("   Targets:")
    print(f"     • {HELM_TARGET_DIR}/ (Helm chart)")
    print(f"     • {DOCKER_TARGET_DIR}/ (Docker Compose)")
    print()
    
    if args.dry_run:
        print("🔍 DRY RUN MODE - No files will be modified")
        print()
    
    # Sync to both targets
    sync_to_target(
        source_path,
        helm_target_path,
        "Helm chart",
        args.dry_run,
        args.verbose,
    )
    sync_to_target(
        source_path,
        docker_target_path,
        "Docker Compose",
        args.dry_run,
        args.verbose,
    )
    
    if not args.dry_run:
        # Count synced files in each target
        helm_count = len(get_html_files(helm_target_path))
        docker_count = len(get_html_files(docker_target_path))
        
        print("✅ Successfully synchronized template file(s)")
        print(f"   • Helm: {helm_count} files")
        print(f"   • Docker: {docker_count} files")
        
        if args.verbose:
            print()
            print("Synchronized files:")
            for html_file in get_html_files(helm_target_path):
                print(f"  ✓ {html_file.name}")
    
    # Show next steps
    if not args.dry_run:
        print()
        print("━" * 80)
        print("✅ Synchronization complete!")
        print()
        print("Next steps:")
        print("  Docker Compose:")
        print(f"    • Review: git diff {DOCKER_TARGET_DIR}")
        print("    • Restart: cd docker && docker-compose restart authentik_server authentik_worker")
        print()
        print("  Helm Chart:")
        print(f"    • Review: git diff {HELM_TARGET_DIR}")
        print("    • Package: helm package services-api-helm-chart/")
        print()
        print("  Commit all changes:")
        print(f"    git add {HELM_TARGET_DIR} {DOCKER_TARGET_DIR}")
        print("    git commit -m 'sync: update email templates'")
        print("━" * 80)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
