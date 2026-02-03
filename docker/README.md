# Docker Deployment

## Quick Start (Recommended)

Use the deployment tool to automatically download templates and generate configuration:

```bash
# Install the tool
pip install octopize-avatar-deploy

# Run interactive configuration
octopize-avatar-deploy --output-dir /app/avatar

# Start services
cd /app/avatar
docker compose down --volumes --remove-orphans  # Clean up any old deployments
docker compose up -d
```

See [deployment-tool/README.md](../deployment-tool/README.md) for full documentation.

## Manual Deployment (Advanced)

For manual configuration, see [deploying-on-single-instance.md](./deploying-on-single-instance.md).
