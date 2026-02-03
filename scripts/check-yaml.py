#!/usr/bin/env python3
# /// script
# dependencies = ["pyyaml>=6.0"]
# ///
"""
Check YAML files for syntax errors, respecting .check-yaml-ignore patterns.

This is a custom version of pre-commit's check-yaml that allows ignoring
certain files via .check-yaml-ignore (similar to .gitignore syntax).
"""

import argparse
import fnmatch
import sys
from pathlib import Path
from typing import List

try:
    import yaml
except ImportError:
    print("Error: pyyaml is required. Install with: pip install pyyaml")
    sys.exit(1)


def load_ignore_patterns(ignore_file: Path) -> List[str]:
    """Load ignore patterns from .check-yaml-ignore file."""
    if not ignore_file.exists():
        return []

    patterns = []
    with open(ignore_file) as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if line and not line.startswith('#'):
                patterns.append(line)
    return patterns


def should_ignore(file_path: str, patterns: List[str], root_dir: Path) -> bool:
    """Check if file should be ignored based on patterns."""
    # Convert to relative path from root
    try:
        rel_path = Path(file_path).relative_to(root_dir)
    except ValueError:
        # File is outside root, use as-is
        rel_path = Path(file_path)

    rel_path_str = str(rel_path)

    for pattern in patterns:
        # Handle directory patterns (ending with /)
        if pattern.endswith('/'):
            if rel_path_str.startswith(pattern) or fnmatch.fnmatch(rel_path_str, pattern + '*'):
                return True
        # Handle glob patterns with wildcards
        elif '*' in pattern:
            if fnmatch.fnmatch(rel_path_str, pattern):
                return True
        # Exact match
        elif rel_path_str == pattern:
            return True

    return False


def check_yaml_file(file_path: str, allow_unsafe: bool = False) -> bool:
    """
    Check if a YAML file is valid.

    Returns True if valid, False if invalid.
    """
    try:
        with open(file_path, 'rb') as f:
            if allow_unsafe:
                # Load all documents, allowing custom tags
                for _ in yaml.load_all(f, Loader=yaml.FullLoader):
                    pass
            else:
                # Use safe loader (default)
                for _ in yaml.safe_load_all(f):
                    pass
        return True
    except yaml.YAMLError as e:
        print(f"Error in {file_path}:")
        print(f"  {e}")
        return False
    except Exception as e:
        print(f"Unexpected error checking {file_path}:")
        print(f"  {e}")
        return False


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Check YAML files for syntax errors'
    )
    parser.add_argument(
        'filenames',
        nargs='*',
        help='Filenames to check'
    )
    parser.add_argument(
        '--unsafe',
        action='store_true',
        help='Allow custom YAML tags (use FullLoader instead of SafeLoader)'
    )
    parser.add_argument(
        '--ignore-file',
        default='.check-yaml-ignore',
        help='Path to ignore patterns file (default: .check-yaml-ignore)'
    )

    args = parser.parse_args(argv)

    # Find root directory (where .check-yaml-ignore should be)
    root_dir = Path.cwd()
    while root_dir != root_dir.parent:
        if (root_dir / '.check-yaml-ignore').exists():
            break
        if (root_dir / '.git').exists():
            break
        root_dir = root_dir.parent

    # Load ignore patterns
    ignore_file = root_dir / args.ignore_file
    ignore_patterns = load_ignore_patterns(ignore_file)

    # Check files
    failed_files = []

    for filename in args.filenames:
        if should_ignore(filename, ignore_patterns, root_dir):
            continue

        if not check_yaml_file(filename, allow_unsafe=args.unsafe):
            failed_files.append(filename)

    # Print summary if we ignored files
    if failed_files:
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
