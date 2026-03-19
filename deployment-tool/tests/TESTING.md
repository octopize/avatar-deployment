# Testing Guide

## Running Tests

```bash
just test-all                # All tests (or: uv run pytest)
just test                    # Unit tests only
just test-integration        # Integration tests only

# Specific test
uv run pytest tests/integration/test_cli_integration.py::TestCLIDeploymentScenarios::test_deployment_scenarios[basic_deployment]

# Useful flags
uv run pytest -s             # Show print statements
uv run pytest -x             # Stop on first failure
uv run pytest -vv            # Full diff output
```

## Test Structure

```
tests/
├── conftest.py              # Shared fixtures and comparison helpers
├── fixtures/                # Test data and expected outputs
│   ├── __init__.py          # FixtureManager utilities
│   └── {scenario}/          # One directory per scenario
│       ├── input.yaml       # Key-based response dictionary
│       ├── output.txt       # Expected CLI output
│       └── expected/        # Expected generated files (.env, docker-compose.yml, etc.)
├── unit/                    # Unit tests for individual modules
├── steps/                   # Unit tests for step classes
├── integration/             # CLI integration tests (CLITestHarness)
└── test_cli_harness.py      # Tests for the harness itself
```

## Fixture Format (Key-Based)

All fixtures use key-based dictionaries — keys map to `prompt_key` parameters in step code:

```yaml
# tests/fixtures/{scenario}/input.yaml
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

Keys are **order-independent** — adding steps doesn't break existing fixtures.

### Available Prompt Keys by Step

| Step | Keys |
|---|---|
| `required_config` | `public_url`, `env_name`, `organization_name` |
| `nginx_tls` | `ssl_certificate_path`, `ssl_certificate_key_path` |
| `authentik` | `bootstrap_email` |
| `database` | *(no prompts)* |
| `authentik_blueprint` | *(no prompts)* |
| `storage` | *(no prompts)* |
| `email` | `mail_provider`, `smtp_host`, `smtp_port`, `smtp_sender_email`, `smtp_password` |
| `user` | `admin_emails` |
| `telemetry` | `enable_sentry`, `enable_telemetry` |
| `logging` | *(no prompts)* |
| `resume` | `continue` *(special — only when deployment state exists)* |

### Conditional Prompts

Some prompts only appear based on config values:
- **SMTP prompts** — only if `email.mail_provider: "smtp"`
- **Admin emails** — only if email authentication is enabled
- **Resume prompt** — only if deployment state exists

## Updating Fixtures

When CLI output or generated files intentionally change:

```bash
AVATAR_DEPLOY_UPDATE_FIXTURES=1 uv run pytest tests/integration/
git diff tests/fixtures/    # Review changes
uv run pytest               # Verify tests pass
```

## Writing Unit Tests for Steps

```python
class TestMyStep:
    @pytest.fixture
    def defaults(self):
        return {"my_section": {"host": "example.com", "port": 587}}

    @pytest.fixture
    def step(self, tmp_path, defaults):
        config = {"MY_KEY": "value"}
        return MyStep(tmp_path, defaults, config, interactive=False)

    def test_collect_config(self, step):
        config = step.collect_config()
        assert config["MY_KEY"] == "value"
        assert "MY_HOST" in config

    def test_generate_secrets(self, step):
        secrets = step.generate_secrets()
        assert isinstance(secrets, dict)

    def test_step_metadata(self, step):
        assert step.name == "my_step"
```

**Key patterns**:
- Use `tmp_path` for `output_dir`, `interactive=False` for deterministic tests
- Pre-load config values the step reads from `self.config`
- Test `collect_config()`, `generate_secrets()`, and metadata separately

## Writing Integration Tests

Integration tests use `CLITestHarness` to run the full CLI pipeline:

```python
def test_scenario(self, temp_deployment_dir, log_file, mock_docker_source):
    responses = fixture_manager.load_input_fixture("my_scenario")
    harness = CLITestHarness(
        responses=responses,
        args=["--output-dir", str(temp_deployment_dir),
              "--template-from", str(mock_docker_source)],
        log_file=str(log_file),
    )
    exit_code = harness.run()

    # All three assertions are REQUIRED
    assert exit_code == 0
    assert compare_output(log_file, temp_deployment_dir, "my_scenario", fixture_manager)
    assert compare_generated_files(temp_deployment_dir, "my_scenario", FIXTURES_DIR)
