#!/usr/bin/env python3
# /// script
# dependencies = ["yamllint>=1.33.0"]
# ///
"""
Lint Helm chart templates by rendering them and running yamllint.

This script:
1. Renders the Helm chart templates
2. Splits them into individual YAML files
3. Filters out subchart templates (charts/ directory)
4. Runs yamllint on our own templates
"""

import re
import subprocess
import sys
import tempfile
from pathlib import Path

# Configuration
PATH_TO_CHART = "services-api-helm-chart"
RELEASE_NAME = "services-api"
NAMESPACE = "services-api"
YAMLLINT_CONFIG = ".yamllint"


def render_helm_templates() -> str:
    """Render Helm templates using helm template command."""
    try:
        result = subprocess.run(
            ["helm", "template", RELEASE_NAME, PATH_TO_CHART, "--namespace", NAMESPACE],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        print("❌ Failed to render Helm templates:")
        print(e.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print("❌ helm command not found. Please install Helm.")
        sys.exit(1)


def split_yaml_to_files(yaml_content: str, output_dir: Path) -> list[Path]:
    """
    Split multi-document YAML into individual files based on Source comments.

    Returns list of file paths that were written.
    """
    split_re = re.compile("^---$", re.MULTILINE)
    grab_source_re = re.compile("^# Source: (.+)$", re.MULTILINE)

    files_written = []

    for doc in re.split(split_re, yaml_content):
        source_match = grab_source_re.search(doc)
        if not source_match:
            continue

        filename = source_match.group(1)

        # Discard the first line of the doc (Source comment)
        doc_lines = doc.split("\n")[2:]
        doc_content = "\n".join(doc_lines)

        # Write to temp directory
        new_file = output_dir / filename
        new_file.parent.mkdir(parents=True, exist_ok=True)
        new_file.write_text(doc_content)
        files_written.append(new_file)

    return files_written


def filter_own_templates(files: list[Path]) -> list[Path]:
    """Filter out subchart templates, keeping only our own."""
    return [f for f in files if "/charts/" not in str(f)]


def run_yamllint(files: list[Path]) -> int:
    """Run yamllint on the given files. Returns exit code."""
    if not files:
        print("✅ No templates to lint")
        return 0

    try:
        # Import yamllint here so we get better error if it's missing
        import yamllint.cli

        # Build yamllint arguments
        args = ["-c", YAMLLINT_CONFIG] + [str(f) for f in files]

        # Run yamllint
        return yamllint.cli.run(args)
    except ImportError:
        print("❌ yamllint not found. Installing via uv...")
        sys.exit(1)


def main():
    try:
        subprocess.run(
            ["helm", "lint", PATH_TO_CHART],
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as e:
        print("  ❌ Helm lint failed:")
        print(e.stderr.decode())
        return 1

    # Render templates
    rendered_yaml = render_helm_templates()

    # Split into individual files
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_path = Path(tmpdir)
        files = split_yaml_to_files(rendered_yaml, temp_path)

        # Filter to only our templates (not subcharts)
        our_files = filter_own_templates(files)

        if not our_files:
            print("  ⚠️  No templates found to lint")
            return 0

        # Run yamllint
        exit_code = run_yamllint(our_files)

        if exit_code != 0:
            print("  ❌ yamllint found issues")

        return exit_code


if __name__ == "__main__":
    sys.exit(main())
