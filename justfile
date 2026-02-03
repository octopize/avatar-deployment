import './helm.just'

default:
    @just -l


tag VERSION:
    @git tag -s services-api-helm-chart-v{{VERSION}} -m "Release new services-api helm chart v{{VERSION}}"

setup-precommit:
    #/usr/bin/env bash
    set -euo pipefail

    pip install pre-commit
    pre-commit install
    @echo "✓ Pre-commit hooks installed"

update-image-versions:
    uv run ./scripts/update-image-versions.py --verbose

check-image-versions:
    uv run ./scripts/update-image-versions.py --check-only --verbose
