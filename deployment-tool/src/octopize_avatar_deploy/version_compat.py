"""
Version compatibility checking for Avatar deployment tool.

Ensures that the script version is compatible with template and config versions.
Prevents old scripts from modifying new templates (forward compatibility).
"""

import re
from pathlib import Path

# Script version (semantic versioning: MAJOR.MINOR.PATCH)
SCRIPT_VERSION = "2.7.0"


class VersionError(Exception):
    """Raised when version compatibility check fails."""

    pass


def parse_version(version_str: str) -> tuple[int, int, int]:
    """
    Parse semantic version string into tuple.

    Args:
        version_str: Version string like "1.2.3"

    Returns:
        Tuple of (major, minor, patch)

    Raises:
        ValueError: If version string is invalid
    """
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)$", version_str.strip())
    if not match:
        raise ValueError(f"Invalid version string: {version_str}")
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)))


def parse_version_constraint(constraint: str) -> tuple[str, tuple[int, int, int]]:
    """
    Parse version constraint like ">=1.0.0" or "<2.0.0".

    Args:
        constraint: Version constraint string

    Returns:
        Tuple of (operator, version_tuple)
    """
    match = re.match(r"^([><=]+)([\d.]+)$", constraint.strip())
    if not match:
        raise ValueError(f"Invalid constraint: {constraint}")

    operator, version_str = match.groups()
    version = parse_version(version_str)
    return operator, version


def check_constraint(
    version: tuple[int, int, int],
    operator: str,
    constraint_version: tuple[int, int, int],
) -> bool:
    """
    Check if version satisfies constraint.

    Args:
        version: Version tuple to check
        operator: Comparison operator (>=, <, >, <=, ==)
        constraint_version: Version tuple to compare against

    Returns:
        True if constraint is satisfied
    """
    if operator == ">=":
        return version >= constraint_version
    elif operator == ">":
        return version > constraint_version
    elif operator == "<=":
        return version <= constraint_version
    elif operator == "<":
        return version < constraint_version
    elif operator == "==":
        return version == constraint_version
    else:
        raise ValueError(f"Unknown operator: {operator}")


def check_version_compatibility(script_version: str, required_version: str) -> bool:
    """
    Check if script version satisfies requirement.

    Args:
        script_version: Current script version (e.g., "1.0.0")
        required_version: Required version spec (e.g., ">=1.0.0,<2.0.0")

    Returns:
        True if compatible

    Raises:
        VersionError: If versions are incompatible
    """
    script_ver = parse_version(script_version)

    # Parse requirement (can be comma-separated constraints)
    constraints = [c.strip() for c in required_version.split(",")]

    for constraint in constraints:
        operator, required_ver = parse_version_constraint(constraint)
        if not check_constraint(script_ver, operator, required_ver):
            return False

    return True


def extract_template_version(template_path: Path) -> str | None:
    """
    Extract version from template file header.

    Expected format:
    # Template Version: 1.0.0
    # Compatible with octopize-avatar-deploy: >=1.0.0,<2.0.0

    Args:
        template_path: Path to template file

    Returns:
        Version string or None if not found
    """
    try:
        content = template_path.read_text()

        # Look for version in first 20 lines
        lines = content.split("\n")[:20]

        for line in lines:
            # Match: # Template Version: 1.0.0
            if "template version:" in line.lower():
                match = re.search(r"(\d+\.\d+\.\d+)", line)
                if match:
                    return match.group(1)

        return None
    except Exception:
        return None


def extract_compatibility_spec(template_path: Path) -> str | None:
    """
    Extract compatibility spec from template file header.

    Args:
        template_path: Path to template file

    Returns:
        Compatibility spec string or None if not found
    """
    try:
        content = template_path.read_text()
        lines = content.split("\n")[:20]

        for line in lines:
            # Match: # Compatible with octopize-avatar-deploy: >=1.0.0,<2.0.0
            if "compatible with" in line.lower():
                match = re.search(r":\s*([\d\s.,<>=]+)$", line)
                if match:
                    return match.group(1).strip()

        return None
    except Exception:
        return None


