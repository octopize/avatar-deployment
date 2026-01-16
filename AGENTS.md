# AI Agents Configuration

**Project**: Avatar Deployment Infrastructure  
**Purpose**: Multi-environment deployment configs for Octopize Avatar platform (Kubernetes Helm + Docker Compose)

## Architecture Overview

This repository manages deployments for the Avatar platform using two distinct deployment strategies:

1. **Kubernetes/Helm** (`services-api-helm-chart/`) - Production clusters with authentik SSO
2. **Docker Compose** (`docker/`) - Single-instance deployments

**Critical Principle**: Templates sync from `common/authentik-templates/` → deployment targets via `sync-templates.py`

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

**Source of Truth**: `common/authentik-templates/*.html`

When modifying email templates:

```bash
# 1. Edit templates in common/authentik-templates/
# 2. Sync to deployment targets
./sync-templates.py [--dry-run] [--verbose]

# This copies HTML files to:
#   - services-api-helm-chart/templates-files/
#   - docker/authentik/custom-templates/
```

**How it works**:

- Helm chart uses `.Files.Glob "templates-files/*.html"` in [authentik-custom-templates-configmap.yaml](services-api-helm-chart/templates/authentik-custom-templates-configmap.yaml)
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

## Specialized Agent: Authentik Email Templates

**Trigger**: Working with authentication emails in `common/authentik-templates/`  
**Skill Reference**: [skills/authentik-email-templates/SKILL.md](skills/authentik-email-templates/SKILL.md)

### Key Constraints

- **Django template syntax**: Use `{{ user.name }}`, `{{ url }}` (see [skills/authentik-email-templates/references/authentik-variables.md](skills/authentik-email-templates/references/authentik-variables.md))
- **Inline CSS only** - Email client compatibility requirement
- **Octopize brand colors**: Teal gradients (#38f9d7, #43e97b) per [skills/authentik-email-templates/references/color-schemes.md](skills/authentik-email-templates/references/color-schemes.md)
- **Business casual tone, no emojis**
- **Always provide plain text URL** alongside buttons

### Workflow

1. Edit/create in `common/authentik-templates/email_*.html`
2. Run `./sync-templates.py` to propagate changes
3. Templates deployed via ConfigMap (Helm) or volume mount (Docker)

---

## Common Pitfalls

1. **Editing deployment targets directly** - Always edit `common/authentik-templates/`, never `templates-files/` or `docker/authentik/custom-templates/`
2. **Forgetting helm dependency update** - Required before `just push-helm-chart` to include latest authentik chart
3. **Using `latest` image tags** - Pin specific versions in values.yaml (see avatarServiceApiVersion)
4. **Helm template variable confusion** - Authentik templates use `{{ }}` for Django, Helm uses `{{ .Values }}` - they don't interfere because `.Files.Glob` loads raw content

---

## Adding New Capabilities

To add new specialized agent skills:

1. Create skill directory: `skills/[skill-name]/`
2. Define skill per [skill-creator.md](skill-creator.md)
3. Add assets in `skills/[skill-name]/assets/`
4. Add references in `skills/[skill-name]/references/`
5. Document agent capabilities in this file

---

## Project File Map

```
├── common/authentik-templates/        ← SOURCE OF TRUTH for email templates
├── services-api-helm-chart/           ← Kubernetes deployment
│   ├── Chart.yaml                     ← Version (bump on changes)
│   ├── values.yaml                    ← Config (flat structure for API)
│   ├── templates/                     ← Kubernetes manifests
│   │   └── authentik-custom-templates-configmap.yaml  ← Template loader
│   └── templates-files/               ← Synced from common/ (DO NOT EDIT)
├── docker/                            ← Single-instance deployment
│   ├── Makefile                       ← Secret generation targets
│   ├── docker-compose.yml             ← Service definitions
│   └── authentik/custom-templates/    ← Synced from common/ (DO NOT EDIT)
├── justfile & helm.just               ← Primary build tool (Helm operations)
├── sync-templates.py                  ← Template sync script (rsync or copy)
└── skills/                            ← Agent skill definitions
```
