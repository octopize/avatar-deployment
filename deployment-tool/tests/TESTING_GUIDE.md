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

## Integration Testing with CLITestHarness

The CLITestHarness allows you to test the complete CLI workflow by:

1. **Mocking user input** - Provide pre-configured responses
2. **Capturing output** - Log all output to a file for verification
3. **Comparing results** - Match actual output against expected fixtures

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

### Debug Prompt Order

When tests fail due to prompt mismatches or when adding a new step, use the `AVATAR_DEPLOY_DEBUG_PROMPTS` environment variable to see the exact order and values of prompts:

```bash
# See all prompts with their response index and values
AVATAR_DEPLOY_DEBUG_PROMPTS=1 uv run pytest tests/integration/test_cli_integration.py::test_name -s

# Example output:
# [PROMPT #1] Public URL (domain name, e.g., avatar.example.com) => 'https://avatar.example.com'
# [PROMPT #2] Environment name (e.g., mycompany-prod) => 'production'
# [PROMPT #3] Organization name (e.g., MyCompany) => 'MyCompany'
# ...
```

This shows:
- The **order** of prompts (numbered sequentially)
- The **prompt message** being displayed
- The **response value** that will be used (from fixture or default)

**Use this when:**
- Adding a new deployment step and need to know where to insert responses in fixtures
- Test fails with "not enough responses" or "validation failed"
- Understanding which step is consuming which responses

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

## Testing New Deployment Steps

When adding a new deployment step (e.g., `AuthentikBlueprintStep`), follow this workflow to ensure proper integration and testing.

### 1. Create the Step

Implement your step in `src/octopize_avatar_deploy/steps/`:

```python
class MyNewStep(DeploymentStep):
    name = "my_new_step"
    description = "Configure my new feature"
     

    def collect_config(self) -> dict[str, Any]:
        config = {}
        # Use self.prompt() for interactive input
        if self.interactive:
            config["MY_VALUE"] = self.prompt("Enter value", "default")
        return config

    def generate_secrets(self) -> dict[str, str]:
        return {"my_secret": secrets.token_hex()}
```

### 2. Add Unit Tests

Create tests for the step in `tests/`:

```python
def test_my_new_step_collect_config():
    """Test configuration collection."""
    step = MyNewStep(
        output_dir=Path("/tmp"),
        defaults={},
        interactive=False,
    )
    config = step.collect_config()
    assert "MY_VALUE" in config

def test_my_new_step_secrets():
    """Test secret generation."""
    step = MyNewStep(output_dir=Path("/tmp"), defaults={})
    secrets = step.generate_secrets()
    assert "my_secret" in secrets
    assert len(secrets["my_secret"]) > 0
```

### 3. Integrate into Configurator

Add to `DEFAULT_STEP_CLASSES` in `configure.py`:

```python
DEFAULT_STEP_CLASSES: list[type[DeploymentStep]] = [
    RequiredConfigStep,
    DatabaseStep,
    MyNewStep,  # Add in appropriate order
    # ...
]
```

### 4. Debug Prompt Order

**Before modifying integration tests**, understand the new prompt sequence:

```bash
# Run an existing integration test with debug prompts
AVATAR_DEPLOY_DEBUG_PROMPTS=1 uv run pytest \
  tests/integration/test_cli_integration.py::TestCLIDeploymentScenarios::test_deployment_scenarios[basic_deployment] \
  -xvs 2>&1 | grep "\[PROMPT"
```

Example output:
```
[PROMPT #1] Public URL (domain name, e.g., avatar.example.com) => 'https://avatar.example.com'
[PROMPT #2] Environment name (e.g., mycompany-prod) => 'production'
[PROMPT #3] Organization name (e.g., MyCompany) => 'MyCompany'
[PROMPT #4] Base domain for Avatar => 'smtp'  # ← Your new step started here!
[PROMPT #5] OAuth2 Client ID => 'smtp.example.com'  # ← Still your step
...
```

This shows:
- **Which prompts your step adds** (e.g., prompts 4-5 in example above)
- **Where they appear** in the sequence
- **What response values are being consumed** (note how SMTP values are used for blueprint!)

### 5. Update Integration Test Fixtures

**Prefer modifying existing fixtures** over creating new ones.

#### Count current responses:
```bash
yq '.responses | length' tests/fixtures/basic_deployment/input.yaml
# Output: 11
```

After adding a step with 2 prompts, you'll need 13 total responses.

#### Edit `tests/fixtures/*/input.yaml`:

Add responses for your step's prompts **in the correct position** based on step order:

```yaml
responses:
  - "https://avatar.example.com"   # RequiredConfigStep: PUBLIC_URL
  - "production"                   # RequiredConfigStep: ENV_NAME
  - "MyCompany"                    # RequiredConfigStep: ORGANIZATION_NAME
  - "avatar.example.com"           # ← NEW: YourStep: DOMAIN
  - "my-client-id"                 # ← NEW: YourStep: CLIENT_ID
  - "smtp"                         # EmailStep: MAIL_PROVIDER (was #4, now #6)
  - "smtp.example.com"             # EmailStep: SMTP_HOST (was #5, now #7)
  # ... etc - all subsequent responses shift down by 2
```

**Critical**: Insert responses at the position where your step runs, based on `DEFAULT_STEP_CLASSES` order!

### 6. Update Expected Output

