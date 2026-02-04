"""Tests for input gatherer implementations."""

import pytest

from octopize_avatar_deploy.input_gatherer import (
    ConsoleInputGatherer,
    MockInputGatherer,
)


class TestConsoleInputGatherer:
    """Test ConsoleInputGatherer implementation."""

    def test_prompt_with_default(self, monkeypatch):
        """Test prompt with default value when user presses Enter."""
        monkeypatch.setattr("builtins.input", lambda _: "")
        gatherer = ConsoleInputGatherer()
        result = gatherer.prompt("Enter value", default="default_value")
        assert result == "default_value"

    def test_prompt_with_user_input(self, monkeypatch):
        """Test prompt returns user input when provided."""
        monkeypatch.setattr("builtins.input", lambda _: "user_input")
        gatherer = ConsoleInputGatherer()
        result = gatherer.prompt("Enter value", default="default_value")
        assert result == "user_input"

    def test_prompt_without_default_requires_input(self, monkeypatch):
        """Test prompt without default requires non-empty input."""
        inputs = iter(["", "", "required_value"])  # Empty inputs, then valid
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        gatherer = ConsoleInputGatherer()
        result = gatherer.prompt("Enter value")
        assert result == "required_value"

    def test_prompt_yes_no_default_true(self, monkeypatch):
        """Test yes/no prompt with default=True when user presses Enter."""
        monkeypatch.setattr("builtins.input", lambda _: "")
        gatherer = ConsoleInputGatherer()
        result = gatherer.prompt_yes_no("Continue?", default=True)
        assert result is True

    def test_prompt_yes_no_default_false(self, monkeypatch):
        """Test yes/no prompt with default=False when user presses Enter."""
        monkeypatch.setattr("builtins.input", lambda _: "")
        gatherer = ConsoleInputGatherer()
        result = gatherer.prompt_yes_no("Continue?", default=False)
        assert result is False

    def test_prompt_yes_no_accepts_yes(self, monkeypatch):
        """Test yes/no prompt accepts various yes inputs."""
        for yes_input in ["y", "yes", "Y", "YES", "true", "1"]:
            monkeypatch.setattr("builtins.input", lambda _, val=yes_input: val)
            gatherer = ConsoleInputGatherer()
            result = gatherer.prompt_yes_no("Continue?", default=False)
            assert result is True

    def test_prompt_yes_no_rejects_no(self, monkeypatch):
        """Test yes/no prompt rejects non-yes inputs."""
        for no_input in ["n", "no", "N", "NO", "false", "0", "nope"]:
            monkeypatch.setattr("builtins.input", lambda _, val=no_input: val)
            gatherer = ConsoleInputGatherer()
            result = gatherer.prompt_yes_no("Continue?", default=True)
            assert result is False

    def test_prompt_choice_returns_selected(self, monkeypatch, capsys):
        """Test choice prompt returns selected option."""
        monkeypatch.setattr("builtins.input", lambda _: "2")
        gatherer = ConsoleInputGatherer()
        choices = ["option1", "option2", "option3"]
        result = gatherer.prompt_choice("Select option", choices)
        assert result == "option2"

    def test_prompt_choice_with_default(self, monkeypatch, capsys):
        """Test choice prompt uses default when user presses Enter."""
        monkeypatch.setattr("builtins.input", lambda _: "")
        gatherer = ConsoleInputGatherer()
        choices = ["option1", "option2", "option3"]
        result = gatherer.prompt_choice("Select option", choices, default="option2")
        assert result == "option2"

    def test_prompt_choice_rejects_invalid_number(self, monkeypatch, capsys):
        """Test choice prompt rejects invalid numbers and retries."""
        inputs = iter(["0", "4", "2"])  # Invalid, invalid, then valid
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        gatherer = ConsoleInputGatherer()
        choices = ["option1", "option2", "option3"]
        result = gatherer.prompt_choice("Select option", choices)
        assert result == "option2"

    def test_prompt_choice_rejects_non_numeric(self, monkeypatch, capsys):
        """Test choice prompt rejects non-numeric input and retries."""
        inputs = iter(["abc", "xyz", "1"])  # Invalid strings, then valid
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))
        gatherer = ConsoleInputGatherer()
        choices = ["option1", "option2", "option3"]
        result = gatherer.prompt_choice("Select option", choices)
        assert result == "option1"


