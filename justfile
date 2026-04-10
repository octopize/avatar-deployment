import './helm.just'

default:
    @just -l


tag-helm VERSION:
    @git tag -s services-api-helm-chart-v{{VERSION}} -m "Release new services-api helm chart v{{VERSION}}"

# Bump patch version, commit Chart.yaml, create a signed tag, and push to OCI registry
ship-helm: release-helm push-helm-chart

# Bump patch version, commit Chart.yaml, and create a signed tag
release-helm:
    #!/usr/bin/env bash
    set -euo pipefail
    new_version=$(just bump-patch)
    git add services-api-helm-chart/Chart.yaml
    git commit -m "chore: bump helm chart version to $new_version"
    just tag-helm "$new_version"
    echo "✓ Released services-api-helm-chart v$new_version"

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

blueprint-convert INPUT_FILE OUTPUT_FILE="common/authentik-blueprint/octopize-avatar-blueprint.yaml" *ARGS: blueprint-install
    @uv tool run authentik-blueprint export \
        --validate \
        {{INPUT_FILE}} \
        {{OUTPUT_FILE}} \
        {{ARGS}}


blueprint-convert-staging: (blueprint-convert "docker/authentik/blueprints/staging-export.yaml")
