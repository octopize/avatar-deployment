# Scripts

Automation scripts for the Avatar deployment repository.

## sync-templates.py

Synchronizes Authentik email templates and branding assets from the source of truth (`common/authentik-templates/` and `common/authentik-branding/`) to deployment targets (Helm chart and Docker Compose).

### Usage

```bash
# Dry run - show what would be synced without making changes
./scripts/sync-templates.py --dry-run --verbose

# Sync files for real
./scripts/sync-templates.py

# Verbose output
./scripts/sync-templates.py --verbose
```

### Pre-commit Hook

This script runs automatically when files in `common/` are modified to ensure templates stay synchronized across deployment targets.

### What It Syncs

- **Email templates** (`*.html`):
  - From: `common/authentik-templates/`
  - To: `services-api-helm-chart/templates-files/` and `docker/authentik/custom-templates/`

- **Branding assets** (favicon.ico, logo.png):
  - From: `common/authentik-branding/`
  - To: `services-api-helm-chart/branding/` and `docker/authentik/branding/`

---

## validate-authentik-blueprint.py

Validates the Authentik blueprint template to ensure it follows best practices and can be successfully deployed.

### Usage

```bash
# Run all validations
python scripts/validate-authentik-blueprint.py
```

### Pre-commit Hook

This script runs automatically when the blueprint template (`docker/templates/authentik/octopize-avatar-blueprint.yaml`) is modified.

### Validations Performed

1. **No database PKs** - Ensures no primary key fields remain
2. **No managed flags** - Checks for managed field removal
3. **No UUIDs** - Verifies no hard-coded UUIDs exist
4. **No blueprint IDs** - Ensures use of `!Find` instead of blueprint IDs
5. **No !KeyOf usage** - Enforces `!Find` pattern
6. **All placeholders documented** - Verifies template variables are documented
7. **Injection script works** - Tests that the template can be populated with values

---

## check-yaml.py

Custom YAML syntax checker with ignore file support. Validates YAML files while respecting patterns defined in `.check-yaml-ignore`.

### Usage

**Run manually:**
```bash
# Check specific files
uv run scripts/check-yaml.py file1.yaml file2.yaml

# Allow custom YAML tags (like Authentik's !Find, !KeyOf)
uv run scripts/check-yaml.py --unsafe file.yaml

# Use custom ignore file
uv run scripts/check-yaml.py --ignore-file custom-ignore.txt *.yaml
```

### Pre-commit Hook

This script runs automatically via pre-commit on all YAML files. Files matching patterns in `.check-yaml-ignore` are skipped.

### Ignore Patterns

The `.check-yaml-ignore` file uses patterns similar to `.gitignore`:

```
# Exact file matches
docker/templates/authentik/octopize-avatar-blueprint.yaml

# Glob patterns
deployment-tool/tests/fixtures/*/expected/authentik/octopize-avatar-blueprint.yaml

# Directory patterns (trailing slash)
services-api-helm-chart/templates/
```

### Why Not Use Standard check-yaml?

The standard `check-yaml` from `pre-commit/pre-commit-hooks` fails on:
- **Authentik blueprints** - Use custom YAML tags like `!Find`, `!KeyOf`, `!Context`
- **Helm templates** - Contain Go template syntax that isn't valid YAML
- **Jinja2 templates** - Use `{{ }}` syntax within YAML

This custom checker allows excluding these special cases while still validating regular YAML files.

### Dependencies

- Python 3.8+
- `pyyaml` - YAML parsing (automatically installed by `uv run`)

---

## update-image-versions.py

Automatically checks container registries (quay.io, ghcr.io) for the latest semantic version tags of Octopize images and updates [`deployment-tool/defaults.yaml`](../deployment-tool/defaults.yaml).

### Usage

**Run manually:**
```bash
# Check for updates without modifying files
./scripts/update-image-versions.py --check-only

# Update defaults.yaml with latest versions
./scripts/update-image-versions.py

# Verbose output showing all fetched tags
./scripts/update-image-versions.py --verbose
```

**Run with uv (recommended):**
```bash
uv run scripts/update-image-versions.py --verbose
```

**For private repositories**, set authentication tokens:
```bash
# Quay.io private repositories
export QUAY_TOKEN="your_quay_bearer_token"

# GitHub Container Registry private repositories
export GITHUB_TOKEN="your_github_personal_access_token"

# Then run the script
./scripts/update-image-versions.py --verbose
```

### Pre-commit Hook

This script runs automatically as a pre-commit hook when `defaults.yaml` is modified. It will:

1. Check quay.io and ghcr.io for the latest versions
2. Update `defaults.yaml` if newer versions are available
3. Fail the commit if updates were made (so you can review the changes)

**To bypass the hook** (not recommended):
```bash
git commit --no-verify
```

### Monitored Images

The script checks the following images:

| Image | Registry | Repository | Version Pattern |
|-------|----------|------------|-----------------|
| api | quay.io | octopize/services-api | Semantic (e.g., 2.20.1) |
| web | quay.io | octopize/avatar-web | Semantic (e.g., 0.40.0) |
| pdfgenerator | quay.io | octopize/pdfgenerator | Semantic (e.g., 1.2.3) |
| seaweedfs | quay.io | octopize/seaweedfs-chart | Semantic (e.g., 0.2.0) |
| authentik | ghcr.io | goauthentik/server | Year.minor.patch (e.g., 2025.10.2) |

### How It Works

1. Queries the registry API to fetch all available tags
2. Filters tags matching semantic versioning patterns
3. Sorts by version number and selects the latest
4. Compares with current version in `defaults.yaml`
5. Updates the file if a newer version is found

### Adding New Images

To monitor additional images, edit `IMAGE_CONFIGS` in the script:

```python
IMAGE_CONFIGS = {
    "your-image": {
        "registry": "quay.io",  # or "ghcr.io"
        "repository": "org/repo-name",
        "pattern": r"^\d+\.\d+\.\d+$",  # Regex for valid version tags
    },
}
```

### Troubleshooting

**No tags found:**
- Check if the repository name is correct
- Verify the repository is public (private repos require authentication)
- Check network connectivity to the registry

**Version not updating:**
- Ensure the version pattern regex matches the tag format
- Use `--verbose` to see all available tags
- Check if newer versions exist on the registry

**Pre-commit hook fails:**
- This is expected when updates are found
- Review the changes with `git diff deployment-tool/defaults.yaml`
- Stage the updated file: `git add deployment-tool/defaults.yaml`
- Retry the commit

### Dependencies

- Python 3.8+
- `pyyaml` - YAML file parsing
- `requests` - HTTP requests to registry APIs

Install with:
```bash
pip install pyyaml requests
```

Or use `uv` which installs dependencies automatically.
