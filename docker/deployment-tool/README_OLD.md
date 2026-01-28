# Octopize Avatar Deployment Tool

Automated configuration tool for deploying Octopize Avatar platform using Docker Compose.

## Overview

This tool simplifies the deployment of Avatar by:
- **Downloading deployment templates** from GitHub (no need to clone the repo!)
- Automatically generating configuration files
- Creating secure random secrets
- **Providing deployment presets** (dev-mode, production, airgapped)
- Reducing manual configuration errors
- Supporting both interactive and non-interactive modes

## Architecture

**Standalone Package** - The tool is designed to be completely standalone:
- ✅ Core logic bundled in PyPI package (`configure.py`, `state_manager.py`, `defaults.yaml`)
- ✅ Templates downloaded on-demand from GitHub (`

## Quick Start

### Option 1: Using uvx (Recommended)

Once published to PyPI, you can run the tool directly:

```bash
# Run directly with uvx (will be available after PyPI publication)
uvx octopize-avatar-deploy --output-dir /app/avatar
```

### Option 2: From Source with uv

```bash
# Clone the repository
git clone --depth 1 --filter=blob:none --sparse https://github.com/octopize/avatar-deployment
cd avatar-deployment
git sparse-checkout set docker/deployment-tool

# Run with uv
cd docker/deployment-tool
uv run configure.py --output-dir /app/avatar
```

### Option 3: Using Python directly

```bash
# Install dependencies
pip install pyyaml jinja2

# Run the configurator
python configure.py --output-dir /app/avatar
```

## Usage

### Interactive Mode

Simply run the script and follow the prompts:

```bash
uv run configure.py --output-dir /app/avatar
# Or when published to PyPI:
# uvx octopize-avatar-deploy --output-dir /app/avatar
```

You'll be asked to provide:
- **Public URL (domain name)** - Required
- **Environment name** - Required
- Service versions (optional - defaults from defaults.yaml)
- Email configuration (optional - defaults to AWS)
- Telemetry preferences
- And more...

### Non-Interactive Mode

Use a configuration file for automated deployments:

```bash
# Create a config file
cat > my-config.yaml << EOF
PUBLIC_URL: avatar.mycompany.com
ENV_NAME: mycompany-prod
AVATAR_API_VERSION: 2.20.1
AVATAR_WEB_VERSION: 0.40.0
MAIL_PROVIDER: smtp
SMTP_HOST: mail.mycompany.com
EOF

# Run with config file
./bootstrap.sh --config my-config.yaml --non-interactive --output-dir /app/avatar
```

## Command Line Options

```
--output-dir DIR        Output directory for generated files (default: current directory)
--config FILE           YAML configuration file to use
--non-interactive       Run in non-interactive mode (use defaults or config file)
--auth-type TYPE        Authentication type: email or username (default: email)
--save-config           Save configuration to deployment-config.yaml
--help                  Show help message
```

## What Gets Generated

After running the tool, you'll have:

```
/app/avatar/
├── .env                          # Main configuration file
├── nginx/
│   └── nginx.conf               # NGINX configuration
├── .secrets/                    # Directory containing secrets
│   ├── db_password             # Auto-generated
│   ├── pepper                  # Auto-generated
│   ├── authjwt_secret_key      # Auto-generated
│   ├── file_encryption_key     # Auto-generated
│   ├── admin_emails            # Needs manual input
│   ├── db_name                 # Needs manual input
│   └── ...                     # And more
└── deployment-config.yaml       # Optional: saved configuration
```

## Post-Generation Steps

1. **Review the generated `.env` file** - Make any necessary adjustments

2. **Fill in required secrets** - Edit files in `.secrets/` directory:
   ```bash
   # Required secrets that need manual input:
   nano /app/avatar/.secrets/admin_emails
   nano /app/avatar/.secrets/db_name
   nano /app/avatar/.secrets/db_user
   nano /app/avatar/.secrets/organization_name
   # ... and others as needed
   ```

3. **Configure TLS certificates** - Set up your SSL certificates:
   ```bash
   mkdir -p /app/avatar/tls/private
   # Copy your certificates to /app/avatar/tls/
   ```

4. **Review nginx configuration** - Ensure paths to TLS certificates are correct

5. **Start the deployment**:
   ```bash
   cd /app/avatar
   docker compose up -d
   ```

## Development

### Running Tests

```bash
# With pytest installed
python -m pytest tests/ -v

# With uv
uv run --with pytest tests/test_configure.py

# Using the test script directly
uv run tests/test_configure.py
```

### Building the Package

```bash
# Install build tools
pip install build

# Build the package
python -m build

# This creates dist/ with wheel and source distributions
```

### Publishing to PyPI

```bash
# Install twine
pip install twine

# Upload to PyPI
twine upload dist/*
```

## Configuration Reference

### Essential Settings

| Setting | Description | Default |
|---------|-------------|---------|
| `PUBLIC_URL` | Domain name for your deployment | `avatar.example.com` |
| `ENV_NAME` | Environment identifier | `customer-name-prod` |
| `AVATAR_HOME` | Installation directory | `/app/avatar` |

### Service Versions

| Setting | Description | Default |
|---------|-------------|---------|
| `AVATAR_API_VERSION` | Avatar API Docker image version | `2.20.1` |
| `AVATAR_WEB_VERSION` | Avatar Web Docker image version | `0.40.0` |
| `AVATAR_PDFGENERATOR_VERSION` | PDF Generator version | `latest` |

### Email Configuration

| Setting | Description | Default |
|---------|-------------|---------|
| `MAIL_PROVIDER` | Email provider: `aws` or `smtp` | `aws` |
| `SMTP_HOST` | SMTP server hostname | `email-smtp.eu-west-3.amazonaws.com` |
| `SMTP_PORT` | SMTP server port | `587` |
| `SMTP_SENDER_EMAIL` | Sender email address | `noreply@octopize.io` |

## Templates

Templates are located in the `templates/` directory:

- `.env.template` - Environment configuration template
- `nginx.conf.template` - NGINX configuration template

Templates use Jinja2 syntax with `{{ VARIABLE }}` placeholders.

## Troubleshooting

### uv installation fails

If the bootstrap script can't install uv:
```bash
# Install manually
curl -LsSf https://astral.sh/uv/install.sh | sh

# Then run configure.py directly
uv run configure.py --output-dir /app/avatar
```

### Missing dependencies

If running without uv:
```bash
pip install pyyaml jinja2
python configure.py --output-dir /app/avatar
```

### Permission errors

Ensure you have write permissions to the output directory:
```bash
sudo mkdir -p /app/avatar
sudo chown $USER:$USER /app/avatar
```

## Support

- Documentation: https://docs.octopize.io/docs/deploying/self-hosted
- Issues: https://github.com/octopize/avatar-deployment/issues
- Contact: contact@octopize.io

## License

MIT License - see LICENSE file for details