def validate_template_compatibility(
    template_path: Path, script_version: str = SCRIPT_VERSION, verbose: bool = False
) -> bool:
    """
    Validate that script version is compatible with template.

    Args:
        template_path: Path to template file
        script_version: Script version to check
        verbose: Print validation details

    Returns:
        True if compatible or no version info found

    Raises:
        VersionError: If versions are incompatible
    """
    template_version = extract_template_version(template_path)
    compatibility_spec = extract_compatibility_spec(template_path)

    if verbose:
        print(f"Validating {template_path.name}:")
        print(f"  Template version: {template_version or 'not specified'}")
        print(f"  Compatibility: {compatibility_spec or 'not specified'}")
        print(f"  Script version: {script_version}")

    # If no version info in template, assume compatible (legacy template)
    if not compatibility_spec:
        if verbose:
            print("  ✓ No version constraints (assuming compatible)")
        return True

    # Check compatibility
    try:
        compatible = check_version_compatibility(script_version, compatibility_spec)

        if compatible:
            if verbose:
                print("  ✓ Compatible")
            return True
        else:
            raise VersionError(
                f"Script version {script_version} is not compatible with "
                f"{template_path.name} (requires {compatibility_spec}). "
                f"Please upgrade octopize-avatar-deploy: "
                f"pip install --upgrade octopize-avatar-deploy"
            )

    except ValueError as e:
        if verbose:
            print(f"  ⚠ Warning: Invalid version spec: {e}")
        # If version spec is invalid, assume compatible to avoid breaking
        return True


def validate_all_templates(
    templates_dir: Path, script_version: str = SCRIPT_VERSION, verbose: bool = False
) -> bool:
    """
    Validate all templates in directory.

    Args:
        templates_dir: Directory containing templates
        script_version: Script version to check
        verbose: Print validation details

    Returns:
        True if all templates are compatible

    Raises:
        VersionError: If any template is incompatible
    """
    if verbose:
        print("\nValidating template compatibility...")
        print("=" * 60)

    templates = list(templates_dir.glob("*.template"))

    if not templates:
        if verbose:
            print("No templates found")
        return True

    for template in templates:
        validate_template_compatibility(template, script_version, verbose)

    if verbose:
        print(f"\n✓ All {len(templates)} templates are compatible")

    return True


def validate_template_version(
    version_file: Path, script_version: str = SCRIPT_VERSION, verbose: bool = False
) -> None:
    """
    Validate that the template version is compatible with the script version.

    This reads the .template-version file which should contain:
    - First line: template version (e.g., "0.1.0")
    - Optional second line: compatibility constraint (e.g., ">=1.0.0,<2.0.0")

    Args:
        version_file: Path to .template-version file
        script_version: Script version to check against
        verbose: Print validation details

    Raises:
        VersionError: If template version is incompatible with script version
    """
    try:
        content = version_file.read_text().strip().split("\n")

        if not content or not content[0].strip():
            raise VersionError(
                f"Invalid .template-version file: {version_file} (empty or missing version)"
            )

        template_version = content[0].strip()

        # Parse template version to validate format
        try:
            parse_version(template_version)
        except ValueError as e:
            raise VersionError(
                f"Invalid template version format in {version_file}: {template_version}"
            ) from e

        # Check for compatibility constraint (optional second line)
        compatibility_spec = None
        if len(content) > 1 and content[1].strip():
            compatibility_spec = content[1].strip()

        if verbose:
            print(f"\nValidating template version from {version_file.name}:")
            print(f"  Template version: {template_version}")
            print(f"  Compatibility spec: {compatibility_spec or 'not specified'}")
            print(f"  Script version: {script_version}")

        # If no compatibility spec, accept any script version
        if not compatibility_spec:
            if verbose:
                print("  ✓ No version constraints (compatible)")
            return

        # Check compatibility
        try:
            compatible = check_version_compatibility(script_version, compatibility_spec)

            if compatible:
                if verbose:
                    print("  ✓ Compatible")
            else:
                raise VersionError(
                    f"Script version {script_version} is not compatible with "
                    f"template version {template_version} (requires {compatibility_spec}). "
                    f"Please upgrade octopize-avatar-deploy: "
                    f"pip install --upgrade octopize-avatar-deploy"
                )

        except ValueError as e:
            # Invalid constraint format - log warning but don't fail
            if verbose:
                print(f"  ⚠ Warning: Invalid compatibility spec: {e}")

    except FileNotFoundError:
        raise VersionError(f"Template version file not found: {version_file}") from None
    except Exception as e:
        if isinstance(e, VersionError):
            raise
        raise VersionError(f"Failed to validate template version: {e}") from e