```

### Creating a New Scenario

1. Create `tests/fixtures/my_scenario/input.yaml` with responses
2. Run with fixture update to generate expected output:
   ```bash
   AVATAR_DEPLOY_UPDATE_FIXTURES=1 uv run pytest tests/integration/test_cli_integration.py::TestClass::test_name
   ```
3. Review generated `output.txt` and `expected/` directory
4. Run without the env var to verify the test passes

### Shared Fixtures (`conftest.py`)

| Fixture | Scope | Purpose |
|---|---|---|
| `fixtures_dir` | session | Path to `tests/fixtures/` |
| `docker_templates_dir` | session | Path to production templates in `docker/templates/` |
| `temp_deployment_dir` | function | Temp directory for each test's output |
| `log_file` | function | Log file path in temp dir |
| `mock_docker_source` | function | Temp copy of production templates |
| `temp_templates_dir` | function | Templates provisioned via `LocalTemplateProvider` |

## Adding a New Deployment Step

### Checklist

- [ ] Step class created in `src/octopize_avatar_deploy/steps/`
- [ ] Exported in `steps/__init__.py`
- [ ] Added to `DEFAULT_STEP_CLASSES` in `configure.py` (order matters)
- [ ] Unit tests created in `tests/steps/`
- [ ] Prompt order verified with `AVATAR_DEPLOY_DEBUG_PROMPTS=1`
- [ ] Integration fixtures updated (responses in `input.yaml`, step description in `output.txt`)
- [ ] All tests pass: `just test-all`
- [ ] Fixture changes reviewed: `git diff tests/fixtures/`

### Debug Prompt Order

When adding a step or debugging fixture mismatches:

```bash
AVATAR_DEPLOY_DEBUG_PROMPTS=1 uv run pytest \
  tests/integration/test_cli_integration.py::TestCLIDeploymentScenarios::test_deployment_scenarios[basic_deployment] \
  -xvs 2>&1 | grep "\[PROMPT"
```

Output shows the prompt sequence with keys and consumed values:
```
[PROMPT] Public URL ... [key: required_config.public_url] => 'avatar.example.com'
[PROMPT] Environment name ... [key: required_config.env_name] => 'production'
```

## Debugging

### Common Issues

| Problem | Solution |
|---|---|
| `MockInputGatherer: No response configured for key 'X'` | Add the missing key to `input.yaml` |
| `MockInputGatherer: Key 'X' has already been used` | A prompt is being called twice — check step logic |
| Output mismatch | Review diff — if intentional, update fixtures |
| Test hangs | Response count doesn't match prompt count |

### Useful Commands

```bash
# See all prompts with debug info
AVATAR_DEPLOY_DEBUG_PROMPTS=1 uv run pytest tests/integration/ -xvs

# Interactive debugging
# Add: import pdb; pdb.set_trace()
uv run pytest tests/path -xvs
```

## Environment Variables

| Variable | Purpose |
|---|---|
| `AVATAR_DEPLOY_UPDATE_FIXTURES=1` | Update expected output and generated file fixtures |
| `AVATAR_DEPLOY_TEST_MODE=1` | Enable test mode (set by CLITestHarness) |
| `AVATAR_DEPLOY_TEST_SILENT=1` | Silent mode (set by CLITestHarness) |
| `AVATAR_DEPLOY_TEST_LOG_FILE=<path>` | Log file path (set by CLITestHarness) |
| `AVATAR_DEPLOY_DEBUG_PROMPTS=1` | Show all prompts with keys and response values |

## Integration Test Scenarios

| Scenario | Description |
|---|---|
| `basic_deployment` | Minimal config — email auth, SMTP, SeaweedFS |
| `cloud_storage` | S3/GCS/Azure storage backend |
| `config_not_found` | Error handling for missing config file |
| `config_round_trip_*` | Save config → reload → verify round-trip |
