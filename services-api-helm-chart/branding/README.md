# Authentik Branding Assets (Helm)

This directory contains branding assets synchronized from `common/authentik-branding/`.

**Do NOT edit files in this directory directly.**

Edit files in `common/authentik-branding/` and run `./sync-templates.py` to propagate changes.

## Files
- `favicon.ico` - Browser favicon
- `logo.png` - Authentik logo

## Synchronization
Run from repository root:
```bash
./sync-templates.py [--dry-run] [--verbose]
```
