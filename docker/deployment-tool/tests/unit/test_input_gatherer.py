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
        gatherer = MockInputGatherer(["mocked_value"])
        result = gatherer.prompt("Enter value")
        assert result == "mocked_value"

    def test_prompt_uses_default_for_empty_response(self):
        """Test prompt uses default for empty mocked response."""
        gatherer = MockInputGatherer([""])
        result = gatherer.prompt("Enter value", default="default_value")
        assert result == "default_value"

    def test_prompt_yes_no_returns_boolean(self):
        """Test yes/no prompt returns boolean response."""
        gatherer = MockInputGatherer([True, False])
        assert gatherer.prompt_yes_no("First?") is True
        assert gatherer.prompt_yes_no("Second?") is False

    def test_prompt_yes_no_converts_string_to_bool(self):
        """Test yes/no prompt converts string responses to boolean."""
        gatherer = MockInputGatherer(["y", "yes", "n", "no"])
        assert gatherer.prompt_yes_no("First?") is True
        assert gatherer.prompt_yes_no("Second?") is True
        assert gatherer.prompt_yes_no("Third?") is False
        assert gatherer.prompt_yes_no("Fourth?") is False

    def test_prompt_choice_by_number(self):
        """Test choice prompt accepts numeric choice."""
        gatherer = MockInputGatherer(["2"])
        choices = ["option1", "option2", "option3"]
        result = gatherer.prompt_choice("Select", choices)
        assert result == "option2"

    def test_prompt_choice_by_name(self):
        """Test choice prompt accepts choice name directly."""
        gatherer = MockInputGatherer(["option3"])
        choices = ["option1", "option2", "option3"]
        result = gatherer.prompt_choice("Select", choices)
        assert result == "option3"

    def test_prompt_choice_uses_default_for_empty(self):
        """Test choice prompt uses default for empty response."""
        gatherer = MockInputGatherer([""])
        choices = ["option1", "option2", "option3"]
        result = gatherer.prompt_choice("Select", choices, default="option2")
        assert result == "option2"

    def test_multiple_prompts_in_sequence(self):
        """Test multiple prompts consume responses in order."""
        gatherer = MockInputGatherer(["first", "second", True, "3"])
        assert gatherer.prompt("Q1") == "first"
        assert gatherer.prompt("Q2") == "second"
        assert gatherer.prompt_yes_no("Q3") is True
        assert gatherer.prompt_choice("Q4", ["a", "b", "c"]) == "c"

    def test_runs_out_of_responses(self):
        """Test error when running out of pre-configured responses."""
        gatherer = MockInputGatherer(["only_one"])
        gatherer.prompt("Q1")
        with pytest.raises(ValueError, match="ran out of responses"):
            gatherer.prompt("Q2")

    def test_prompt_raises_on_bool_response(self):
        """Test prompt raises TypeError when receiving bool instead of string."""
        gatherer = MockInputGatherer([True])
        with pytest.raises(TypeError, match="Expected string response, got bool"):
            gatherer.prompt("Q1")

    def test_prompt_choice_raises_on_bool_response(self):
        """Test prompt_choice raises TypeError when receiving bool."""
        gatherer = MockInputGatherer([True])
        with pytest.raises(TypeError, match="Expected string response, got bool"):
            gatherer.prompt_choice("Q1", ["a", "b"])
