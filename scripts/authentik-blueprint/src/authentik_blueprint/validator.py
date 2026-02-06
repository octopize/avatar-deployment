"""Authentik Blueprint Validator - Validates blueprint templates."""

import re
from pathlib import Path
from typing import List


class BlueprintValidator:
    """Validates Authentik blueprint templates."""

    def __init__(self):
        self.validations = [
            ("No database PKs", self.validate_no_pks),
            ("No managed flags", self.validate_no_managed),
            ("No UUIDs", self.validate_no_uuids),
            ("All placeholders documented", self.validate_placeholders),
            ("No user entries", self.validate_no_user_entries),
            ("Only Octopize groups", self.validate_no_unwanted_groups),
        ]

    def validate_no_pks(self, content: str) -> List[str]:
        """Check for database primary keys."""
        errors = []
        for i, line in enumerate(content.split('\n'), 1):
            if re.match(r'^\s+pk:\s+', line):
                errors.append(f"Line {i}: Found database PK field: {line.strip()}")
        return errors

    def validate_no_managed(self, content: str) -> List[str]:
        """Check for managed flags."""
        errors = []
        for i, line in enumerate(content.split('\n'), 1):
            if re.match(r'^\s+managed:\s+', line):
                errors.append(f"Line {i}: Found managed flag: {line.strip()}")
        return errors

    def validate_no_uuids(self, content: str) -> List[str]:
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

    def validate_placeholders(self, content: str) -> List[str]:
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
            for placeholder in sorted(undocumented):
                errors.append(f"Undocumented placeholder: [[{placeholder}]]")

        return errors

    def validate_no_user_entries(self, content: str) -> List[str]:
        """Check for user model entries (should not be in templates)."""
        errors = []
        for i, line in enumerate(content.split('\n'), 1):
            if re.match(r'^\s+model:\s+authentik_core\.user\s*$', line):
                errors.append(f"Line {i}: Found user entry (should not be in template)")
        return errors

    def validate_no_unwanted_groups(self, content: str) -> List[str]:
        """Check for non-Octopize groups."""
        errors = []
        lines = content.split('\n')

        # Track when we're in a group entry
        in_group_entry = False
        group_name = None
        group_start_line = 0

        for i, line in enumerate(lines, 1):
            # Check if this is a group model line
            if re.match(r'^\s+model:\s+authentik_core\.group\s*$', line):
                in_group_entry = True
                group_start_line = i
                group_name = None
                continue

            # If we're in a group entry, look for the name
            if in_group_entry:
                name_match = re.match(r'^\s+name:\s+(.+?)\s*$', line)
                if name_match:
                    group_name = name_match.group(1).strip()

                    # Check if it's an Octopize group
                    if not (group_name.startswith('Octopize') or
                            group_name.startswith('!Context') or
                            group_name.startswith('!Format')):
                        errors.append(
                            f"Line {i}: Found non-Octopize group: {group_name} "
                            f"(group entry starts at line {group_start_line})"
                        )

                    in_group_entry = False

                # If we hit another model line or entries section, reset
                if re.match(r'^\s+model:', line) or re.match(r'^  - ', line):
                    in_group_entry = False

        return errors

    def validate(self, blueprint_path: Path) -> bool:
        """Run all validations on a blueprint file.

        Args:
            blueprint_path: Path to blueprint file

        Returns:
            True if all validations pass, False otherwise
        """
        if not blueprint_path.exists():
            print(f"❌ Blueprint not found: {blueprint_path}")
            return False

        content = blueprint_path.read_text()
        all_errors = []

        for name, validator in self.validations:
            errors = validator(content)

            if errors:
                print(f"❌ {name}: FAILED")
                for error in errors:
                    print(f"   {error}")
                all_errors.extend(errors)
            else:
                print(f"✅ {name}: PASSED")

        if all_errors:
            print(f"\n❌ Validation failed with {len(all_errors)} error(s)")
            return False
        else:
            print("\n✅ All validations PASSED")
            return True
