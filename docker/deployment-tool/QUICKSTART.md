# Quick Start Guide

## For System Administrators

### 1. Quick Installation (Interactive)

```bash
# Navigate to deployment tool
cd avatar-deployment/docker/deployment-tool

# Run the configurator with uv
uv run configure.py --output-dir /app/avatar

# Or with Python directly (requires pyyaml and jinja2 installed)
python configure.py --output-dir /app/avatar

# Follow the interactive prompts to configure your deployment
# Required: PUBLIC_URL and ENV_NAME
# Optional: Everything else has sensible defaults
```

### 2. Quick Installation (Automated)

```bash
# Create your configuration file  
cp config.example.yaml my-config.yaml
nano my-config.yaml  # Edit with your PUBLIC_URL and ENV_NAME (required)

# Run non-interactive deployment
uv run configure.py --config my-config.yaml --non-interactive --output-dir /app/avatar
```

### 3. Using Make (from docker directory)

```bash
cd avatar-deployment/docker

# Interactive configuration
make configure

# Non-interactive configuration
make configure-non-interactive CONFIG_FILE=deployment-tool/my-config.yaml
```

## What Happens

The tool will:
1. ✓ Install `uv` if not present
2. ✓ Generate `.env` file with your configuration
3. ✓ Generate `nginx/nginx.conf` with your domain
4. ✓ Create `.secrets/` directory with auto-generated secrets
5. ⚠ Create placeholder files for secrets requiring manual input

## After Running

### Required Manual Steps

1. **Fill in user-specific secrets** in `/app/avatar/.secrets/`:
   - `admin_emails` - Comma-separated admin email addresses
   - `db_name` - Database name (e.g., `avatar`)
   - `db_user` - Database user (e.g., `avataruser`)
   - `db_admin_user` - Database admin user (e.g., `postgres`)
   - `organization_name` - Your organization name
   - `authentik_database_name` - Authentik database name (e.g., `authentik`)
   - `authentik_database_user` - Authentik database user (e.g., `authentikuser`)
   - `telemetry_s3_access_key_id` - Provided by Octopize
   - `telemetry_s3_secret_access_key` - Provided by Octopize

   If using AWS SES for email:
   - `aws_mail_account_access_key_id` - Provided by Octopize
   - `aws_mail_account_secret_access_key` - Provided by Octopize

2. **Configure TLS certificates**:
   ```bash
   mkdir -p /app/avatar/tls/private
   # Copy your certificate files to /app/avatar/tls/
   ```

3. **Review generated files**:
   - Check `/app/avatar/.env` for any customizations
   - Verify `/app/avatar/nginx/nginx.conf` has correct domain

4. **Create Docker volume**:
   ```bash
   docker volume create avatar_postgres_data
   ```

5. **Copy docker-compose.yml**:
   ```bash
   cp avatar-deployment/docker/docker-compose.yml /app/avatar/
   ```

6. **Start the deployment**:
   ```bash
   cd /app/avatar
   docker compose up -d
   ```

## Command Reference

```bash
# Show help
python configure.py --help
# or: uv run configure.py --help

# Interactive mode with custom output directory
uv run configure.py --output-dir /custom/path

# Non-interactive with config file (requires PUBLIC_URL and ENV_NAME in config)
uv run configure.py --config my-config.yaml --non-interactive

# Username authentication instead of email
uv run configure.py --auth-type username

# Save configuration for reuse
uv run configure.py --save-config
```

## Troubleshooting

### "uv not found"
Install uv:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
```

Or use Python directly:
```bash
pip install pyyaml jinja2
python configure.py --output-dir /app/avatar
```

### "Permission denied"
```bash
chmod +x ./configure.py
```

### "No such file or directory: templates"
Make sure you're running from the deployment-tool directory:
```bash
cd avatar-deployment/docker/deployment-tool
uv run configure.py
```

### "Missing required fields: PUBLIC_URL, ENV_NAME"
In non-interactive mode, your config file must include PUBLIC_URL and ENV_NAME:
```yaml
PUBLIC_URL: avatar.example.com
ENV_NAME: mycompany-prod
```

### Want to re-generate configuration
The tool won't overwrite existing files. To regenerate:
```bash
# Backup existing files if needed
mv /app/avatar/.env /app/avatar/.env.backup

# Run configurator again
./bootstrap.sh --output-dir /app/avatar
```

## Advanced Usage

### Using as a Python Module

```python
from configure import DeploymentConfigurator
from pathlib import Path

config = {
    "PUBLIC_URL": "avatar.mycompany.com",
    "ENV_NAME": "mycompany-prod",
    # ... other settings
}

configurator = DeploymentConfigurator(
    templates_dir=Path("templates"),
    output_dir=Path("/app/avatar"),
    config=config
)

configurator.generate_configs()
configurator.create_secrets(auth_type="email")
```

### Validating Configuration

```bash
# Test the generated .env file
cd /app/avatar
docker compose config
```

## Support

- Full Documentation: [avatar-deployment/docker/deployment-tool/README.md](README.md)
- Installation Guide: https://docs.octopize.io/docs/deploying/self-hosted/installation
- Issues: https://github.com/octopize/avatar-deployment/issues
