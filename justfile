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

    uvx pre-commit install
    @echo "✓ Pre-commit hooks installed"

update-image-versions:
    uv run ./scripts/update-image-versions.py --verbose

check-image-versions:
    uv run ./scripts/update-image-versions.py --check-only --verbose

# ─── Blueprint tools ──────────────────────────────────────────────────────────
# All subcommands live in scripts/authentik-blueprint (authentik-blueprint <cmd>).
# See scripts/authentik-blueprint/README.md for full documentation.
#
# Quick reference — when to use which:
#   blueprint-validate        → before every commit (instant, no network)
#   blueprint-validate-schema → after editing constrained fields or bumping Authentik version
#   verify-blueprint-local    → after run-noninteractive-local.sh
#   verify-blueprint-k8s      → after deploying to staging / production

blueprint-install:
    @uv tool install --force --reinstall scripts/authentik-blueprint 2> /dev/null

# Fast static checks: no PKs, no managed flags, known field choices valid.
# Run on every commit. No network or containers needed.
blueprint-validate *ARGS: blueprint-install
    @uv tool run authentik-blueprint validate {{ARGS}}

# Convert a raw blueprint export (with DB PKs) to a declarative !Find-based template.
blueprint-export *ARGS: blueprint-install
    @uv tool run authentik-blueprint export {{ARGS}}

# Export + validate + place in common/authentik-blueprint/.
blueprint-convert INPUT_FILE OUTPUT_FILE="common/authentik-blueprint/octopize-avatar-blueprint.yaml" *ARGS: blueprint-install
    @uv tool run authentik-blueprint export \
        --validate \
        {{INPUT_FILE}} \
        {{OUTPUT_FILE}} \
        {{ARGS}}

blueprint-convert-staging: (blueprint-convert "docker/authentik/blueprints/staging-export.yaml")

# Validate all single-choice field values against the Authentik source tree.
# Shallow-clones authentik at VERSION (cached in /tmp/authentik-VERSION).
# Run when bumping the Authentik version or editing model-constrained fields.
# No containers needed.
#
# Usage:
#   just blueprint-validate-schema 2026.2.1
#   just blueprint-validate-schema 2026.2.1 --blueprint path/to/blueprint.yaml
blueprint-validate-schema VERSION *ARGS: blueprint-install
    @uv tool run authentik-blueprint schema-check \
        --authentik-version {{VERSION}} \
        {{ARGS}}

# Run the importer stepper in the local Docker worker (auto-detects container).
# Run after `cd deployment-tool && bash run-noninteractive-local.sh`.
#
# Usage:
#   just verify-blueprint-local
#   just verify-blueprint-local --container my-container-name
verify-blueprint-local *ARGS: blueprint-install
    @uv tool run authentik-blueprint verify-live {{ARGS}}

# Run the importer stepper against a live Kubernetes deployment.
# Run after deploying to staging or production to confirm every blueprint entry passed.
#
# Usage:
#   just verify-blueprint-k8s /path/to/kubeconfig.yml
#   just verify-blueprint-k8s /path/to/kubeconfig.yml --namespace staging
verify-blueprint-k8s KUBECONFIG *ARGS: blueprint-install
    @uv tool run authentik-blueprint verify-live --kubeconfig {{KUBECONFIG}} {{ARGS}}
