"""Tests for LoggingStep."""

import pytest

from octopize_avatar_deploy.input_gatherer import MockInputGatherer
from octopize_avatar_deploy.printer import SilentPrinter
from octopize_avatar_deploy.steps.logging import LoggingStep


@pytest.fixture
def defaults():
    """Sample defaults for logging tests."""
    return {
        "application": {
            "use_console_logging": "true",
            "log_level": "INFO",
        }
    }


@pytest.fixture
def logging_step(tmp_path, defaults):
    """Create a LoggingStep instance for testing."""
    printer = SilentPrinter()
    input_gatherer = MockInputGatherer([])
    config = {}
    return LoggingStep(
        output_dir=tmp_path,
        defaults=defaults,
        config=config,
        interactive=False,
        printer=printer,
        input_gatherer=input_gatherer,
    )


def test_collect_config_uses_defaults(logging_step, defaults):
    """Test that collect_config uses defaults for logging config."""
    config = logging_step.collect_config()

    assert config["USE_CONSOLE_LOGGING"] == defaults["application"]["use_console_logging"]
    assert config["LOG_LEVEL"] == defaults["application"]["log_level"]


def test_collect_config_respects_existing_console_logging(tmp_path, defaults):
    """Test that collect_config doesn't override existing USE_CONSOLE_LOGGING."""
    printer = SilentPrinter()
    input_gatherer = MockInputGatherer([])
    existing_config = {"USE_CONSOLE_LOGGING": "false"}

    step = LoggingStep(
        output_dir=tmp_path,
        defaults=defaults,
        config=existing_config,
        interactive=False,
        printer=printer,
        input_gatherer=input_gatherer,
    )

    config = step.collect_config()

    # Should not include USE_CONSOLE_LOGGING since it's already in config
    assert "USE_CONSOLE_LOGGING" not in config
    # LOG_LEVEL should still be included
    assert config["LOG_LEVEL"] == defaults["application"]["log_level"]


def test_collect_config_respects_existing_log_level(tmp_path, defaults):
    """Test that collect_config respects existing LOG_LEVEL."""
    printer = SilentPrinter()
    input_gatherer = MockInputGatherer([])
    existing_config = {"LOG_LEVEL": "DEBUG"}

    step = LoggingStep(
        output_dir=tmp_path,
        defaults=defaults,
        config=existing_config,
        interactive=False,
        printer=printer,
        input_gatherer=input_gatherer,
    )

    config = step.collect_config()

    assert config["LOG_LEVEL"] == "DEBUG"


def test_generate_secrets_returns_empty_dict(logging_step):
    """Test that generate_secrets returns an empty dict."""
    secrets = logging_step.generate_secrets()
    assert secrets == {}


def test_step_metadata(logging_step):
    """Test step metadata."""
    assert logging_step.name == "logging"
    assert logging_step.description == "Configure application logging settings"
    assert logging_step.required is False
