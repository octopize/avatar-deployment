#!/usr/bin/env python3
"""
sync-templates.py
Synchronizes authentik email templates and branding assets from source of truth to deployment targets

Usage:
  ./sync-templates.py [--dry-run] [--verbose]

This script ensures that both the Helm chart and Docker compose directories
stay synchronized with the common/ source of truth for:
  - Email templates (*.html files)
  - Branding assets (favicon.ico, logo.png)
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List

# Configuration - Email Templates
SOURCE_DIR = "common/authentik-templates"
HELM_TARGET_DIR = "services-api-helm-chart/templates-files"
DOCKER_TARGET_DIR = "docker/authentik/custom-templates"

# Configuration - Branding Assets
BRANDING_SOURCE_DIR = "common/authentik-branding"
BRANDING_HELM_TARGET_DIR = "services-api-helm-chart/branding"
# Docker uses direct mount from common/authentik-branding, no copy needed


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


def get_branding_files(directory: Path) -> List[Path]:
    """Get branding asset files (favicon.ico, logo.png)."""
    if not directory.exists():
        return []
    branding_files = []
    for pattern in ["favicon.ico", "logo.png"]:
        files = list(directory.glob(pattern))
        branding_files.extend(files)
    return sorted(branding_files)


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


def sync_manual(source: Path, target: Path, dry_run: bool = False, file_pattern: str = "*.html") -> None:
    """Fallback sync using manual copy."""
    if not dry_run:
        # Determine which files to sync based on pattern
        if file_pattern == "*.html":
            source_files = get_html_files(source)
            target_files = get_html_files(target)
        else:  # branding assets
            source_files = get_branding_files(source)
            target_files = get_branding_files(target)
        
        # Remove old files from target
        for old_file in target_files:
            old_file.unlink()
        
        # Copy new files
        for file_path in source_files:
            shutil.copy2(file_path, target / file_path.name)


def sync_to_target(
    source: Path,
    target: Path,
    target_name: str,
    dry_run: bool = False,
    verbose: bool = False,
    file_pattern: str = "*.html",
) -> None:
    """Sync to a target directory."""
    if verbose:
        print(f"→ Syncing to {target_name}...")
    
    # Try rsync first, fall back to manual copy
    if not sync_with_rsync(source, target, dry_run, verbose):
        sync_manual(source, target, dry_run, file_pattern)


def main() -> int:
    """Main execution function."""
    args = parse_args()
    
    # Resolve paths relative to script location
    
    # Email templates paths
    source_path = script_dir / SOURCE_DIR
    helm_target_path = script_dir / HELM_TARGET_DIR
    docker_target_path = script_dir / DOCKER_TARGET_DIR
    
    # Branding assets paths
    branding_source_path = script_dir / BRANDING_SOURCE_DIR
    branding_helm_target_path = script_dir / BRANDING_HELM_TARGET_DIR
    
    # Validate email templates source directory exists
    if not source_path.is_dir():
        print(f"❌ ERROR: Email templates source directory not found: {source_path}")
        print(f"   Expected: {SOURCE_DIR}/")
        return 1
    
    # Create target directories if they don't exist
    all_target_paths = [helm_target_path, docker_target_path, branding_helm_target_path]
    for target_path in all_target_paths:
        if not target_path.exists():
            if args.dry_run:
                print(f"📁 Would create directory: {target_path}")
            else:
                target_path.mkdir(parents=True, exist_ok=True)
                if args.verbose:
                    print(f"📁 Created directory: {target_path}")
    
    # Count source files
    source_files = get_html_files(source_path)
    source_file_count = len(source_files)
    
    branding_files = get_branding_files(branding_source_path) if branding_source_path.exists() else []
    branding_file_count = len(branding_files)
    
    if source_file_count == 0:
        print("⚠️  WARNING: No .html files found in email templates source directory")
        print(f"   Source: {source_path}")
    
    print("🔄 Synchronizing authentik email templates and branding...")
    print()
    print("📧 Email Templates:")
    print(f"   Source: {SOURCE_DIR}/ ({source_file_count} files)")
    print("   Targets:")
    print(f"     • {HELM_TARGET_DIR}/ (Helm chart)")
    print(f"     • {DOCKER_TARGET_DIR}/ (Docker Compose)")
    print()
    print("🎨 Branding Assets:")
    print(f"   Source: {BRANDING_SOURCE_DIR}/ ({branding_file_count} files)")
    print("   Targets:")
    print(f"     • {BRANDING_HELM_TARGET_DIR}/ (Helm chart)")
    print(f"     • Docker uses direct mount from {BRANDING_SOURCE_DIR}/")
    print()
    
    if args.dry_run:
        print("🔍 DRY RUN MODE - No files will be modified")
        print()
    
    # Sync email templates to both targets
    if source_file_count > 0:
        sync_to_target(
            source_path,
            helm_target_path,
            "Helm chart (templates)",
            args.dry_run,
            args.verbose,
            "*.html",
        )
        sync_to_target(
            source_path,
            docker_target_path,
            "Docker Compose (templates)",
            args.dry_run,
            args.verbose,
            "*.html",
        )
    
    # Sync branding assets to Helm target only
    if branding_file_count > 0:
        sync_to_target(
            branding_source_path,
            branding_helm_target_path,
            "Helm chart (branding)",
            args.dry_run,
            args.verbose,
            "branding",
        )
    
    if not args.dry_run:
        # Count synced files in each target
        helm_count = len(get_html_files(helm_target_path))
        docker_count = len(get_html_files(docker_target_path))
        branding_count = len(get_branding_files(branding_helm_target_path))
        
        print("✅ Successfully synchronized files")
        print(f"   • Email templates (Helm): {helm_count} files")
        print(f"   • Email templates (Docker): {docker_count} files")
        print(f"   • Branding assets (Helm): {branding_count} files")
        
        if args.verbose:
            print()
            print("Synchronized email templates:")
            for html_file in get_html_files(helm_target_path):
                print(f"  ✓ {html_file.name}")
            print()
            print("Synchronized branding assets:")
            for brand_file in get_branding_files(branding_helm_target_path):
                print(f"  ✓ {brand_file.name}")
    
    # Show next steps
    if not args.dry_run:
        print()
        print("━" * 80)
        print("✅ Synchronization complete!")
        print()
        print("Next steps:")
        print("  Docker Compose:")
        print(f"    • Review: git diff {DOCKER_TARGET_DIR}")
        print(f"    • Branding files are mounted directly from {BRANDING_SOURCE_DIR}/")
        print("    • Restart: cd docker && docker-compose restart authentik_server authentik_worker")
        print()
        print("  Helm Chart:")
        print(f"    • Review: git diff {HELM_TARGET_DIR} {BRANDING_HELM_TARGET_DIR}")
        print("    • Package: just push-helm-chart")
        print()
        print("  Commit all changes:")
        print(f"    git add {HELM_TARGET_DIR} {DOCKER_TARGET_DIR} {BRANDING_HELM_TARGET_DIR}")
        print("    git commit -m 'sync: update email templates and brandingIR}")
        print("    git commit -m 'sync: update email templates'")
        print("━" * 80)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
