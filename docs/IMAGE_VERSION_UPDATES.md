# Image Version Update Pre-commit Hook

## Overview

Automated system for keeping container image versions up-to-date in `deployment-tool/defaults.yaml`.

## How It Works

1. **Pre-commit Hook**: When you modify `defaults.yaml` and commit, the hook automatically runs
2. **Registry Check**: Script queries quay.io and ghcr.io for the latest semantic version tags
3. **Version Update**: If newer versions are found, `defaults.yaml` is automatically updated
4. **Commit Blocked**: The commit fails so you can review the changes
5. **Review & Commit**: You review the updated versions, add the file, and commit again

## Workflow Example

```bash
# 1. You modify something in defaults.yaml
vim deployment-tool/defaults.yaml

# 2. Try to commit
git add deployment-tool/defaults.yaml
git commit -m "Update configuration"

# 3. Pre-commit hook runs and finds updates
# Output:
#   Checking for image updates...
#   api: 2.20.1 → 2.21.0
#   web: 0.40.0 → 0.41.0
#   ✓ Updated deployment-tool/defaults.yaml
#   ⚠ Image versions were updated. Please review and commit the changes.

# 4. Review the automatic updates
git diff deployment-tool/defaults.yaml

# 5. If changes look good, add and commit again
git add deployment-tool/defaults.yaml
git commit -m "Update configuration and image versions"
```

## Manual Usage

You can also run the update script manually:

```bash
# Check for updates without modifying files
./scripts/update-image-versions.py --check-only

# Update defaults.yaml
./scripts/update-image-versions.py

# Verbose mode (shows all API calls and tags)
./scripts/update-image-versions.py --verbose
```

## Authentication

For **private repositories**, the script needs authentication tokens:

### Quay.io Private Repositories

1. Log in to quay.io
2. Go to Account Settings → Robot Accounts or CLI Password
3. Generate a token with read permissions
4. Set environment variable:

```bash
export QUAY_TOKEN="your_bearer_token_here"
```

### GitHub Container Registry

1. Go to GitHub Settings → Developer settings → Personal access tokens
2. Generate token with `read:packages` scope
3. Set environment variable:

```bash
export GITHUB_TOKEN="ghp_your_token_here"
```

## Configuration

Edit `scripts/update-image-versions.py` to add or modify images:

```python
IMAGE_CONFIGS = {
    "api": {
        "registry": "quay.io",
        "repository": "octopize/services-api",
        "pattern": r"^\d+\.\d+\.\d+$",  # Semantic versioning
    },
    # Add more images here...
}
```

## Monitored Images

| Image | Registry | Current | Pattern |
|-------|----------|---------|---------|
| api | quay.io/octopize/services-api | 2.20.1 | x.y.z |
| web | quay.io/octopize/avatar-web | 0.40.0 | x.y.z |
| pdfgenerator | quay.io/octopize/pdfgenerator | latest | x.y.z |
| seaweedfs | quay.io/octopize/seaweedfs-chart | 0.2.0 | x.y.z |
| authentik | ghcr.io/goauthentik/server | 2025.10.2 | yyyy.m.p |

## Bypassing the Hook

**Not recommended**, but if you need to skip the check:

```bash
git commit --no-verify -m "Your message"
```

## Troubleshooting

### "401 Unauthorized" errors

**Cause**: Trying to access private repositories without authentication.

**Solution**: Set `QUAY_TOKEN` and/or `GITHUB_TOKEN` environment variables (see Authentication section above).

### Hook doesn't run

**Cause**: Pre-commit hooks not installed.

**Solution**:
```bash
pip install pre-commit
pre-commit install
```

### Updates not detected

**Possible causes**:
- No newer versions exist on the registry
- Version pattern doesn't match tag format
- Network connectivity issues

**Debug**:
```bash
./scripts/update-image-versions.py --verbose --check-only
```

This shows all tags fetched and helps identify pattern mismatches.

### Script fails to run

**Cause**: Missing Python dependencies.

**Solution**:
```bash
# Install dependencies
pip install pyyaml requests

# Or use uv (installs dependencies automatically)
uv run scripts/update-image-versions.py
```

## CI/CD Integration

You can also run this in CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
- name: Check for image updates
  run: |
    pip install pyyaml requests
    python scripts/update-image-versions.py --check-only
  env:
    QUAY_TOKEN: ${{ secrets.QUAY_TOKEN }}
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

## Files Modified

- `.pre-commit-config.yaml` - Added `update-image-versions` hook
- `scripts/update-image-versions.py` - Main update script
- `scripts/README.md` - Detailed script documentation
- `README.md` - Added development section
- `.gitignore` - Added Python and environment patterns

## Future Enhancements

Potential improvements:
- Support for Docker Hub registry
- Automatic pull request creation for updates
- Configurable version constraints (e.g., only patch updates)
- Notification system for major version changes
- Integration with Dependabot-style update workflows
