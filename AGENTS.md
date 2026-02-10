# AI Agents Configuration

**Project**: Avatar Deployment Infrastructure  
**Purpose**: Multi-environment deployment configs for Octopize Avatar platform (Kubernetes Helm + Docker Compose)

**Important**: Do NOT create summary documents or extensive documentation after completing tasks unless explicitly requested by the user. Keep responses concise and focused on the task at hand.

## Testing Requirements

**CRITICAL**: Always run the full test suite after making any code modifications:

```bash
cd deployment-tool
just test-all  # Or: uv run pytest
```

Verify all tests pass before considering the work complete. This applies to:
- Source code changes in `src/`
- Test modifications in `tests/`
- Configuration changes that affect behavior
- Fixture updates

## Architecture Overview

This repository manages deployments for the Avatar platform using two distinct deployment strategies:

1. **Kubernetes/Helm** (`services-api-helm-chart/`) - Production clusters with authentik SSO
2. **Docker Compose** (`docker/`) - Single-instance deployments

**Critical Principle**: Templates sync from `common/authentik-templates/` → deployment targets via `scripts/sync-templates.py`

### Component Structure

- **Avatar API** (Python/FastAPI) - Main application backend
- **Avatar Web** (Next.js) - Frontend client  
- **PDF Generator** - Document rendering service
- **Authentik** - SSO/authentication (Helm subchart dependency)
- **Storage Backend** - S3-compatible (SeaweedFS or cloud)

---

## Build & Deployment Workflows

### Tool Selection: just vs make vs helm

**Use `just` (justfile)** for all Helm operations:

```bash
just lint              # Lint Helm chart + rendered YAML
just template          # Render templates without installing
just install           # Install to local cluster
just push-helm-chart   # Package + push to quay.io/octopize/helm/services-api
```

**Use `make` for**:

- Docker compose workflows: `make secrets-with-email-auth`
- Legacy helm operations (being migrated to just)

**Direct `helm` commands** - Avoid unless debugging; use just wrappers

### Critical Helm Commands

Located in [helm.just](helm.just):

- `just lint` - Validates both Helm syntax AND rendered YAML consistency via yamllint
- `just update-dependencies` - Pulls authentik subchart (run before packaging)
- Custom `split-yaml` recipe extracts individual manifests for targeted linting

### Template Synchronization Workflow

**Source of Truth**: `common/` directory

When modifying email templates, branding, or the blueprint:

```bash
# 1. Edit files in common/authentik-templates/, common/authentik-branding/, or common/authentik-blueprint/
# 2. Sync to deployment targets
./scripts/sync-templates.py [--dry-run] [--verbose]

# This copies files to:
#   - services-api-helm-chart/static/emails/
#   - services-api-helm-chart/static/branding/
#   - services-api-helm-chart/static/blueprint/
#   - docker/authentik/custom-templates/
#   - docker/authentik/branding/
#   - docker/templates/authentik/
```

**How it works**:

- Helm chart uses `.Files.Glob "static/emails/*.html"` in [authentik-custom-templates-configmap.yaml](services-api-helm-chart/templates/authentik-custom-templates-configmap.yaml)
- Django template syntax (`{{ url }}`) is preserved as raw content (NOT evaluated by Helm)
- Docker compose mounts `custom-templates/` directly to authentik container

---

## Configuration Patterns

### Values.yaml Structure

[services-api-helm-chart/values.yaml](services-api-helm-chart/values.yaml) uses **flat structure** (not nested):

```yaml
# API config at top level (legacy pattern)
baseUrl: https://avatar.yourcompany.com/api
dbHost: 127.0.0.1

# Nested subsections for other components
web:
  config:
    storageEndpointPublicHost: "..."
gcp:
  useGCP: false
```

**Why**: Pulumi integration expects flat API config (TODO comment indicates future refactor needed)

### Environment-Specific Overrides

- Chart version in [Chart.yaml](services-api-helm-chart/Chart.yaml) follows semver
- Tag releases: `just tag 0.0.29` → creates `services-api-helm-chart-v0.0.29` git tag
- Version bump pattern: Increment Chart.yaml version, commit, then tag

### Docker Secrets Management

Secrets stored in `.secrets/` directory (gitignored). Generate via:

```bash
cd docker/
make secrets-with-email-auth     # For email-based auth
make secrets-with-username-auth  # For username-based auth
```

Pattern: Python one-liner generates secrets → saved to individual files

```bash
python3 -c "import secrets; print(secrets.token_hex())" > .secrets/db_password
```

See [docker/deploying-on-single-instance.md](docker/deploying-on-single-instance.md) for full deployment workflow.

---

## Specialized Agents

### Authentik Email Templates

**Trigger**: Working with authentication emails in `common/authentik-templates/`  
**Skill Reference**: [.claude/skills/authentik-email-templates/SKILL.md](.claude/skills/authentik-email-templates/SKILL.md)

### Deployment Tool Steps

