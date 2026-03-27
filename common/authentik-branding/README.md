# Authentik Branding Assets

This directory contains the runtime branding assets for Authentik deployments.

**⚠️ Source of truth**: edit files here, not in generated or deployment-specific directories.

## Files

- `favicon.ico` - Browser favicon, ideally `16x16` or `32x32`
- `logo.png` - Authentik UI logo, ideally a transparent PNG with modest width

Flow colours are defined in `common/authentik-blueprint/octopize-avatar-blueprint.yaml`, not as branding asset files. The discarded `background_image` asset is no longer part of the setup.

## Quick Start

1. Replace `favicon.ico` and/or `logo.png` here.
2. Run `./scripts/sync-templates.py` from the repo root.
3. Redeploy Authentik:
   - Docker Compose: restart `authentik_server` and `authentik_worker` in the deployment directory.
   - Helm: package and deploy the updated chart.

## Synced Targets

After running `./scripts/sync-templates.py`, these files are copied to:

- `docker/authentik/branding/`
- `services-api-helm-chart/static/branding/`

Never edit those copies directly.

See [SETUP.md](./SETUP.md) for the full workflow, deployment details, and troubleshooting.
