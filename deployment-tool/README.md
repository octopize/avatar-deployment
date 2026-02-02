# Octopize Avatar Deployment Tool

Automated configuration tool for deploying Octopize Avatar platform using Docker Compose.

## Overview

This tool simplifies Avatar deployment by:
- **📦 Standalone package** - No need to clone the entire repository
- **⬇️ Downloads templates** automatically from GitHub
- **🎯 Deployment presets** - dev-mode, production, airgapped configurations
- **🔐 Secure secrets generation** - Automatic creation of encryption keys
- **✅ Stateless by design** - Minimal bundled dependencies
- **🔄 Resumable configuration** - State management for interrupted setups

## Architecture

### What's Bundled vs Downloaded

**Bundled in PyPI Package:**
- `configure.py` - Main configuration logic
- `state_manager.py` - State management for resuming
- `download_templates.py` - Template downloader
- `defaults.yaml` - Default values and presets

**Downloaded from GitHub (on-demand):**
- `.env.template` - Environment configuration template
- `nginx.conf.template` - Nginx configuration template
- `docker-compose.yml` - Docker services definition
- `.template-version` - Template version information
- Other deployment files

These templates are located in `docker/templates/` in the avatar-deployment repository.

This design means you can install and run the tool without cloning the repository!

## Quick Start

### Option 1: Using uvx (Recommended - After PyPI Publication)

```bash
uvx octopize-avatar-deploy --output-dir /app/avatar
```

### Option 2: Using pip

```bash
pip install octopize-avatar-deploy
octopize-avatar-deploy --output-dir /app/avatar
```

### Option 3: From Source with uv

```bash
# Sparse clone (only deployment-tool directory)
git clone --depth 1 --filter=blob:none --sparse https://github.com/octopize/avatar-deployment
cd avatar-deployment
git sparse-checkout set deployment-tool

# Run with uv
cd deployment-tool
uv run configure.py --output-dir /app/avatar
```

## Deployment Presets

Choose a preset to quickly configure for your environment:

### `default` - Production Configuration
- Console logging: **disabled** (use structured logs)
- Sentry monitoring: **enabled**
- Telemetry: **enabled**
- Best for: Production deployments with monitoring

### `dev-mode` - Development Configuration  
- Console logging: **enabled** (see logs in terminal)
- Sentry monitoring: **disabled**
- Telemetry: **disabled**
- Best for: Local development and testing

### `airgapped` - Air-Gapped Deployment
- Console logging: **disabled**
- Sentry monitoring: **disabled** (no external connections)
- Telemetry: **disabled** (no external connections)
- Best for: Secure, isolated environments

### `custom` - Manual Configuration
- Configure all options interactively
- Best for: Specific requirements

## Usage

### Interactive Mode with Preset

```bash
octopize-avatar-deploy --output-dir /app/avatar --preset dev-mode
```

The tool will:
1. Download latest templates from GitHub
2. Apply preset configuration
3. Prompt for required values (PUBLIC_URL, ENV_NAME)
4. Generate configuration files

### Non-Interactive Mode

```bash
# Create config file
cat > my-config.yaml << EOF
PUBLIC_URL: avatar.mycompany.com
ENV_NAME: mycompany-prod
AVATAR_API_VERSION: 2.20.1
AVATAR_WEB_VERSION: 0.40.0
MAIL_PROVIDER: smtp
SMTP_HOST: mail.mycompany.com
EOF

# Run with config
octopize-avatar-deploy \
  --config my-config.yaml \
  --preset default \
  --non-interactive \
  --output-dir /app/avatar
```

### Advanced Options

```bash
octopize-avatar-deploy \
  --output-dir /app/avatar \
  --preset dev-mode \
  --download-branch main \          # Git branch to download from
  --skip-download \                 # Use cached templates
  --save-config \                   # Save config to deployment-config.yaml
  --verbose                         # Show detailed progress
```

## Command Line Options