**Trigger**: Adding new configuration steps to the deployment tool  
**Skill Reference**: [.claude/skills/deployment-tool-steps/SKILL.md](.claude/skills/deployment-tool-steps/SKILL.md)

### Key Constraints

- **Django template syntax**: Use `{{ user.name }}`, `{{ url }}` (see [.claude/skills/authentik-email-templates/references/authentik-variables.md](.claude/skills/authentik-email-templates/references/authentik-variables.md))
- **Inline CSS only** - Email client compatibility requirement
- **Octopize brand colors**: Teal gradients (#38f9d7, #43e97b) per [.claude/skills/authentik-email-templates/references/color-schemes.md](.claude/skills/authentik-email-templates/references/color-schemes.md)
- **Business casual tone, no emojis**
- **Always provide plain text URL** alongside buttons

### Workflow

1. Edit/create in `common/authentik-templates/email_*.html`
2. Run `./scripts/sync-templates.py` to propagate changes
3. Templates deployed via ConfigMap (Helm) or volume mount (Docker)

---

## Common Pitfalls

1. **Editing deployment targets directly** - Always edit `common/authentik-templates/`, never `static/emails/` or `docker/authentik/custom-templates/`
2. **Forgetting helm dependency update** - Required before `just push-helm-chart` to include latest authentik chart
3. **Using `latest` image tags** - Pin specific versions in values.yaml (see avatarServiceApiVersion)
4. **Helm template variable confusion** - Authentik templates use `{{ }}` for Django, Helm uses `{{ .Values }}` - they don't interfere because `.Files.Glob` loads raw content


---

## Docker Deployment Tool Testing

**Trigger**: Working with tests in `deployment-tool/tests/`  
**Quick Reference**: [deployment-tool/tests/QUICK_REFERENCE.md](deployment-tool/tests/QUICK_REFERENCE.md)

### Testing Workflow

When adding or modifying tests for the deployment tool, **always consult QUICK_REFERENCE.md** first for:

- Running tests (`just test-deploy-tool` or `uv run pytest`)
- Creating new test cases with fixtures
- Updating expected output fixtures
- Using CLITestHarness for integration tests
- Available pytest fixtures and utilities

**Key Points**:

- Use `--template-from <path>` argument (not `--skip-download` or `--templates-dir`)
- Templates are always stored at `output-dir/.avatar-templates`
- Update fixtures with `AVATAR_DEPLOY_UPDATE_FIXTURES=1 uv run pytest`
- Test patterns documented in QUICK_REFERENCE.md with working examples

---

## Project File Map

```
├── common/authentik-templates/        ← SOURCE OF TRUTH for email templates
├── common/authentik-branding/         ← SOURCE OF TRUTH for branding assets
├── common/authentik-blueprint/        ← SOURCE OF TRUTH for authentik blueprint
├── services-api-helm-chart/           ← Kubernetes deployment
│   ├── Chart.yaml                     ← Version (bump on changes)
│   ├── values.yaml                    ← Config (flat structure for API)
│   ├── templates/                     ← Kubernetes manifests
│   │   └── authentik-custom-templates-configmap.yaml  ← Template loader
│   └── static/                        ← Synced from common/ (DO NOT EDIT)
│       ├── emails/                    ← Email templates (*.html)
│       ├── branding/                  ← Branding assets (favicon, logo)
│       └── blueprint/                 ← Authentik blueprint (*.yaml)
├── docker/                            ← Single-instance deployment
│   ├── Makefile                       ← Secret generation targets
│   ├── docker-compose.yml             ← Service definitions
│   └── authentik/custom-templates/    ← Synced from common/ (DO NOT EDIT)
├── deployment-tool/                   ← Deployment configuration tool
│   ├── src/octopize_avatar_deploy/    ← Source code
│   │   ├── steps/                     ← Deployment steps (add new steps here)
│   │   ├── configure.py               ← Main configurator (DEFAULT_STEP_CLASSES)
│   │   └── defaults.yaml              ← Default configuration values
│   ├── tests/                         ← Test suite with fixtures
│   │   ├── steps/                     ← Unit tests for steps
│   │   ├── integration/               ← Integration tests
│   │   └── QUICK_REFERENCE.md         ← Testing guide (READ THIS FIRST)
│   └── .avatar-templates/             ← Template files
│       ├── .env.template              ← Environment variables template
│       └── docker-compose.yml         ← Docker compose template
├── justfile & helm.just               ← Primary build tool (Helm operations)
├── scripts/                           ← Validation and utility scripts
│   ├── sync-templates.py              ← Template sync script (rsync or copy)
│   ├── validate-authentik-blueprint.py ← Blueprint template validator
│   ├── check-version-bump.py          ← Version bump verification
│   └── update-image-versions.py       ← Image version updater
├── .claude/skills/                    ← Agent skill definitions
│   ├── authentik-email-templates/     ← Email template creation skill
│   └── deployment-tool-steps/         ← Deployment step creation skill
└── AGENTS.md                          ← This file (agent configuration guide)
```
