# Testing Guide

## Overview

This document provides a comprehensive guide to testing the Avatar Deployment Tool, with a focus on integration testing using the CLITestHarness.

## Test Structure

```
tests/
├── conftest.py                    # Shared pytest fixtures and configuration
├── pytest.ini                     # Pytest configuration
├── integration/                   # Integration tests
│   ├── __init__.py
│   ├── README.md                  # Integration test documentation
│   ├── test_cli_integration.py   # Basic CLI tests
│   └── test_cli_advanced.py      # Advanced scenario tests
├── fixtures/                      # Test fixtures
│   ├── __init__.py               # Fixture utilities (FixtureManager)
│   ├── *_input.yaml              # Input response files
│   └── *_output.txt              # Expected output files
└── [unit tests]                  # Existing unit tests
    ├── test_deployment_configurator.py
    ├── test_deployment_runner.py
    ├── test_input_gatherer.py
    └── ...
```

## Quick Start

### Run all tests

```bash
pytest
```

### Run only integration tests

```bash
pytest tests/integration/
```

### Run only unit tests (exclude integration)

```bash
pytest -m "not integration"
```

### Run specific test file

```bash
pytest tests/integration/test_cli_integration.py
```

### Run with coverage

```bash
pytest --cov=octopize_avatar_deploy --cov-report=html
```

## Integration Testing with CLITestHarness

The CLITestHarness allows you to test the complete CLI workflow by:

1. **Mocking user input** - Provide pre-configured responses
2. **Capturing output** - Log all output to a file for verification
3. **Comparing results** - Match actual output against expected fixtures

### Basic Example

```python
from octopize_avatar_deploy.cli_test_harness import CLITestHarness

def test_deployment():
    responses = [
        "https://avatar.example.com",  # Base URL
        "secret-key-123",              # Django secret
        # ... more responses
    ]
    
    harness = CLITestHarness(
        responses=responses,
        args=["--skip-download", "--output-dir", "/tmp/test"],
        log_file="/tmp/test/output.log"
    )
    
    exit_code = harness.run()
    assert exit_code == 0
```

### Using Fixtures

```python
from tests.fixtures import FixtureManager, normalize_output, should_update_fixtures

fixture_manager = FixtureManager("tests/fixtures")

def test_with_fixtures(temp_deployment_dir, mock_templates_dir):
    # Load responses from fixture file
    responses = fixture_manager.load_input_fixture("basic_deployment")
    
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
    
    # Compare output
    actual = normalize_output(log_file.read_text())
    expected = normalize_output(fixture_manager.load_expected_output("basic_deployment"))
    
    if should_update_fixtures():
        fixture_manager.save_output("basic_deployment", actual)
        pytest.skip("Updated fixtures")
    
    match, diff = fixture_manager.compare_output(actual, expected)
    assert match, f"Output mismatch:\n{diff}"
```

## Fixture Management

### Creating Fixtures

#### 1. Input Fixture (`*_input.yaml`)

```yaml
# tests/fixtures/my_scenario_input.yaml
responses:
  - "https://avatar.test.com"  # Base URL
  - "secret-key"               # Django secret key
  - True                       # Boolean for yes/no questions
  - "more responses..."
```

#### 2. Expected Output Fixture (`*_output.txt`)

```
# tests/fixtures/my_scenario_output.txt
Avatar Deployment Configuration
================================

Step 1/5: Required Configuration
---------------------------------
✓ Base URL configured
...
```

### Updating Fixtures

When CLI output legitimately changes:

```bash
# Update all fixtures
AVATAR_DEPLOY_UPDATE_FIXTURES=1 pytest tests/integration/

# Update specific test
AVATAR_DEPLOY_UPDATE_FIXTURES=1 pytest tests/integration/test_cli_integration.py::TestClass::test_name

# Then verify
pytest tests/integration/
```

## Shared Fixtures

Defined in `tests/conftest.py`:

### `temp_deployment_dir`

Temporary directory for deployment output. Automatically cleaned up after each test.

```python
def test_example(temp_deployment_dir):
    # Use temp_deployment_dir as Path object
    config_file = temp_deployment_dir / "config.yaml"
```

### `mock_templates_dir`

Minimal templates directory with basic template files.

```python
def test_example(temp_deployment_dir, mock_templates_dir):
    # Templates already exist at mock_templates_dir
    pass
```

## Test Markers

### `@pytest.mark.integration`

Automatically applied to tests in `tests/integration/` directory.

```bash
# Run only integration tests
pytest -m integration

# Skip integration tests
pytest -m "not integration"
```

### `@pytest.mark.fixtures`

Mark tests that require fixture files.

