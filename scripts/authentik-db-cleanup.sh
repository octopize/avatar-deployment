#!/usr/bin/env bash
# authentik-db-cleanup.sh
#
# Runs authentik-db-cleanup.py inside the authentik worker container to remove
# non-default objects (flows, stages, policies, prompts, brands, scope
# mappings) from a staging environment, then optionally restarts the worker so
# the production blueprint re-applies.
#
# Works with both Docker Compose and Kubernetes deployments.
#
# Usage:
#   ./scripts/authentik-db-cleanup.sh [OPTIONS]
#
# Options:
#   --live                  Actually delete (default: dry run)
#   --kubeconfig PATH       Use Kubernetes instead of Docker Compose
#   --container NAME        Override the worker container name (Docker Compose)
#   --restart               Restart the worker after cleanup to re-apply blueprint
#   -h, --help              Show this help
#
# Examples:
#   # Dry run against local Docker Compose (auto-detects the worker container)
#   ./scripts/authentik-db-cleanup.sh
#
#   # Live run against local Docker Compose
#   ./scripts/authentik-db-cleanup.sh --live
#
#   # Dry run against Kubernetes staging
#   ./scripts/authentik-db-cleanup.sh \
#       --kubeconfig avatar/infra/envs/scaleway/staging-kubeconfig.yml
#
#   # Live run against Kubernetes staging + restart worker
#   ./scripts/authentik-db-cleanup.sh \
#       --kubeconfig avatar/infra/envs/scaleway/staging-kubeconfig.yml \
#       --live --restart

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLEANUP_PY="$SCRIPT_DIR/authentik-db-cleanup.py"
REMOTE_PATH="/tmp/authentik-db-cleanup.py"

DRY_RUN=true
KUBECONFIG_PATH=""
CONTAINER_OVERRIDE=""
DO_RESTART=false

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
    case "$1" in
        --live)        DRY_RUN=false; shift ;;
        --kubeconfig)  KUBECONFIG_PATH="$2"; shift 2 ;;
        --container)   CONTAINER_OVERRIDE="$2"; shift 2 ;;
        --restart)     DO_RESTART=true; shift ;;
        -h|--help)
        sed -n '2,/^[^#]/{ /^# /s/^# \?//p }' "$0" | sed '/^-\{3,\}/d'
            exit 0
            ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

if [[ ! -f "$CLEANUP_PY" ]]; then
    echo "Error: cleanup script not found at $CLEANUP_PY" >&2
    exit 1
fi

DRY_RUN_ENV="$( [[ "$DRY_RUN" == true ]] && echo "true" || echo "false" )"

# ---------------------------------------------------------------------------
# Kubernetes mode
# ---------------------------------------------------------------------------
if [[ -n "$KUBECONFIG_PATH" ]]; then
    if ! command -v kubectl &>/dev/null; then
        echo "Error: kubectl not found in PATH" >&2
        exit 1
    fi

    echo "Mode: Kubernetes  (kubeconfig: $KUBECONFIG_PATH)"
    echo "Discovering worker pod..."

    WORKER_POD=$(kubectl --kubeconfig "$KUBECONFIG_PATH" get pods \
        -l "app.kubernetes.io/component=worker,app.kubernetes.io/name=authentik" \
        -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)

    if [[ -z "$WORKER_POD" ]]; then
        echo "Error: no authentik worker pod found" >&2
        exit 1
    fi
    echo "Worker pod: $WORKER_POD"

    echo "Copying cleanup script..."
    kubectl --kubeconfig "$KUBECONFIG_PATH" cp \
        "$CLEANUP_PY" "${WORKER_POD}:${REMOTE_PATH}"

    echo "Running cleanup (DRY_RUN=$DRY_RUN_ENV)..."
    kubectl --kubeconfig "$KUBECONFIG_PATH" exec "$WORKER_POD" \
        -- sh -c "DRY_RUN=$DRY_RUN_ENV ak shell -c \"exec(open('$REMOTE_PATH').read())\""

    if [[ "$DO_RESTART" == true ]]; then
        echo ""
        echo "Restarting worker to re-apply blueprint..."
        kubectl --kubeconfig "$KUBECONFIG_PATH" \
            rollout restart deployment/avatar-authentik-worker
        kubectl --kubeconfig "$KUBECONFIG_PATH" \
            rollout status deployment/avatar-authentik-worker
    fi

# ---------------------------------------------------------------------------
# Docker Compose mode
# ---------------------------------------------------------------------------
else
    if ! command -v docker &>/dev/null; then
        echo "Error: docker not found in PATH" >&2
        exit 1
    fi

    if [[ -n "$CONTAINER_OVERRIDE" ]]; then
        WORKER="$CONTAINER_OVERRIDE"
    else
        echo "Mode: Docker Compose  (auto-detecting worker container...)"
        WORKER=$(docker ps --filter "name=authentik_worker" --format "{{.Names}}" | head -1)
        if [[ -z "$WORKER" ]]; then
            echo "Error: no running container matching 'authentik_worker' found." >&2
            echo "Use --container NAME to specify it explicitly." >&2
            exit 1
        fi
    fi
    echo "Worker container: $WORKER"

    echo "Copying cleanup script..."
    docker cp "$CLEANUP_PY" "${WORKER}:${REMOTE_PATH}"

    echo "Running cleanup (DRY_RUN=$DRY_RUN_ENV)..."
    docker exec -e "DRY_RUN=$DRY_RUN_ENV" "$WORKER" \
        ak shell -c "exec(open('$REMOTE_PATH').read())"

    if [[ "$DO_RESTART" == true ]]; then
        echo ""
        echo "Restarting worker to re-apply blueprint..."
        # Derive compose project from container name (strip the service suffix)
        # e.g. avatar_local_3aa0-authentik_worker-1 -> avatar_local_3aa0
        PROJECT=$(echo "$WORKER" | sed 's/-authentik_worker.*//')
        COMPOSE_FILE=$(docker inspect "$WORKER" \
            --format '{{index .Config.Labels "com.docker.compose.project.working_dir"}}')
        if [[ -n "$COMPOSE_FILE" && -f "$COMPOSE_FILE/docker-compose.yml" ]]; then
            COMPOSE_PROJECT_NAME="$PROJECT" docker compose \
                -f "$COMPOSE_FILE/docker-compose.yml" restart authentik_worker
        else
            docker restart "$WORKER"
        fi
    fi
fi