Edit `tests/fixtures/*/output.txt` to add your step's description:

```diff
 --- Configure PostgreSQL database credentials ---
 
+--- Configure my new feature ---
+
 --- Configure S3-compatible storage (SeaweedFS) credentials ---
```

Also update the secret count if your step generates secrets:

```diff
-Writing 20 secrets to .secrets/ directory...
+Writing 22 secrets to .secrets/ directory...
```

### 7. Run and Update Fixtures

```bash
# Run the test - it will likely fail initially
cd deployment-tool
pytest tests/integration/test_cli_integration.py::TestCLIDeploymentScenarios -xvs

# If failures are expected (due to new step), update fixtures automatically
AVATAR_DEPLOY_UPDATE_FIXTURES=1 pytest tests/integration/

# Review the changes
git diff tests/fixtures/

# Run tests again to confirm they pass
pytest tests/integration/
```

### 8. Common Issues When Adding Steps

#### "Not enough responses" error

**Symptom**: `MockInputGatherer ran out of responses (asked 12 times)`

**Cause**: Your step is prompting more times than fixture provides

**Solution**: 
```bash
# Debug to see all prompts
AVATAR_DEPLOY_DEBUG_PROMPTS=1 pytest test_name -xvs 2>&1 | grep PROMPT

# Count how many prompts your step adds
# Add that many responses to input.yaml
```

#### Prompt order confusion

**Symptom**: Wrong values being used for prompts

**Cause**: Step integrated in wrong position in `DEFAULT_STEP_CLASSES`

**Solution**:
```bash
# Debug to see actual prompt order
AVATAR_DEPLOY_DEBUG_PROMPTS=1 pytest test_name -xvs

# Adjust step position in configure.py if needed
# OR adjust fixture responses to match actual order
```

### Testing Checklist

When adding a new step, verify:

- [ ] **Unit tests** created for step class
- [ ] **Step added** to `DEFAULT_STEP_CLASSES` in correct order
- [ ] **Step exported** in `steps/__init__.py`
- [ ] **Debug prompt order** verified with `AVATAR_DEPLOY_DEBUG_PROMPTS=1`
- [ ] **Integration test fixtures** updated (prefer modifying existing):
  - [ ] Responses added in `input.yaml` (correct position!)
  - [ ] Step description added in `output.txt`
  - [ ] Secret count updated if applicable
- [ ] **All unit tests pass**: `pytest tests/ -m "not integration"`
- [ ] **All integration tests pass**: `pytest tests/integration/`
- [ ] **Fixture changes reviewed**: `git diff tests/fixtures/`

### Example: Adding AuthentikBlueprintStep

Here's a real-world example of the prompt order issue:

**Before adding the step**, basic_deployment had 11 responses:
```yaml
responses:
  - "https://avatar.example.com"   # 1: PUBLIC_URL
  - "production"                   # 2: ENV_NAME
  - "MyCompany"                    # 3: ORGANIZATION_NAME
  - "smtp"                         # 4: MAIL_PROVIDER
  - "smtp.example.com"             # 5: SMTP_HOST
  - "587"                          # 6: SMTP_PORT
  - "noreply@example.com"          # 7: SMTP_SENDER_EMAIL
  - ""                             # 8: SMTP_PASSWORD (empty)
  - "admin@example.com"            # 9: ADMIN_EMAILS
  - true                           # 10: ENABLE_SENTRY
  - true                           # 11: ENABLE_TELEMETRY
```

**After adding AuthentikBlueprintStep** (runs after DatabaseStep, before StorageStep):

```bash
AVATAR_DEPLOY_DEBUG_PROMPTS=1 pytest ... | grep PROMPT
# [PROMPT #1] Public URL ...
# [PROMPT #2] Environment name ...
# [PROMPT #3] Organization name ...
# [PROMPT #4] Base domain for Avatar => 'smtp'  # ← WRONG! Using MAIL_PROVIDER value
```

**Fixed fixture** (inserted 4 responses at position 4):
```yaml
responses:
  - "https://avatar.example.com"   # 1: PUBLIC_URL
  - "production"                   # 2: ENV_NAME
  - "MyCompany"                    # 3: ORGANIZATION_NAME
  - "avatar.example.com"           # 4: BLUEPRINT_DOMAIN (NEW)
  - "avatar-api"                   # 5: BLUEPRINT_CLIENT_ID (NEW)
  - "https://avatar.example.com/api/login/sso/auth"  # 6: REDIRECT_URI (NEW)
  - "demo"                         # 7: LICENSE_TYPE (NEW)
  - "smtp"                         # 8: MAIL_PROVIDER (shifted from 4)
  - "smtp.example.com"             # 9: SMTP_HOST (shifted from 5)
  # ... all subsequent values shift by +4
```

## Advanced Topics

### Response Validation

Add validation to ensure fixtures are valid:

```python
def validate_responses(responses, expected_count):
    assert len(responses) == expected_count, \
        f"Expected {expected_count} responses, got {len(responses)}"
```


## Resources

- [Integration Tests README](integration/README.md) - Detailed integration test guide
- [pytest documentation](https://docs.pytest.org/) - Official pytest docs
- [CLITestHarness source](../src/octopize_avatar_deploy/cli_test_harness.py) - Implementation details
- [Fixture utilities source](fixtures/__init__.py) - FixtureManager implementation
