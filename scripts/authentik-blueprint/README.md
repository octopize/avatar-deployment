# authentik-blueprint

Tools for working with Authentik SSO blueprints throughout the development lifecycle.

## Installation

```bash
# Install as a uv tool (used by `just` targets)
uv tool install scripts/authentik-blueprint

# Or in development mode
cd scripts/authentik-blueprint
uv pip install -e ".[dev]"
```

## Commands

All commands are exposed as subcommands of `authentik-blueprint`:

```
authentik-blueprint <subcommand> [options]
```

### `export` — Convert a raw UI export to a declarative blueprint

Converts an Authentik blueprint exported from the admin UI (which uses raw database PKs) into a portable declarative blueprint using `!Find` lookups and `!Context` / `!Env` tags.

Run this **once** when capturing a new blueprint from the admin UI.

```bash
authentik-blueprint export input-export.yaml common/authentik-blueprint/octopize-avatar-blueprint.yaml
# With validation after conversion:
authentik-blueprint export input-export.yaml output.yaml --validate --verbose
```

**via just:**
```bash
just blueprint-export input.yaml output.yaml
just blueprint-convert input.yaml   # exports + places in common/
```

---

### `validate` — Fast static checks (no network, no containers)

Runs a set of structural checks on the blueprint template:

- No raw database PKs or UUIDs
- No `managed:` flags
- All `[[PLACEHOLDER]]` variables are documented in the header
- No `authentik_core.user` entries
- Only Octopize groups are defined
- Known single-choice fields (`pkce`, etc.) have valid values

Run this **on every commit**. It completes in milliseconds.

```bash
authentik-blueprint validate common/authentik-blueprint/octopize-avatar-blueprint.yaml
authentik-blueprint validate --verbose common/authentik-blueprint/octopize-avatar-blueprint.yaml
```

**via just:**
```bash
just blueprint-validate common/authentik-blueprint/octopize-avatar-blueprint.yaml
```

---

### `schema-check` — Validate field choices against the Authentik source (no containers)

AST-parses the Authentik source tree to extract all `TextChoices` field definitions and checks that every plain-string field value in the blueprint is a valid choice.

Catches errors like `pkce: "['plain', 'S256']"` (a list-as-string) that `validate` only catches for fields in its `KNOWN_FIELD_CHOICES` list. `schema-check` covers all 65+ constrained fields across the entire codebase automatically.

The Authentik repo is **shallow-cloned at the specified version and cached** in `/tmp/authentik-<version>`. Subsequent runs use the cache. Requires `git` but no Docker or running containers.

Run this **when bumping the Authentik version** or when editing blueprint entries that use model-constrained fields.

```bash
# Shallow-clones authentik at version 2026.2.1 (cached after first run)
authentik-blueprint schema-check --authentik-version 2026.2.1

# Point at an existing checkout
authentik-blueprint schema-check --authentik-root /tmp/authentik-2026.2.1

# Custom blueprint path
authentik-blueprint schema-check --authentik-version 2026.2.1 \
    --blueprint path/to/blueprint.yaml
```

**via just:**
```bash
just blueprint-validate-schema 2026.2.1
just blueprint-validate-schema 2026.2.1 path/to/blueprint.yaml
```

---

### `verify-live` — Run the importer stepper in a live Authentik worker

Connects to a running Authentik worker (Docker or Kubernetes), runs the blueprint's entries one-by-one through the real importer in a rolled-back transaction, and fails if any entry is rejected by the serializer.

This is the **definitive check** — it exercises real Django serializers against actual configuration and catches errors that static analysis cannot:

- Broken `!KeyOf` / `!Find` references
- Foreign key failures
- Uniqueness violations
- Policy expression errors
- Any other runtime serializer error

> **Why `status: successful` is not enough.** Authentik marks a blueprint as `successful` even when individual entries fail — it silently skips the failing entry and continues. `verify-live` is the only reliable way to confirm every entry passed.

**Docker mode** (after `run-noninteractive-local.sh`):

```bash
# Auto-detect the running worker container
authentik-blueprint verify-live

# Explicit container name
authentik-blueprint verify-live --container avatar_local_abc123_authentik_worker-1
```

**Kubernetes mode:**

```bash
authentik-blueprint verify-live --kubeconfig /path/to/kubeconfig.yml
authentik-blueprint verify-live --kubeconfig /path/to/kubeconfig.yml --namespace staging
```

**via just:**
```bash
# Docker (after run-noninteractive-local.sh)
just verify-blueprint-local
just verify-blueprint-local --container my-container

# Kubernetes
just verify-blueprint-k8s /path/to/kubeconfig.yml
```

---

## When to use which

| Situation | Command |
|---|---|
| Before every commit | `just blueprint-validate` |
| After editing a constrained field (e.g. `pkce`, `designation`) | `just blueprint-validate-schema <version>` |
| After `run-noninteractive-local.sh` | `just verify-blueprint-local` |
| After deploying to staging or production | `just verify-blueprint-k8s <kubeconfig>` |
| Bumping the Authentik version | `just blueprint-validate-schema <new-version>` |
| Capturing a new blueprint from the admin UI | `just blueprint-export` / `just blueprint-convert` |

---

## Development

```bash
cd scripts/authentik-blueprint
uv pip install -e ".[dev]"
uv run pytest
```
