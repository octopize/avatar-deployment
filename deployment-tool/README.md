# Octopize Avatar Deployment Tool

`octopize-deploy-tool` generates the configuration files needed to run the Octopize Avatar platform with Docker Compose. It can also generate component-specific `.env` files for local development workflows.

## Installation

Install the published package:

```bash
pip install octopize-deploy-tool
```

Then verify the CLI is available:

```bash
octopize-deploy-tool --help
```

## Quick Start

Generate a Docker deployment configuration interactively:

```bash
octopize-deploy-tool deploy --output-dir /app/avatar
```

Then start the deployment:

```bash
cd /app/avatar
docker compose down --volumes --remove-orphans
docker compose up -d
```

## Commands

The CLI has two explicit subcommands:

```text
octopize-deploy-tool deploy [options]
octopize-deploy-tool generate-env [options]
```

Running the CLI without a subcommand is not supported.

### `deploy`

Use `deploy` to generate a full Docker Compose deployment.

Example:

```bash
octopize-deploy-tool deploy --output-dir /app/avatar
```

Common `deploy` options:

```text
--output-dir DIR           Output directory for generated files
--config FILE              YAML configuration file to load
--non-interactive          Run without prompts, using config/defaults
--template-from PATH       Use a local template directory instead of the default source
--save-config              Save the resolved configuration to deployment-config.yaml
--verbose                  Show detailed progress output
--mode {production,dev}    Generate production or dev deployment assets
```

### `generate-env`

Use `generate-env` to create per-component `.env` files for local development without generating the full deployment bundle.

Example:

```bash
octopize-deploy-tool generate-env \
  --component api \
  --api-output-path ./avatar-local/api/.env \
  --component web \
  --web-output-path ./avatar-local/web/.env
```

Common `generate-env` options:

```text
--config FILE              YAML configuration file to load
--non-interactive          Run without prompts, using config/defaults
--template-from PATH       Use a local template directory instead of the default source
--verbose                  Show detailed progress output
--component NAME           Generate only the selected component (repeatable; defaults to all)
--api-output-path PATH     Override the API env output path for this run
--web-output-path PATH     Override the web env output path for this run
--python-client-output-path PATH
                           Override the python_client env output path for this run
--output-path COMPONENT=PATH
                           Repeatable generic output-path override
--target NAME              Load named URLs from the environments config section
--api-url URL              Override the API URL
--storage-url URL          Override the storage public URL
--sso-url URL              Override the SSO provider URL
```

## Non-Interactive Usage

You can provide configuration through a YAML file:

```yaml
PUBLIC_URL: avatar.example.com
ENV_NAME: prod
ORGANIZATION_NAME: MyCompany
```

Then run:

```bash
octopize-deploy-tool deploy \
  --output-dir /app/avatar \
  --config config.yaml \
  --non-interactive
```

## Generated Files

The `deploy` command typically writes:

```text
/app/avatar/
├── .env
├── docker-compose.yml
├── nginx/nginx.conf
├── authentik/
│   ├── octopize-avatar-blueprint.yaml
│   ├── custom-templates/
│   └── branding/
└── .secrets/
```

The `generate-env` command writes component env files directly to their resolved destinations, for example:

```text
./avatar-local/
├── api/.env
└── web/.env
```

## Typical Deployment Workflow

1. Generate configuration:

   ```bash
   octopize-deploy-tool deploy --output-dir /app/avatar
   ```

2. Review the generated files:

   ```bash
   cd /app/avatar
   cat .env
   ls -la .secrets/
   ```

3. Add any required TLS certificates for production.

4. Start the services:

   ```bash
   docker compose up -d
   ```

5. Verify the deployment:

   ```bash
   docker compose ps
   docker compose logs -f
   ```

## Troubleshooting

### Templates fail to download or validate

Retry with verbose output:

```bash
octopize-deploy-tool deploy --output-dir /app/avatar --verbose
```

### Existing containers cause bind-mount or startup issues

Clean up old containers and volumes before retrying:

```bash
docker compose down --volumes --remove-orphans
docker compose up -d
```

## Further Information

- Project repository: <https://github.com/octopize/avatar-deployment>
- Deployment documentation: <https://docs.octopize.io/docs/deploying/self-hosted>
