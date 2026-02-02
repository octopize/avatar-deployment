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

## Creating New Test

See [Testing Documentation](TESTING_GUIDE.md) for detailed instructions.

## Environment Variables

- `AVATAR_DEPLOY_UPDATE_FIXTURES=1` - Update expected output fixtures
- `AVATAR_DEPLOY_TEST_MODE=1` - Enable test mode (set by CLITestHarness)
- `AVATAR_DEPLOY_TEST_SILENT=1` - Silent mode (set by CLITestHarness)
- `AVATAR_DEPLOY_TEST_LOG_FILE=<path>` - Log file path (set by CLITestHarness)
- `AVATAR_DEPLOY_TEST_RESPONSES=<serialized>` - Serialized responses (set by CLITestHarness)
- `AVATAR_DEPLOY_DEBUG_PROMPTS=1` - Enable debug logging for input prompts
