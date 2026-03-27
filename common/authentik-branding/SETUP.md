# Authentik Branding Setup Guide

This guide explains how Authentik branding works in this repository now that flow backgrounds are configured with colors in the blueprint instead of a separate background image asset.

## Overview

Runtime branding assets live in `common/authentik-branding/` and are synced to Docker Compose and Helm targets:

- `favicon.ico`
- `logo.png`

Visual flow colours are configured in `common/authentik-blueprint/octopize-avatar-blueprint.yaml`.

## File Structure

```text
common/authentik-branding/                           ← SOURCE OF TRUTH
├── README.md
├── SETUP.md
├── favicon.ico
└── logo.png

docker/authentik/branding/                          ← Synced copy for Docker
services-api-helm-chart/static/branding/            ← Synced copy for Helm

docker/templates/docker-compose.yml.template        ← Mounts synced branding files
services-api-helm-chart/templates/
└── authentik-branding-configmap.yaml               ← Packages assets into ConfigMap
```

## Updating Branding

### 1. Add or replace the assets

Replace the files in `common/authentik-branding/`:

- `favicon.ico`: ideally `16x16` or `32x32`
- `logo.png`: ideally a transparent PNG sized reasonably for the Authentik UI

### 2. Sync to deployment targets

From the repository root:

```bash
./scripts/sync-templates.py
```

Useful variants:

```bash
./scripts/sync-templates.py --dry-run
./scripts/sync-templates.py --verbose
```

This copies branding assets to:

- `docker/authentik/branding/`
- `services-api-helm-chart/static/branding/`

### 3. Redeploy the target environment

#### Docker Compose

The Compose template mounts the synced files read-only into Authentik:

```yaml
- ./authentik/branding/favicon.ico:/media/public/favicon.ico:ro
- ./authentik/branding/logo.png:/media/public/brand_logo.png:ro
```

After syncing, restart the Authentik services in the deployment directory:

```bash
docker compose restart authentik_server authentik_worker
```

#### Helm / Kubernetes

The Helm chart packages the synced files from `services-api-helm-chart/static/branding/` into the `authentik-branding` ConfigMap, then mounts them into both the server and worker pods with `subPath`.

Typical workflow:

```bash
just lint
just push-helm-chart
```

Then deploy the updated chart version to the target cluster.

## Deployment Notes

### Docker Compose

The branding files used by Compose are not read directly from `common/authentik-branding/`; they come from the synced `docker/authentik/branding/` directory. If you update the source files but skip the sync step, the running deployment will keep the old assets.

### Helm / Kubernetes

The branding files are synced into `services-api-helm-chart/static/branding/` and packaged into the ConfigMap used by Authentik:

```yaml
binaryData:
  favicon.ico: {{ .Files.Get "static/branding/favicon.ico" | b64enc | quote }}
  logo.png: {{ .Files.Get "static/branding/logo.png" | b64enc | quote }}
```

Those files are mounted with `subPath` so only the favicon and logo are overridden, not the whole `/media/public/` directory.

## Colors and backgrounds

The login and self-service flow backgrounds are now handled in the Authentik blueprint CSS, using light and dark background colors.

That means:

- there is no `background_image` branding asset to maintain anymore
- branding asset work is limited to `favicon.ico` and `logo.png`
- visual background tweaks belong in `common/authentik-blueprint/octopize-avatar-blueprint.yaml`

## Troubleshooting

If branding changes do not appear:

1. Confirm the files were updated in `common/authentik-branding/`.
2. Run `./scripts/sync-templates.py --verbose`.
3. Confirm the synced copies were updated in `docker/authentik/branding/` or `services-api-helm-chart/static/branding/`.
4. Restart or redeploy Authentik.
5. Clear the browser cache.

If the issue is Helm-specific:

1. Check that `services-api-helm-chart/static/branding/` contains the new files.
2. Confirm the rendered chart still includes the `authentik-branding` ConfigMap.
3. Make sure the chart version and deployment were updated, so the cluster is not still running an older release.

If the issue is visual background styling rather than favicon/logo:

1. Check `common/authentik-blueprint/octopize-avatar-blueprint.yaml` instead of `common/authentik-branding/`.
2. Re-run `./scripts/sync-templates.py` so the updated blueprint reaches its targets.
