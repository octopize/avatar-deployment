# Integration Tests

Comprehensive integration tests for the Avatar Deployment Tool CLI using the `CLITestHarness`.

## Overview

These tests verify end-to-end CLI behavior with various argument combinations and user inputs, comparing actual outputs against expected fixture files.

## Test Structure

```
tests/
├── integration/          # Integration test suite
│   ├── __init__.py
│   ├── test_cli_integration.py    # Basic CLI functionality
│   └── test_cli_advanced.py       # Advanced scenarios
└── fixtures/            # Test fixtures
    ├── __init__.py               # Fixture utilities
    ├── *_input.yaml              # Input responses
    └── *_output.txt              # Expected outputs
```

## Running Tests

### Run all integration tests

```bash
pytest tests/integration/
```

### Run specific test file

```bash
pytest tests/integration/test_cli_integration.py
```

### Run specific test class

```bash
pytest tests/integration/test_cli_integration.py::TestCLIDeploymentScenarios
```

### Run specific test

```bash
pytest tests/integration/test_cli_integration.py::TestCLIDeploymentScenarios::test_basic_deployment_scenario
```

### Run with verbose output

```bash
pytest tests/integration/ -v
```

### Run with output capture disabled (see print statements)

```bash
pytest tests/integration/ -s
```

## Updating Fixtures

When the CLI output format changes legitimately (not a bug), you can update the expected output fixtures:

```bash
# Update all fixtures
AVATAR_DEPLOY_UPDATE_FIXTURES=1 pytest tests/integration/

# Update specific test
AVATAR_DEPLOY_UPDATE_FIXTURES=1 pytest tests/integration/test_cli_integration.py::TestCLIDeploymentScenarios::test_basic_deployment_scenario
```

**Important**: After updating fixtures, rerun the tests without the environment variable to ensure they pass.

## Test Scenarios

### Basic CLI Commands (`test_cli_integration.py`)

- **Help flag**: Verifies `--help` displays correct usage information
- **Version**: Tests version information display

### Deployment Scenarios (`test_cli_integration.py`)

- **Basic deployment**: Minimal configuration with email auth, username database, SeaweedFS
- **Cloud storage**: Deployment with S3/GCS/Azure storage backend
- **No telemetry**: Deployment with telemetry disabled

### Error Handling (`test_cli_integration.py`)

- **Missing output directory**: Validates behavior with non-existent output path
- **Invalid config file**: Tests handling of malformed YAML config
- **Missing templates**: Verifies error when templates missing and download skipped

### Non-Interactive Mode (`test_cli_integration.py`)

- **Config file usage**: Tests `--non-interactive` with complete config file
- **Partial config**: Validates behavior with incomplete configuration

### Advanced Scenarios (`test_cli_advanced.py`)

- **Input validation**: Tests handling of empty/invalid responses
- **Storage backends**: Parametrized tests for all supported storage types
  - SeaweedFS
  - AWS S3
  - Google Cloud Storage
  - Azure Blob Storage
- **Database auth methods**: Tests username and password-only authentication
- **Email configurations**: Tests all combinations of TLS and authentication
- **State resumption**: Tests resuming from saved deployment state
- **Custom branches**: Tests template download from custom Git branches

## Fixture Format

### Input Fixtures (`*_input.yaml`)

```yaml
# Comments explaining the scenario
responses:
  - "response1"           # String response
  - True                  # Boolean response (yes/no questions)
  - "response2"
  # ... more responses in order
```

### Output Fixtures (`*_output.txt`)

Plain text file containing the expected output. The comparison uses normalized output (trailing whitespace removed).

## Creating New Test Scenarios

### 1. Create input fixture

Create `tests/fixtures/my_scenario_input.yaml`:

```yaml
responses:
  - "https://avatar.mytest.com"
  - "secret-key"
  # ... all required responses
```

### 2. Create expected output fixture

Create `tests/fixtures/my_scenario_output.txt`:

```
Avatar Deployment Configuration
================================
...expected output...
```

### 3. Add test case

In `tests/integration/test_cli_integration.py` or `test_cli_advanced.py`:

```python
def test_my_scenario(self, temp_deployment_dir, mock_templates_dir):
    """Test my custom scenario."""
    responses = fixture_manager.load_input_fixture("my_scenario")

    log_file = temp_deployment_dir / "output.log"

    harness = CLITestHarness(
        responses=responses,
        args=[
            "--output-dir", str(temp_deployment_dir),
            "--templates-dir", str(mock_templates_dir),
            "--skip-download",
        ],
        log_file=log_file,
    )

    exit_code = harness.run()
    assert exit_code == 0

    actual_output = normalize_output(log_file.read_text())
    expected_output = normalize_output(
        fixture_manager.load_expected_output("my_scenario")
    )

    if should_update_fixtures():
        fixture_manager.save_output("my_scenario", actual_output)
        pytest.skip("Updated fixtures - rerun tests to validate")

    match, diff = fixture_manager.compare_output(actual_output, expected_output)
    assert match, f"Output mismatch:\n{diff}"
```

### 4. Generate initial output fixture

Run the test with fixture update enabled:

```bash
AVATAR_DEPLOY_UPDATE_FIXTURES=1 pytest tests/integration/test_cli_integration.py::TestClass::test_my_scenario
```

### 5. Verify and refine

Review the generated fixture file, refine if needed, then run the test normally to ensure it passes.

## Utilities

### FixtureManager

Located in `tests/fixtures/__init__.py`, provides:

- `load_input_fixture(name)`: Load input responses from YAML
- `load_expected_output(name)`: Load expected output text
- `save_output(name, output)`: Save output to fixture file
- `compare_output(actual, expected)`: Compare outputs with diff

### Helper Functions

- `should_update_fixtures()`: Check if `AVATAR_DEPLOY_UPDATE_FIXTURES` is set
- `normalize_output(output)`: Remove trailing whitespace, normalize line endings

## Tips

### Debugging Failing Tests

1. **View the diff**: Test failures show unified diff of expected vs actual
2. **Check actual output**: Examine the log file in the temp directory
3. **Run with `-s` flag**: See print statements and real-time output
4. **Use pdb**: Add `import pdb; pdb.set_trace()` for interactive debugging

### Handling Output Variations

If output contains timestamps or dynamic values:

1. Add normalization logic to `normalize_output()` in `tests/fixtures/__init__.py`
2. Use regex to replace dynamic parts with fixed strings
3. Alternatively, use more flexible assertions for dynamic sections

### Test Performance

- Tests use `tempfile.TemporaryDirectory()` for isolation
- Mock templates are minimal to speed up tests
- Use `--skip-download` to avoid network calls
- Parametrized tests run multiple scenarios efficiently

## Continuous Integration

To run integration tests in CI:

```bash
# In your CI pipeline
pytest tests/integration/ -v --tb=short

# With coverage
pytest tests/integration/ --cov=octopize_avatar_deploy --cov-report=term-missing
```

## Maintenance

### When to Update Fixtures

- CLI output format changes (headers, formatting)
- New features add output messages
- Error messages are refined
- Progress indicators are modified

### When NOT to Update Fixtures

- Test is failing due to a bug
- Output contains errors that shouldn't be there
- Behavior has changed unexpectedly

Always review the diff carefully before updating fixtures to ensure changes are intentional.
