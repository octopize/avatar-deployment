# Scripts

Automation scripts for the Avatar deployment repository.

## update-image-versions.py

Automatically checks container registries (quay.io, ghcr.io) for the latest semantic version tags of Octopize images and updates [`docker/deployment-tool/defaults.yaml`](../docker/deployment-tool/defaults.yaml).

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
- Review the changes with `git diff docker/deployment-tool/defaults.yaml`
- Stage the updated file: `git add docker/deployment-tool/defaults.yaml`
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
