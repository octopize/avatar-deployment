# Octopize Avatar Deployment Tool

Automated configuration tool for deploying Octopize Avatar platform using Docker Compose.

## Quick Start

```bash
# Install
pip install octopize-avatar-deploy

# Run interactive configuration
octopize-avatar-deploy --output-dir /app/avatar

# Deploy
cd /app/avatar
docker compose down --volumes --remove-orphans  # Clean old containers if redeploying
docker compose up -d
```

## Usage Options

### Interactive Mode (Default)

```bash
octopize-avatar-deploy --output-dir /app/avatar
```

### Non-Interactive Mode

```bash
# Create config file
cat > config.yaml << EOF
PUBLIC_URL: avatar.example.com
ENV_NAME: prod
ORGANIZATION_NAME: MyCompany
EOF

# Run with config
octopize-avatar-deploy --output-dir /app/avatar --config config.yaml --non-interactive
```

## Command Line Options

```
--output-dir DIR           Output directory (default: current directory)
--config FILE              YAML configuration file
--non-interactive          Non-interactive mode (requires config file)
--template-from PATH       Use local templates instead of downloading from GitHub
--save-config              Save configuration to deployment-config.yaml
--verbose                  Show detailed output
```

## What Gets Generated

```
/app/avatar/
├── .env                            # Environment configuration
├── docker-compose.yml              # Docker services
├── nginx/nginx.conf                # Nginx config
├── authentik/
│   ├── octopize-avatar-blueprint.yaml
│   ├── custom-templates/           # Email templates
│   └── branding/                   # Logo, favicon, background
└── .secrets/                       # Generated secrets (22 files)
```

## Deployment Steps

1. **Generate configuration:**

   ```bash
   octopize-avatar-deploy --output-dir /app/avatar
   ```

2. **Review generated files:**

   ```bash
   cd /app/avatar
   cat .env
   ls -la .secrets/
   ```

3. **Add TLS certificates (production):**

   ```bash
   mkdir -p tls
   cp /path/to/fullchain.pem tls/
   cp /path/to/privkey.pem tls/
   ```

4. **Start services:**

   ```bash
   docker compose down --volumes --remove-orphans
   docker compose up -d
   ```

5. **Verify deployment:**

   ```bash
   docker compose ps
   docker compose logs -f
   curl https://avatar.example.com/api/health
   ```

## Troubleshooting

### "bind source path does not exist" error

Old containers from previous deployment. Solution:

```bash
docker compose down --volumes --remove-orphans
docker compose up -d
```

### Templates not downloading

```bash
rm -rf .avatar-templates/
octopize-avatar-deploy --output-dir /app/avatar --verbose
```

## Development

```bash
# Clone
git clone https://github.com/octopize/avatar-deployment
cd avatar-deployment/deployment-tool

# Install dependencies
just install

# Run tests
just test-all

# Run locally
just run-interactive-local
```
