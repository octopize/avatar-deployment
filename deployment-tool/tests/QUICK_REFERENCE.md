# Integration Testing Quick Reference

## Running Tests

```bash
# All tests
uv run pytest

# Integration tests only
uv run pytest tests/integration/

# Specific test file
uv run pytest tests/integration/test_cli_integration.py

# Specific test
uv run pytest tests/integration/test_cli_integration.py::TestCLIDeploymentScenarios::test_deployment_scenarios[basic_deployment]

# With verbose output
uv run pytest tests/integration/ -v

# With output capture disabled
uv run pytest tests/integration/ -s

# Stop on first failure
uv run pytest tests/integration/ -x
```

## Updating Fixtures

```bash
# Update all fixtures
AVATAR_DEPLOY_UPDATE_FIXTURES=1 uv run pytest tests/integration/

# Update specific test's fixtures
AVATAR_DEPLOY_UPDATE_FIXTURES=1 uv run pytest tests/integration/test_cli_integration.py::TestClass::test_name

# After updating, verify tests pass
uv run pytest tests/integration/
```

## Creating New Test Fixtures

### Key-Based Format

As of the key-based prompting update, all test fixtures use a **key-based dictionary format** instead of list format:

```yaml
# tests/fixtures/my_scenario/input.yaml
responses:
  required_config.public_url: "avatar.example.com"
  required_config.env_name: "production"
  required_config.organization_name: "MyCompany"
  nginx_tls.ssl_certificate_path: ""
  nginx_tls.ssl_certificate_key_path: ""
  authentik.bootstrap_email: "admin@example.com"
  email.mail_provider: "smtp"
  email.smtp_host: "smtp.example.com"
  email.smtp_port: "587"
  email.smtp_sender_email: "noreply@example.com"
  email.smtp_password: ""
  user.admin_emails: "admin@example.com"
  telemetry.enable_sentry: true
  telemetry.enable_telemetry: true
```

### Key Naming Convention

Keys follow the format: `{step_name}.{prompt_key}`

**Step names:**
- `required_config` - RequiredConfigStep
- `nginx_tls` - NginxTlsStep
- `database` - DatabaseStep (no prompts)
- `authentik` - AuthentikStep
- `authentik_blueprint` - AuthentikBlueprintStep (no prompts)
- `storage` - StorageStep (no prompts)
- `email` - EmailStep
- `user` - UserStep
- `telemetry` - TelemetryStep
- `logging` - LoggingStep (no prompts)
- `resume` - Special resume prompts

**Available prompt keys by step:**

RequiredConfigStep:
- `public_url` - PUBLIC_URL domain
- `env_name` - Environment name
- `organization_name` - Organization name

NginxTlsStep:
- `ssl_certificate_path` - TLS certificate path
- `ssl_certificate_key_path` - TLS private key path

AuthentikStep:
- `bootstrap_email` - Authentik admin email

EmailStep:
- `mail_provider` - Mail provider (smtp or aws)
- `smtp_host` - SMTP host (if smtp provider)
- `smtp_port` - SMTP port (if smtp provider)
- `smtp_sender_email` - SMTP sender email (if smtp provider)
- `smtp_password` - SMTP password (if smtp provider, in generate_secrets)

UserStep:
- `admin_emails` - Admin emails (comma-separated, if email auth enabled)

TelemetryStep:
- `enable_sentry` - Enable Sentry monitoring? (bool)
- `enable_telemetry` - Enable usage telemetry? (bool)

Resume workflow:
- `resume.continue` - Resume from where you left off? (bool)

### Why Keys? Benefits Over List Format

**Old list format problems:**
```yaml
responses:
  - "avatar.example.com"  # Position 0 - what is this?
  - "production"           # Position 1 - brittle!
  - "MyCompany"            # Position 2 - breaks if steps reorder
```

**New key-based format benefits:**
- ✅ **Self-documenting** - Keys show what each response is for
- ✅ **Order-independent** - Adding steps in the middle doesn't break tests
- ✅ **Explicit** - Clear mapping between prompts and responses
- ✅ **Maintainable** - Easy to find and update specific responses
- ✅ **Error-resistant** - Missing keys raise clear errors with available options

### Conditional Prompts

Some prompts are conditional based on config values:

- **SMTP prompts** - Only if `email.mail_provider: "smtp"`
- **Admin emails** - Only if email authentication is enabled
- **Resume prompt** - Only if deployment state exists

Make sure your fixture includes keys for all prompts that will be asked given your config!

## Environment Variables

- `AVATAR_DEPLOY_UPDATE_FIXTURES=1` - Update expected output fixtures
- `AVATAR_DEPLOY_TEST_MODE=1` - Enable test mode (set by CLITestHarness)
- `AVATAR_DEPLOY_TEST_SILENT=1` - Silent mode (set by CLITestHarness)
- `AVATAR_DEPLOY_TEST_LOG_FILE=<path>` - Log file path (set by CLITestHarness)
- `AVATAR_DEPLOY_TEST_RESPONSES=<serialized>` - Serialized responses (set by CLITestHarness)
- `AVATAR_DEPLOY_DEBUG_PROMPTS=1` - Enable debug logging for input prompts
