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
uv run pytest tests/integration/test_cli_integration.py::TestCLIDeploymentScenarios::test_basic_deployment_scenario

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

## Test File Structure

```
tests/
├── integration/
│   ├── test_cli_integration.py    # Basic CLI tests
│   └── test_cli_advanced.py       # Advanced scenarios
└── fixtures/
    ├── basic_deployment_input.yaml      # Input responses
    ├── basic_deployment_output.txt      # Expected output
    ├── cloud_storage_input.yaml
    ├── cloud_storage_output.txt
    ├── no_telemetry_input.yaml
    └── no_telemetry_output.txt
```

## Creating New Test

### 1. Create input fixture

`tests/fixtures/my_scenario_input.yaml`:

```yaml
responses:
  - "https://avatar.example.com"
  - "secret-key-123"
  - True  # Boolean responses for yes/no
  # ... more responses in order
```

### 2. Add test case

```python
from tests.fixtures import FixtureManager, normalize_output, should_update_fixtures

fixture_manager = FixtureManager(Path(__file__).parent.parent / "fixtures")

def test_my_scenario(temp_deployment_dir, mock_templates_dir):
    responses = fixture_manager.load_input_fixture("my_scenario")
    
    log_file = temp_deployment_dir / "output.log"
    
    harness = CLITestHarness(
        responses=responses,
        args=["--output-dir", str(temp_deployment_dir),
              "--templates-dir", str(mock_templates_dir),
              "--skip-download"],
        log_file=log_file,
    )
    
    exit_code = harness.run()
    assert exit_code == 0
    
    actual = normalize_output(log_file.read_text())
    expected = normalize_output(fixture_manager.load_expected_output("my_scenario"))
    
    if should_update_fixtures():
        fixture_manager.save_output("my_scenario", actual)
        pytest.skip("Updated fixtures")
    
    match, diff = fixture_manager.compare_output(actual, expected)
    assert match, f"Output mismatch:\n{diff}"
```

### 3. Generate expected output

```bash
AVATAR_DEPLOY_UPDATE_FIXTURES=1 pytest tests/integration/test_file.py::test_my_scenario
```

### 4. Verify

```bash
pytest tests/integration/test_file.py::test_my_scenario
```

## Available Fixtures (from conftest.py)

- `temp_deployment_dir` - Temporary directory for output
- `mock_templates_dir` - Mock templates directory with basic files
- `fixtures_dir` - Path to fixtures directory

## Common CLITestHarness Usage

```python
# Basic usage
harness = CLITestHarness(
    responses=["response1", True, "response2"],
    args=["--skip-download"],
    silent=True
)
exit_code = harness.run()

# With log file
harness = CLITestHarness(
    responses=responses,
    args=["--output-dir", "/tmp/test"],
    log_file="/tmp/test/output.log"
)

# Multiple arguments
harness = CLITestHarness(
    responses=responses,
    args=[
        "--output-dir", str(output_dir),
        "--templates-dir", str(templates_dir),
        "--skip-download",
        "--verbose",
        "--save-config",
    ],
    log_file=log_file,
)
```

## Fixture Manager Methods

```python
from tests.fixtures import FixtureManager

fm = FixtureManager("tests/fixtures")

# Load input responses
responses = fm.load_input_fixture("basic_deployment")  # Returns list

# Load expected output
expected = fm.load_expected_output("basic_deployment")  # Returns string

# Save output (for updating)
fm.save_output("basic_deployment", actual_output)

# Compare outputs
match, diff = fm.compare_output(actual, expected)
if not match:
    print(diff)
```

## Environment Variables

- `AVATAR_DEPLOY_UPDATE_FIXTURES=1` - Update expected output fixtures
- `AVATAR_DEPLOY_TEST_MODE=1` - Enable test mode (set by CLITestHarness)
- `AVATAR_DEPLOY_TEST_SILENT=1` - Silent mode (set by CLITestHarness)
- `AVATAR_DEPLOY_TEST_LOG_FILE=<path>` - Log file path (set by CLITestHarness)
- `AVATAR_DEPLOY_TEST_RESPONSES=<serialized>` - Serialized responses (set by CLITestHarness)
