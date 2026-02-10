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

# Blueprint tools
blueprint-install:
    @uv tool install --force --reinstall scripts/authentik-blueprint 2> /dev/null

blueprint-export *ARGS: blueprint-install
    @uv tool run authentik-blueprint export {{ARGS}}

blueprint-validate *ARGS: blueprint-install
    @uv tool run authentik-blueprint validate {{ARGS}}


blueprint-convert-staging: blueprint-install
    @uv tool run authentik-blueprint export \
        --validate \
        docker/authentik/blueprints/staging-export.yaml \
        common/authentik-blueprint/octopize-avatar-blueprint.yaml