```
--output-dir DIR           Output directory (default: current directory)
--preset NAME              Use preset: default, dev-mode, airgapped
--config FILE              YAML configuration file
--non-interactive          Non-interactive mode (use config/defaults)
--auth-type TYPE           Authentication: email or username (default: email)
--save-config              Save config to deployment-config.yaml
--download-branch BRANCH   Git branch for templates (default: main)
--skip-download            Use cached templates
--verbose                  Detailed output
```

## What Gets Generated

After running the tool, you'll have:

```
/app/avatar/
├── .env                      # Environment configuration
├── nginx.conf                # Nginx reverse proxy config
├── .secrets/                 # Generated secrets (gitignored)
│   ├── db_password
│   ├── authentik_secret_key
│   ├── avatar_api_encryption_key
│   └── ...
├── docker-compose.yml        # Downloaded from GitHub
└── .avatar-templates/        # Cached templates (auto-downloaded)
    ├── .env.template
    ├── nginx.conf.template
    ├── docker-compose.yml
    └── .template-version
```

## Configuration Presets in Detail

Presets are defined in `defaults.yaml`:

```yaml
presets:
  default:
    description: "Production-ready with telemetry and monitoring"
    application:
      use_console_logging: "false"
      sentry_enabled: "true"
    telemetry:
      enabled: true
  
  dev-mode:
    description: "Development with console logging"
    application:
      use_console_logging: "true"
      sentry_enabled: "false"
    telemetry:
      enabled: false
  
  airgapped:
    description: "No external monitoring/telemetry"
    application:
      use_console_logging: "false"
      sentry_enabled: "false"
    telemetry:
      enabled: false
```

You can override preset values during interactive configuration.

## Template Download Mechanism

Templates are downloaded from GitHub on first run:

1. **Check cache** - `.avatar-templates/` directory
2. **Download if needed** - From `github.com/octopize/avatar-deployment`
3. **Use cached** - On subsequent runs (unless `--skip-download` is used)

This ensures:
- ✅ Always get latest templates (from specified branch)
- ✅ Offline support (once cached)
- ✅ No repository cloning required
- ✅ Minimal package size

## State Management

The tool saves progress to `.deployment-state.yaml` allowing you to:

- **Resume interrupted configurations**
- **Track which steps completed**
- **Avoid re-entering values**

Steps:
1. Collect required config
2. Collect optional config
3. Generate .env file
4. Generate nginx.conf
5. Generate secrets
6. Prompt for user secrets (optional)
7. Finalize

```bash
# If interrupted, just run again:
octopize-avatar-deploy --output-dir /app/avatar

# Tool will ask: "Continue from where you left off? [Y/n]"
```

## Troubleshooting

### Templates not downloading

```bash
# Force re-download
rm -rf .avatar-templates/
octopize-avatar-deploy --output-dir /app/avatar --verbose
```

### Use specific Git branch

```bash
# Download from development branch
octopize-avatar-deploy \
  --output-dir /app/avatar \
  --download-branch develop \
  --verbose
```

### Offline mode

```bash
# Download templates once
octopize-avatar-deploy --output-dir /app/avatar

# Then use cached versions
octopize-avatar-deploy --output-dir /app/avatar --skip-download
```

## Development

### Project Structure

```
deployment-tool/
├── configure.py           # Main script (bundled)
├── state_manager.py       # State management (bundled)
├── download_templates.py  # Template downloader (bundled)
├── defaults.yaml          # Defaults and presets (bundled)
├── tests/                 # Test suite
├── README.md             
└── pyproject.toml         # Package configuration
```

### Running Tests

```bash
cd deployment-tool
pytest tests/
```

### Building Package

```bash
pip install build
python -m build
```

## Related Documentation

- [Deployment Guide](../deploying-on-single-instance.md)
- [Docker Compose Configuration](../docker-compose.yml)
- [Migration Guide](../MIGRATION_GUIDE.md)

## Support

For issues and questions:
- Email: help@octopize.io
- Documentation: https://docs.octopize.io
- Repository: https://github.com/octopize/avatar-deployment

## License

Apache License v2.0
