# avatar-deployment

This repo contains deployment configurations for the avatar software.

## Documentation

Refer to the link provided by the Octopize team.

## Development

### Pre-commit Hooks

This repository uses pre-commit hooks to maintain code quality and consistency:

```bash
# Install pre-commit hooks
pip install pre-commit
pre-commit install

# Run hooks manually
pre-commit run --all-files
```

**Included hooks:**
- **Authentik template sync** - Synchronizes email templates from `common/` to deployment targets
- **Image version updates** - Checks container registries for latest versions and updates `docker/deployment-tool/defaults.yaml`
- **Standard checks** - Trailing whitespace, YAML validation, merge conflicts, etc.

See [`.pre-commit-config.yaml`](.pre-commit-config.yaml) for full configuration.

For details on the image version update script, see [`scripts/README.md`](scripts/README.md).

## Contact and support

Reach out to help@octopize.io

For more information, check out www.octopize.io

## Licence

This repo is available under the Apache License v2.