```python
@pytest.mark.fixtures
def test_with_fixtures():
    pass
```

### `@pytest.mark.parametrized`

Mark parametrized tests with multiple scenarios.

```python
@pytest.mark.parametrized
@pytest.mark.parametrize("backend", ["s3", "gcs", "azure"])
def test_storage_backends(backend):
    pass
```

### `@pytest.mark.slow`

Mark tests that take significant time.

```bash
# Skip slow tests
pytest -m "not slow"
```

## Best Practices

### 1. Test Isolation

- Each test should use its own temporary directory
- Don't share state between tests
- Use fixtures for common setup

### 2. Fixture Naming

- Input: `{scenario}_input.yaml`
- Output: `{scenario}_output.txt`
- Use descriptive scenario names

### 3. Output Normalization

Add normalization for dynamic content:

```python
def normalize_output(output: str) -> str:
    output = output.replace(r"\d{4}-\d{2}-\d{2}", "YYYY-MM-DD")  # Dates
    output = re.sub(r"\d+\.\d+s", "X.XXs", output)  # Timing
    return output
```

### 4. Parametrized Tests

Use parametrization for similar scenarios:

```python
@pytest.mark.parametrize("storage,extra", [
    ("s3", ["endpoint", "key", "secret", "bucket"]),
    ("gcs", ["endpoint", "key", "secret", "bucket"]),
])
def test_storage(storage, extra):
    pass
```

### 5. Error Testing

Test both success and failure cases:

```python
def test_invalid_config():
    harness = CLITestHarness(
        responses=[],
        args=["--config", "invalid.yaml"],
        silent=True
    )
    exit_code = harness.run()
    assert exit_code != 0  # Should fail
```

## Debugging

### View Test Output

```bash
# See print statements
pytest -s

# Show full diff
pytest -vv

# Stop on first failure
pytest -x
```

### Interactive Debugging

```python
def test_example():
    import pdb; pdb.set_trace()
    # ... test code
```

### Check Captured Output

```python
def test_example(temp_deployment_dir):
    log_file = temp_deployment_dir / "output.log"
    harness.run()
    
    # Print actual output for debugging
    print("\n" + "="*60)
    print(log_file.read_text())
    print("="*60)
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      - run: pip install -e '.[dev]'
      - run: pytest tests/ --cov --cov-report=xml
      - uses: codecov/codecov-action@v3
```

### Run Integration Tests in CI

```bash
# Fast unit tests first
pytest -m "not integration" --tb=short

# Then integration tests
pytest -m integration --tb=short -v
```

## Common Issues

### Fixture Update Not Working

**Problem**: Setting `AVATAR_DEPLOY_UPDATE_FIXTURES=1` doesn't update fixtures.

**Solution**: Check that:
- Environment variable is exported: `export AVATAR_DEPLOY_UPDATE_FIXTURES=1`
- Test is actually running (not skipped)
- Fixture path is correct

### Output Mismatch

**Problem**: Test fails with output difference.

**Solutions**:
1. Review the diff carefully - is this intentional?
2. Update fixture if change is legitimate
3. Fix the code if it's a bug
4. Add normalization if difference is insignificant

### Tests Hanging

**Problem**: Test seems to hang indefinitely.

**Solutions**:
1. Check that response count matches number of prompts
2. Verify no infinite loops in step logic
3. Add timeout to test execution

### Template Not Found

**Problem**: Test fails with "template not found" error.

**Solutions**:
1. Ensure `mock_templates_dir` fixture is used
2. Create required template files in the fixture
3. Use `--skip-download` flag

## Advanced Topics

### Custom Fixture Manager

Extend `FixtureManager` for custom needs:

```python
class CustomFixtureManager(FixtureManager):
    def load_with_substitution(self, name, **kwargs):
        template = self.load_expected_output(name)
        return template.format(**kwargs)
```

### Response Validation

Add validation to ensure fixtures are valid:

```python
def validate_responses(responses, expected_count):
    assert len(responses) == expected_count, \
        f"Expected {expected_count} responses, got {len(responses)}"
```

### Performance Testing

Time your integration tests:

```python
import time

def test_performance(temp_deployment_dir, mock_templates_dir):
    start = time.time()
    harness.run()
    duration = time.time() - start
    
    assert duration < 5.0, f"Test took too long: {duration}s"
```

## Resources

- [Integration Tests README](integration/README.md) - Detailed integration test guide
- [pytest documentation](https://docs.pytest.org/) - Official pytest docs
- [CLITestHarness source](../src/octopize_avatar_deploy/cli_test_harness.py) - Implementation details
- [Fixture utilities source](fixtures/__init__.py) - FixtureManager implementation
