# Authentik Branding Setup Guide

This guide explains how to customize authentik's branding (favicon and logo) for both Docker Compose and Helm deployments.

## Overview

Custom branding assets are managed from a single source directory (`common/authentik-branding/`) and deployed to both environments:

- **Docker Compose**: Direct volume mounts from `common/authentik-branding/`
- **Helm/Kubernetes**: Copied to `services-api-helm-chart/branding/` via sync script, then packaged into ConfigMap

## File Structure

```
common/authentik-branding/          ← SOURCE OF TRUTH
├── README.md
├── favicon.ico                     ← Browser favicon (32x32 or 16x16 recommended)
└── logo.png                        ← UI logo (max-width 300px recommended)

docker/docker-compose.yml           ← Mounts directly from common/
services-api-helm-chart/
├── branding/                       ← Synced copy for Helm (DO NOT EDIT)
│   ├── README.md
│   ├── favicon.ico
│   └── logo.png
└── templates/
    └── authentik-branding-configmap.yaml  ← Packages assets into ConfigMap
```

## Setup Instructions

### 1. Add Your Branding Assets

Replace the placeholder files in `common/authentik-branding/`:

```bash
# Add your custom favicon (ICO format, 16x16 or 32x32)
cp /path/to/your/favicon.ico common/authentik-branding/

# Add your custom logo (PNG format, transparent background recommended)
cp /path/to/your/logo.png common/authentik-branding/
```

**Recommended specifications**:
- **favicon.ico**: 16x16 or 32x32 pixels, ICO format
- **logo.png**: PNG with transparent background, max-width 300px

### 2. Sync to Deployment Targets

For Helm deployments, run the sync script to copy branding assets:

```bash
# From repository root
./sync-templates.py --verbose

# Or dry-run to preview changes
./sync-templates.py --dry-run
```

This copies assets from `common/authentik-branding/` to `services-api-helm-chart/branding/`.

**Note**: Docker Compose doesn't need syncing - it mounts files directly.

### 3. Deploy Changes

#### Docker Compose

Restart the authentik services:

```bash
cd docker/
docker-compose restart authentik_server authentik_worker
```

The branding assets are mounted as read-only volumes:
```yaml
volumes:
  - ../common/authentik-branding/favicon.ico:/media/public/favicon.ico:ro
  - ../common/authentik-branding/logo.png:/media/public/brand_logo.png:ro
```

#### Helm/Kubernetes

Package and push the updated chart:

```bash
# Lint, package, and push to registry
just push-helm-chart

# Or manually
cd services-api-helm-chart/
helm package .
helm push services-api-helm-chart-*.tgz oci://quay.io/octopize/helm
```

Then upgrade your deployment:

```bash
helm upgrade avatar-deployment oci://quay.io/octopize/helm/services-api-helm-chart \
  --version <new-version> \
  --values your-values.yaml
```

## How It Works

### Docker Compose Implementation

The branding files are mounted directly into the authentik containers at runtime:

```yaml
# docker/docker-compose.yml
authentik_server:
  volumes:
    - ../common/authentik-branding/favicon.ico:/media/public/favicon.ico:ro
    - ../common/authentik-branding/logo.png:/media/public/brand_logo.png:ro

authentik_worker:
  volumes:
    - ../common/authentik-branding/favicon.ico:/media/public/favicon.ico:ro
    - ../common/authentik-branding/logo.png:/media/public/brand_logo.png:ro
```

The `:ro` flag makes mounts read-only for security.

### Helm Implementation

Branding assets are packaged into a ConfigMap using Helm's native file handling:

```yaml
# services-api-helm-chart/templates/authentik-branding-configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: authentik-branding
binaryData:
  favicon.ico: {{ .Files.Get "branding/favicon.ico" | b64enc | quote }}
  logo.png: {{ .Files.Get "branding/logo.png" | b64enc | quote }}
```

The ConfigMap is then mounted to both authentik server and worker pods using `subPath` to only overwrite specific files:

```yaml
# services-api-helm-chart/values.yaml
authentik:
  server:
    volumeMounts:
      - name: branding-assets
        mountPath: /media/public/favicon.ico
        subPath: favicon.ico
        readOnly: true
      - name: branding-assets
        mountPath: /media/public/brand_logo.png
        subPath: logo.png
        readOnly: true
```

**Why `subPath`?** Without it, mounting the ConfigMap would replace the entire `/media/public/` directory, removing all other authentik media files. Using `subPath` ensures we only override the specific branding files.

## Troubleshooting

### Branding not updating in Docker Compose

1. Ensure files exist in `common/authentik-branding/`
2. Restart the authentik services: `docker-compose restart authentik_server authentik_worker`
3. Check file permissions (should be readable)
4. Clear browser cache (Ctrl+Shift+R or Cmd+Shift+R)

### Branding not updating in Helm

1. Verify files were synced: `ls -la services-api-helm-chart/branding/`
2. Check if sync script ran successfully: `./sync-templates.py --verbose`
3. Ensure ConfigMap was created: `kubectl get configmap authentik-branding -o yaml`
4. Check pod mounts: `kubectl describe pod <authentik-pod-name>`
5. Verify chart version was bumped in `Chart.yaml`
6. Force pod restart: `kubectl rollout restart deployment authentik-server`

### Files show as placeholder in Helm

The `.Files.Get` function requires files to exist during `helm package`. Ensure:
1. Branding assets exist in `services-api-helm-chart/branding/`
2. Run `./sync-templates.py` before packaging
3. Check Helm packaging output for warnings

## Updating AGENTS.md

This branding setup follows the same pattern as email templates. Update [AGENTS.md](../AGENTS.md) to document:

```markdown
### Branding Assets Workflow

**Source of Truth**: `common/authentik-branding/{favicon.ico,logo.png}`

When modifying branding:

1. Edit assets in `common/authentik-branding/`
2. For Helm: Run `./sync-templates.py` to copy to `services-api-helm-chart/branding/`
3. For Docker: Files are mounted directly (no sync needed)
4. Deploy using `just push-helm-chart` (Helm) or `docker-compose restart` (Docker)
```

## Advanced: Adding More Branding Assets

To add additional branding files (e.g., background images):

1. **Add to source**: Place file in `common/authentik-branding/`
2. **Update sync script**: Add pattern to `get_branding_files()` in `sync-templates.py`
3. **Update ConfigMap**: Add entry to `authentik-branding-configmap.yaml`
4. **Update values.yaml**: Add volumeMount with appropriate subPath
5. **Run sync**: `./sync-templates.py`

Example for adding a background image:

```yaml
# In authentik-branding-configmap.yaml
binaryData:
  background.jpg: {{ .Files.Get "branding/background.jpg" | b64enc | quote }}

# In values.yaml (both server and worker)
volumeMounts:
  - name: branding-assets
    mountPath: /media/public/background.jpg
    subPath: background.jpg
    readOnly: true
```

## See Also

- [Email Templates Skill](../skills/authentik-email-templates/SKILL.md)
- [sync-templates.py](../sync-templates.py)
- [Authentik Media Documentation](https://docs.goauthentik.io/docs/installation/docker-compose#media)
