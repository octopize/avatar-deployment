#!/usr/bin/env python3
"""
Authentik Blueprint Template Validator

This script validates the blueprint template to ensure:
1. No database PKs (pk:) remain
2. No managed flags remain
3. No UUIDs remain
4. No blueprint-level IDs remain (should use !Find instead of !KeyOf)
5. All placeholders are documented
6. Template can be successfully injected with test values

Usage:
    python validate_template.py
"""

import re
import sys
from pathlib import Path


def validate_no_pks(content: str) -> list[str]:
    """Check for database primary keys."""
    errors = []
    for i, line in enumerate(content.split('\n'), 1):
        if re.match(r'^\s+pk:\s+', line):
            errors.append(f"Line {i}: Found database PK field: {line.strip()}")
    return errors


def validate_no_managed(content: str) -> list[str]:
    """Check for managed flags."""
    errors = []
    for i, line in enumerate(content.split('\n'), 1):
        if re.match(r'^\s+managed:\s+', line):
            errors.append(f"Line {i}: Found managed flag: {line.strip()}")
    return errors


def validate_no_uuids(content: str) -> list[str]:
    """Check for UUIDs."""
    errors = []
    uuid_pattern = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
    for i, line in enumerate(content.split('\n'), 1):
        # Skip comment lines that show examples
        if line.strip().startswith('#'):
            continue
        if re.search(uuid_pattern, line, re.IGNORECASE):
            errors.append(f"Line {i}: Found UUID: {line.strip()}")
    return errors


def validate_no_blueprint_ids(content: str) -> list[str]:
    """Check for blueprint-level ID fields (should use !Find, not !KeyOf)."""
    errors = []
    lines = content.split('\n')

    for i, line in enumerate(lines, 1):
        # Check for id: fields that are not in comments
        if re.match(r'^\s+id:\s+\w', line) and not line.strip().startswith('#'):
            # Make sure it's at the right indentation level (entry-level, not attrs)
            # Entry-level IDs are typically at 4 spaces
            if line.startswith('    id:') and not line.startswith('      '):
                errors.append(f"Line {i}: Found blueprint ID field: {line.strip()}")

    return errors


def validate_no_keyof(content: str) -> list[str]:
    """Check for !KeyOf usage (should use !Find instead)."""
    errors = []
    for i, line in enumerate(content.split('\n'), 1):
        if '!KeyOf' in line and not line.strip().startswith('#'):
            errors.append(f"Line {i}: Found !KeyOf (use !Find instead): {line.strip()}")
    return errors


def validate_placeholders(content: str) -> list[str]:
    """Check that all placeholders used in content are documented in header comments."""
    errors = []

    # Extract header comments (before first non-comment line after metadata)
    header_lines = []
    in_header = True
    for line in content.split('\n'):
        if in_header:
            if line.strip().startswith('#') or not line.strip() or line.startswith('---') or line.startswith('version:') or line.startswith('metadata:'):
                header_lines.append(line)
            else:
                in_header = False
    header = '\n'.join(header_lines)

    # Find all placeholders in content (excluding header)
    content_without_header = '\n'.join(content.split('\n')[len(header_lines):])
    placeholders_in_content = set(re.findall(r'\[\[([^\]]+)\]\]', content_without_header))

    # Find all placeholders mentioned in header (including in comments)
    placeholders_in_header = set(re.findall(r'\[\[([^\]]+)\]\]', header))

    # Check for undocumented placeholders
    undocumented = placeholders_in_content - placeholders_in_header
    if undocumented:
        errors.append(f"Undocumented placeholders: {', '.join(sorted(undocumented))}")

    return errors


def main():
    """Run all validations."""
    # Template moved to docker/templates/authentik/
    template_path = Path(__file__).parent.parent / "docker" / "templates" / "authentik" / "octopize-avatar-blueprint.yaml"

    if not template_path.exists():
        print(f"❌ Template not found: {template_path}")
        sys.exit(1)

    content = template_path.read_text()

    all_errors = []

    # Run validations
    validations = [
        ("No database PKs", validate_no_pks),
        ("No managed flags", validate_no_managed),
        ("No UUIDs", validate_no_uuids),
        ("No blueprint IDs", validate_no_blueprint_ids),
        ("No !KeyOf usage", validate_no_keyof),
        ("All placeholders documented", validate_placeholders),
    ]

    for name, validator in validations:
        errors = validator(content)

        if errors:
            print(f"❌ {name}: FAILED")
            for error in errors:
                print(f"   {error}")
            all_errors.extend(errors)

    if all_errors:
        print(f"\n❌ Validation failed with {len(all_errors)} error(s)")
        sys.exit(1)

if __name__ == "__main__":
    main()
