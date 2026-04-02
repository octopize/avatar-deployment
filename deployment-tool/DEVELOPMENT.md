# Code Patterns & Development Guidelines

This document describes the code patterns, conventions, and development guidelines for the Avatar Deployment Tool.

## Python Conventions

- **Python 3.13+** — uses modern generics (`list[str]`, `dict[str, Any]`, `T` via `TypeVar`), PEP 695 generic dataclasses (`ValidationSuccess[T]`), and `type X = ...` aliases
- **Type annotations** on all function signatures and class attributes
- **Docstrings** on all public classes and methods (Google-style with Args/Returns/Raises sections)
- **Line length**: 100 characters (configured in `pyproject.toml` via ruff)
- **Import sorting**: `isort` via ruff, with `octopize_avatar_deploy` as known first-party

## Architecture Patterns

### Protocol-Based Abstractions

The codebase uses `typing.Protocol` (structural subtyping) for all pluggable interfaces rather than ABC:

| Protocol | Implementations | Purpose |
|---|---|---|
| `Printer` | `ConsolePrinter`, `RichPrinter`, `SilentPrinter`, `FilePrinter` | Output formatting |
| `InputGatherer` | `ConsoleInputGatherer`, `RichInputGatherer`, `MockInputGatherer` | User input collection |
| `TemplateProvider` | `GitHubTemplateProvider`, `LocalTemplateProvider` | Template acquisition |

**Rich vs Console**: At runtime, `DeploymentConfigurator` selects `RichPrinter`/`RichInputGatherer` when stdout/stdin is a TTY, otherwise falls back to `ConsolePrinter`/`ConsoleInputGatherer`.

**Pattern for new protocols**:

```python
from typing import Protocol

class MyProtocol(Protocol):
    def do_thing(self, value: str) -> bool: ...

class ConcreteImpl:
    """No need to inherit from MyProtocol — structural typing matches."""
    def do_thing(self, value: str) -> bool:
        return True
```

### Step-Based Pipeline

All deployment logic is organized into **steps** — modular classes that each handle one configuration concern. The `DeploymentConfigurator` orchestrates them.

#### Step Class Contract

Every step extends `DeploymentStep` (ABC in `steps/base.py`) and must implement:

```python
class MyStep(DeploymentStep):
    # Required class attributes
    name = "my_step"                    # Unique identifier (snake_case)
    description = "Configure X and Y"   # Human-readable, shown during execution

    # Optional overrides
    modes = [DeploymentMode.PRODUCTION, DeploymentMode.DEV]  # Default: both modes
    required = True                     # Default: True

    def collect_config(self) -> dict[str, Any]:
        """Collect configuration key-value pairs for .env template rendering."""
        ...

    def generate_secrets(self) -> dict[str, str]:
        """Return {filename: value} for files written to .secrets/ directory."""
        ...
```

#### Configuration Resolution Order

The `get_config_or_prompt()` method resolves values in this priority:

1. **Pre-loaded config** (`self.config[key]`) — from YAML config file or previous steps
2. **Interactive prompt** — asks user, with optional validation
3. **Default value** — literal or looked up from `defaults.yaml` via `DefaultKey("dotted.path")`

```python
# Literal default
host = self.get_config_or_prompt("SMTP_HOST", "SMTP host", "localhost", prompt_key="email.smtp_host")

# defaults.yaml lookup
port = self.get_config_or_prompt("SMTP_PORT", "SMTP port", DefaultKey("email.smtp.port"),
                                 prompt_key="email.smtp_port", parse_and_validate=parse_str)
```

#### Prompt Keys

Every prompt **must** have a unique `prompt_key` parameter (format: `{step_name}.{field}`). This key:
- Enables `MockInputGatherer` to return pre-configured responses in tests
- Is used as the fixture key in integration test `input.yaml` files
- Must be globally unique across all steps

#### Validation Pattern

Validators return `ValidationSuccess[T] | ValidationError` (not exceptions):

```python
from .base import ValidationError, ValidationSuccess, ValidationResult

def parse_port(value: Any) -> ValidationResult[int]:
    try:
        port = int(value)
        if 1 <= port <= 65535:
            return ValidationSuccess(port)
        return ValidationError(f"Port must be 1-65535, got {port}")
    except (ValueError, TypeError):
        return ValidationError(f"Cannot parse as port number: {value}")
```

Built-in validators: `parse_bool`, `parse_int`, `parse_str`, `make_path_validator(must_exist, must_be_dir, must_be_file)`.

#### Deployment Mode Filtering

Steps declare which modes they run in via the `modes` class variable:

```python
class WebLocalSourceStep(DeploymentStep):
    modes = [DeploymentMode.DEV]  # Only runs in dev mode
```

