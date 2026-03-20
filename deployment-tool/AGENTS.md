# AI Agents Configuration — Deployment Tool

**Component**: Octopize Avatar Deployment Tool  
**Purpose**: Interactive/automated Docker Compose configuration generator for deploying the Octopize Avatar platform  
**Language**: Python 3.13+ · **Entry point**: `octopize-deploy-tool` CLI

**Important**: Do NOT create summary documents or extensive documentation after completing tasks unless explicitly requested. Keep responses concise and focused on the task at hand.

## Key References

| Document | Purpose |
|---|---|
| [DEVELOPMENT.md](DEVELOPMENT.md) | Code patterns, architecture conventions, and development guidelines |
| [README.md](README.md) | Public-facing PyPI README for external users; keep installation and usage examples repository-agnostic |
| [tests/TESTING.md](tests/TESTING.md) | Running tests, fixtures, CLITestHarness, debugging, adding steps |
| [../.claude/skills/deployment-tool-steps/SKILL.md](../.claude/skills/deployment-tool-steps/SKILL.md) | Skill for adding new deployment steps |

## Testing Requirements

**CRITICAL**: Always run the full test suite after making any code modifications:

```bash
just test-all  # Or: uv run pytest
```

Verify all tests pass before considering the work complete. This applies to:
- Source code changes in `src/`
- Test modifications in `tests/`
- Configuration changes that affect behavior
- Fixture updates

Update fixtures when expected output intentionally changes:

```bash
AVATAR_DEPLOY_UPDATE_FIXTURES=1 uv run pytest tests/integration/
```

## Documentation Audience

- `README.md` in this directory is public-facing documentation published on PyPI.
- Write it for external users installing and operating the released CLI, not for repository contributors.
- Prefer published-install and CLI usage examples over local `just` workflows or contributor setup steps.
- Keep contributor/development guidance in `DEVELOPMENT.md`, `tests/TESTING.md`, or agent docs instead.

## Architecture Overview

The tool follows a **step-based pipeline** architecture. See [DEVELOPMENT.md](DEVELOPMENT.md) for detailed code patterns.

1. Load configuration (YAML defaults + user overrides)
2. Execute ordered configuration steps (each step collects/validates a concern)
3. Render Jinja2 templates (`.env`, `docker-compose.yml`, nginx config, etc.)
4. Write output to the target directory

### Key Modules

| Module | Purpose |
|---|---|
| `configure.py` | Main entry point, CLI argument parsing, step orchestration (`DEFAULT_STEP_CLASSES`) |
| `state_manager.py` | Tracks configuration state across steps |
| `input_gatherer.py` | Handles interactive prompts and non-interactive config loading |
| `deployment_mode.py` | Deployment mode/preset logic (default, dev-mode, airgapped) |
| `download_templates.py` | Template acquisition (GitHub download or local path) |
| `defaults.yaml` | Default configuration values and image versions |
| `printer.py` | Formatted output and progress display |
| `cli_test_harness.py` | Test harness for integration testing |
| `version_compat.py` | Version compatibility checking |

### Steps (`src/octopize_avatar_deploy/steps/`)

Each step extends `base.py` and handles one configuration concern:

| Step | Concern |
|---|---|
| `required.py` | Public URL, environment name, organization |
| `nginx.py` | TLS, ports, certificate paths |
| `database.py` | Database connection configuration |
| `authentik.py` | Authentik SSO service configuration |
| `authentik_blueprint.py` | Authentik blueprint configuration |
| `storage.py` | S3-compatible storage (SeaweedFS or cloud) |
| `email.py` | Email provider (AWS SES or SMTP) |
| `user.py` | Admin user configuration |
| `telemetry.py` | Telemetry and monitoring |
| `logging.py` | Logging configuration |
| `local_source.py` | Local source mounts for development |
| `api_local_source.py` | API-specific local source configuration |

**Adding a new step**: See [DEVELOPMENT.md § Step Registration](DEVELOPMENT.md#step-registration) and the [deployment-tool-steps skill](../.claude/skills/deployment-tool-steps/SKILL.md).

## Build & Development

### Just Commands

```bash
just install          # Install dependencies via uv
just test             # Unit tests only
just test-integration # Integration tests only
just test-all         # All tests
just lint             # Lint with ruff
just format           # Format with ruff
just lint-fix         # Auto-fix lint issues
just typecheck        # Run pyright
just lci              # Full check: lint-fix + typecheck + test-all
just build            # Build package
```

### Running Locally

```bash
just run-interactive-github  # Run with GitHub templates
just run-interactive-local   # Run with local templates
```

### CLI Options

```
deploy:
  --output-dir DIR       Output directory for generated files
  --config FILE          YAML configuration file
  --non-interactive      Non-interactive mode (requires --config)
  --template-from PATH   Use local templates instead of downloading
  --save-config          Save configuration to YAML
  --verbose              Verbose output

generate-env:
  --config FILE                     YAML configuration file
  --non-interactive                 Non-interactive mode
  --template-from PATH              Use local templates instead of downloading
  --verbose                         Verbose output
  --component NAME                  Generate only selected components (defaults to all)
  --api-output-path PATH            Override API env destination for this run
  --web-output-path PATH            Override web env destination for this run
  --python-client-output-path PATH  Override python_client env destination for this run
  --output-path COMPONENT=PATH      Repeatable generic output-path override
```

## Configuration Presets

Defined in `defaults.yaml`:

| Preset | Description |
|---|---|
| `default` | Production — telemetry, monitoring, TLS enabled |
| `dev-mode` | Development — console logging, no external services |
| `airgapped` | Air-gapped — no external monitoring/telemetry |

## Generated Output

The tool produces:

- `.env` — Environment configuration
- `docker-compose.yml` — Docker service definitions
- `nginx/nginx.conf` — Reverse proxy configuration
- `authentik/` — SSO configuration + blueprints
- `.secrets/` — 22 auto-generated secret files

## Common Pitfalls

1. **Editing templates at runtime path** — Templates come from `.avatar-templates/` which is populated at runtime. Edit source templates in the repo, not generated output.
2. **Forgetting to update fixtures** — When step behavior changes, run `AVATAR_DEPLOY_UPDATE_FIXTURES=1 uv run pytest` to update expected outputs.
3. **Missing step registration** — New steps must be added to `DEFAULT_STEP_CLASSES` in `configure.py` and exported in `steps/__init__.py`.
4. **Template variable naming** — `.env.template` uses Jinja2 `{{ var }}` syntax. Ensure state keys match template variable names.
5. **Prompt keys** — Every interactive prompt must have a unique `prompt_key` for `MockInputGatherer` to work in tests.