class TestMockInputGatherer:
    """Test MockInputGatherer implementation."""

    def test_prompt_returns_mocked_response(self):
        """Test prompt returns pre-configured response."""
        gatherer = MockInputGatherer({"test.value": "mocked_value"})
        result = gatherer.prompt("Enter value", key="test.value")
        assert result == "mocked_value"

    def test_prompt_uses_default_for_empty_response(self):
        """Test prompt uses default for empty mocked response."""
        gatherer = MockInputGatherer({"test.value": ""})
        result = gatherer.prompt("Enter value", default="default_value", key="test.value")
        assert result == "default_value"

    def test_prompt_yes_no_returns_boolean(self):
        """Test yes/no prompt returns boolean response."""
        gatherer = MockInputGatherer({"test.first": True, "test.second": False})
        assert gatherer.prompt_yes_no("First?", key="test.first") is True
        assert gatherer.prompt_yes_no("Second?", key="test.second") is False

    def test_prompt_yes_no_converts_string_to_bool(self):
        """Test yes/no prompt converts string responses to boolean."""
        gatherer = MockInputGatherer({"q1": "y", "q2": "yes", "q3": "n", "q4": "no"})
        assert gatherer.prompt_yes_no("First?", key="q1") is True
        assert gatherer.prompt_yes_no("Second?", key="q2") is True
        assert gatherer.prompt_yes_no("Third?", key="q3") is False
        assert gatherer.prompt_yes_no("Fourth?", key="q4") is False

    def test_prompt_choice_by_number(self):
        """Test choice prompt accepts numeric choice."""
        gatherer = MockInputGatherer({"test.choice": "2"})
        choices = ["option1", "option2", "option3"]
        result = gatherer.prompt_choice("Select", choices, key="test.choice")
        assert result == "option2"

    def test_prompt_choice_by_name(self):
        """Test choice prompt accepts choice name directly."""
        gatherer = MockInputGatherer({"test.choice": "option3"})
        choices = ["option1", "option2", "option3"]
        result = gatherer.prompt_choice("Select", choices, key="test.choice")
        assert result == "option3"

    def test_prompt_choice_uses_default_for_empty(self):
        """Test choice prompt uses default for empty response."""
        gatherer = MockInputGatherer({"test.choice": ""})
        choices = ["option1", "option2", "option3"]
        result = gatherer.prompt_choice("Select", choices, default="option2", key="test.choice")
        assert result == "option2"

    def test_multiple_prompts_with_different_keys(self):
        """Test multiple prompts with different keys."""
        gatherer = MockInputGatherer({"q1": "first", "q2": "second", "q3": True, "q4": "3"})
        assert gatherer.prompt("Q1", key="q1") == "first"
        assert gatherer.prompt("Q2", key="q2") == "second"
        assert gatherer.prompt_yes_no("Q3", key="q3") is True
        assert gatherer.prompt_choice("Q4", ["a", "b", "c"], key="q4") == "c"

    def test_missing_key_raises_error(self):
        """Test error when key not found in responses."""
        gatherer = MockInputGatherer({"existing.key": "value"})
        with pytest.raises(KeyError, match="No response configured for key 'missing.key'"):
            gatherer.prompt("Q1", key="missing.key")

    def test_no_key_raises_error(self):
        """Test error when no key provided."""
        gatherer = MockInputGatherer({"test.key": "value"})
        with pytest.raises(ValueError, match="requires a 'key' parameter"):
            gatherer.prompt("Q1")

    def test_duplicate_key_raises_error(self):
        """Test error when same key is used twice."""
        gatherer = MockInputGatherer({"test.key": "value"})
        gatherer.prompt("Q1", key="test.key")
        with pytest.raises(ValueError, match="Key 'test.key' has already been used"):
            gatherer.prompt("Q2", key="test.key")

    def test_prompt_raises_on_bool_response(self):
        """Test prompt raises TypeError when receiving bool instead of string."""
        gatherer = MockInputGatherer({"test.key": True})
        with pytest.raises(TypeError, match="Expected string response.*got bool"):
            gatherer.prompt("Q1", key="test.key")

    def test_prompt_choice_raises_on_bool_response(self):
        """Test prompt_choice raises TypeError when receiving bool."""
        gatherer = MockInputGatherer({"test.key": True})
        with pytest.raises(TypeError, match="Expected string response.*got bool"):
            gatherer.prompt_choice("Q1", ["a", "b"], key="test.key")