`DeploymentConfigurator` filters steps at init time: `[cls for cls in all_step_classes if mode in cls.modes]`.

#### Shared Config Dict

All steps share the same `config` dict by reference. A step can read values set by previous steps:

```python
def collect_config(self) -> dict[str, Any]:
    # Access value set by RequiredConfigStep
    public_url = self.config.get("PUBLIC_URL", "")
```

#### Step Registration

New steps must be:
1. Defined in `src/octopize_avatar_deploy/steps/{name}.py`
2. Exported in `steps/__init__.py`
3. Added to `DEFAULT_STEP_CLASSES` in `configure.py` (order matters — determines execution sequence)

### State Management

`DeploymentState` (in `state_manager.py`) persists configuration progress to `.deployment-state.yaml`, enabling interrupted configurations to be resumed. Step states: `not-started` → `in-progress` → `completed`.

### Template Rendering

Templates use **Jinja2** syntax. The `.env.template` and other template files reference config keys directly:

```
PUBLIC_URL={{ PUBLIC_URL }}
SMTP_HOST={{ SMTP_HOST }}
```

Template variables must match the keys returned by `collect_config()` across all steps.

## Testing Patterns

### Unit Tests for Steps

Step unit tests use non-interactive mode with pre-loaded config:

```python
class TestEmailStep:
    @pytest.fixture
    def defaults(self):
        """Provide defaults matching defaults.yaml structure."""
        return {"email": {"smtp": {"host": "smtp.example.com", ...}}}

    @pytest.fixture
    def step(self, tmp_path, defaults):
        """Create step in non-interactive mode with config pre-set."""
        config = {}
        return EmailStep(tmp_path, defaults, config, interactive=False)

    def test_collect_config(self, step):
        config = step.collect_config()
        assert "SMTP_HOST" in config
        assert "MAIL_PROVIDER" not in config

    def test_generate_secrets(self, step):
        step.collect_config()
        secrets = step.generate_secrets()
        assert isinstance(secrets, dict)

    def test_step_metadata(self, step):
        assert step.name == "email"
        assert "email" in step.description.lower()
```

**Key patterns**:
- Use `tmp_path` (pytest built-in) for `output_dir`
- Set `interactive=False` for deterministic tests without prompts
- Pre-load config values that the step reads from `self.config`
- Test `collect_config()`, `generate_secrets()`, and metadata separately

### Integration Tests (CLITestHarness)

Integration tests use `CLITestHarness` to run the full CLI pipeline with mocked input:

```python
def test_basic_deployment(self, temp_deployment_dir, log_file, mock_docker_source):
    responses = fixture_manager.load_input_fixture("basic_deployment")
    harness = CLITestHarness(
        responses=responses,
        args=["--output-dir", str(temp_deployment_dir),
              "--template-from", str(mock_docker_source)],
        log_file=str(log_file),
    )
    exit_code = harness.run()

    assert exit_code == 0
    assert compare_output(log_file, temp_deployment_dir, "basic_deployment", fixture_manager)
    assert compare_generated_files(temp_deployment_dir, "basic_deployment", FIXTURES_DIR)
```

**Required assertions** for all integration tests:
1. `assert exit_code == 0` — CLI succeeds
2. `assert compare_output(...)` — Console output matches fixture
3. `assert compare_generated_files(...)` — All generated files match expected fixtures

### Fixture Format (Key-Based)

```yaml
# tests/fixtures/{scenario}/input.yaml
responses:
  required_config.public_url: "avatar.example.com"
  required_config.env_name: "production"
  email.mail_provider: "smtp"
  email.smtp_host: "smtp.example.com"
  telemetry.enable_sentry: true
```

Keys are **order-independent** and map directly to `prompt_key` parameters in step code.

### Shared Test Fixtures (`conftest.py`)

| Fixture | Scope | Purpose |
|---|---|---|
| `fixtures_dir` | session | Path to `tests/fixtures/` |
| `docker_templates_dir` | session | Path to real production templates in `docker/templates/` |
| `temp_deployment_dir` | function | Temp directory for each test's output |
| `log_file` | function | Log file path in temp dir |
| `mock_docker_source` | function | Temp copy of production templates |
| `temp_templates_dir` | function | Templates provisioned via `LocalTemplateProvider` |

### Updating Expected Fixtures

When step behavior intentionally changes:

```bash
AVATAR_DEPLOY_UPDATE_FIXTURES=1 uv run pytest tests/integration/
git diff tests/fixtures/  # Review changes before committing
uv run pytest             # Verify tests pass with updated fixtures
```

## Code Quality Commands

```bash
just lint        # Check with ruff
just format      # Format with ruff
just lint-fix    # Auto-fix lint issues
just typecheck   # Run pyright 
just lci         # Full check: lint-fix + typecheck + test-all
```
