# Authentik Branding Assets

This directory contains branding assets for authentik deployments.

**⚠️ SOURCE OF TRUTH**: Edit files HERE, not in deployment-specific directories.

## Files

- `favicon.ico` - Browser favicon (recommended: 32x32 or 16x16 pixels)
- `logo.png` - Authentik UI logo (recommended: max-width 300px, transparent background)

## Quick Start

1. **Replace assets**: Copy your favicon.ico and logo.png into this directory
2. **Sync to Helm** (if using Kubernetes): Run `./sync-templates.py` from repo root
3. **Deploy**:
   - Docker: `cd docker && docker-compose restart authentik_server authentik_worker`
   - Helm: `just push-helm-chart`

## Full Documentation

See [SETUP.md](./SETUP.md) for complete setup instructions, deployment workflows, and troubleshooting.

## File Locations

### This Directory (Source)
```
common/authentik-branding/
├── favicon.ico          ← Edit here
├── logo.png            ← Edit here
├── README.md           ← This file
└── SETUP.md            ← Full documentation
```

### Docker Compose (Direct Mount)
Files are mounted directly from this directory - no copying needed.

### Helm (Synced Copy)
Files are copied to `services-api-helm-chart/branding/` via `sync-templates.py`, then packaged into a ConfigMap during `helm package`.

**Important**: Never edit files in `services-api-helm-chart/branding/` - always edit here and sync.
