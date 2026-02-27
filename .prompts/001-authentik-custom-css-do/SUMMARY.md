# Authentik Custom CSS — Octopize Brand

Added custom CSS support for authentik SSO with Octopize teal branding, applied to all authentication flows via the existing common/ → sync-templates.py → deployment targets pattern.

## Files Created

- `common/authentik-css/custom.css` — Source of truth for Octopize brand CSS
- `services-api-helm-chart/templates/authentik-custom-css-configmap.yaml` — Helm ConfigMap for CSS
- `services-api-helm-chart/static/css/custom.css` — Synced copy (do not edit directly)
- `docker/authentik/css/custom.css` — Synced copy (do not edit directly)

## Files Modified

- `scripts/sync-templates.py` — Added Custom CSS AssetCategory
- `services-api-helm-chart/values.yaml` — Added custom-css volume + volumeMount to worker and server
- `common/authentik-blueprint/octopize-avatar-blueprint.yaml` — Added `branding_custom_css` field
- `docker/templates/docker-compose.yml.template` — Added CSS volume mount to authentik_server and authentik_worker
- `deployment-tool/src/octopize_avatar_deploy/download_templates.py` — Added `authentik/css/custom.css` to REQUIRED_FILE_MANIFEST
- `deployment-tool/src/octopize_avatar_deploy/configure.py` — Added CSS copy block after branding copy
- `docker/templates/.template-version` — Bumped from 0.23.0 to 0.24.0
- `deployment-tool/tests/fixtures/` — Updated all affected test fixtures

## Test Status

320 tests pass. 2 pre-existing failures in `test_nginx.py` (unrelated to this change).

## Next Step

Deploy to staging and visually verify all authentication flows display Octopize teal branding.
