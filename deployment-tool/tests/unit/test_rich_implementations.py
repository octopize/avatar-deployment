"""Tests for Rich-based printer and input gatherer implementations."""

import pytest

from octopize_avatar_deploy.input_gatherer import RichInputGatherer
from octopize_avatar_deploy.printer import RichPrinter


class TestRichPrinter:
    """Test RichPrinter implementation."""

    def test_initialization(self):
        """Test RichPrinter can be initialized."""
        printer = RichPrinter()
        assert printer.console is not None

    def test_print(self, capsys):
        """Test basic print outputs text."""
        printer = RichPrinter()
        printer.print("test message")
        captured = capsys.readouterr()
        assert "test message" in captured.out

    def test_print_success(self, capsys):
        """Test success message includes checkmark."""
        printer = RichPrinter()
        printer.print_success("success message")
        captured = capsys.readouterr()
        assert "success message" in captured.out
        assert "✓" in captured.out

    def test_print_error(self, capsys):
        """Test error message includes X symbol."""
        printer = RichPrinter()
        printer.print_error("error message")
        captured = capsys.readouterr()
        assert "error message" in captured.out
        assert "✗" in captured.out

    def test_print_warning(self, capsys):
        """Test warning message includes warning symbol."""
        printer = RichPrinter()
        printer.print_warning("warning message")
        captured = capsys.readouterr()
        assert "warning message" in captured.out
        assert "⚠" in captured.out

    def test_print_header(self, capsys):
        """Test header is formatted with panel."""
        printer = RichPrinter()
        printer.print_header("Test Header")
        captured = capsys.readouterr()
        assert "Test Header" in captured.out

    def test_print_header_empty(self, capsys):
        """Test empty header just prints newline."""
        printer = RichPrinter()
        printer.print_header("")
        captured = capsys.readouterr()
        # Should just print a newline
        assert len(captured.out.strip()) == 0 or captured.out == "\n"

    def test_print_step(self, capsys):
        """Test step message is formatted."""
        printer = RichPrinter()
        printer.print_step("Step description")
        captured = capsys.readouterr()
        assert "Step description" in captured.out
        assert "---" in captured.out

    def test_print_step_skipped(self, capsys):
        """Test skipped step includes SKIPPED indicator."""
        printer = RichPrinter()
        printer.print_step("Skipped step", skipped=True)
        captured = capsys.readouterr()
        assert "Skipped step" in captured.out
        assert "SKIPPED" in captured.out


class TestRichInputGatherer:
    """Test RichInputGatherer implementation."""

    def test_initialization(self):
        """Test RichInputGatherer can be initialized."""
        gatherer = RichInputGatherer()
        assert gatherer.console is not None

    def test_prompt_with_default(self, monkeypatch):
        """Test prompt with default value returns default on Enter."""
        # Mock Prompt.ask to return empty string (simulating Enter)
        from rich.prompt import Prompt

        monkeypatch.setattr(Prompt, "ask", lambda *args, **kwargs: kwargs.get("default", ""))
        gatherer = RichInputGatherer()
        result = gatherer.prompt("Enter value", default="default_value")
        assert result == "default_value"

    def test_prompt_with_user_input(self, monkeypatch):
        """Test prompt returns user input when provided."""
        from rich.prompt import Prompt

        monkeypatch.setattr(Prompt, "ask", lambda *args, **kwargs: "user_input")
        gatherer = RichInputGatherer()
        result = gatherer.prompt("Enter value", default="default_value")
        assert result == "user_input"

    def test_prompt_without_default_requires_input(self, monkeypatch):
        """Test prompt without default requires non-empty input."""
        from rich.prompt import Prompt

        inputs = iter(["", "", "required_value"])  # Empty inputs, then valid

        def mock_ask(*args, **kwargs):
            return next(inputs)

        monkeypatch.setattr(Prompt, "ask", mock_ask)
        gatherer = RichInputGatherer()
        result = gatherer.prompt("Enter value")
        assert result == "required_value"

    def test_prompt_yes_no_default_true(self, monkeypatch):
        """Test yes/no prompt with default=True."""
        from rich.prompt import Confirm

        monkeypatch.setattr(Confirm, "ask", lambda *args, **kwargs: kwargs.get("default", True))
        gatherer = RichInputGatherer()
        result = gatherer.prompt_yes_no("Continue?", default=True)
        assert result is True

    def test_prompt_yes_no_default_false(self, monkeypatch):
        """Test yes/no prompt with default=False."""
        from rich.prompt import Confirm

        monkeypatch.setattr(Confirm, "ask", lambda *args, **kwargs: kwargs.get("default", False))
        gatherer = RichInputGatherer()
        result = gatherer.prompt_yes_no("Continue?", default=False)
        assert result is False

    def test_prompt_yes_no_accepts_yes(self, monkeypatch):
        """Test yes/no prompt accepts yes response."""
        from rich.prompt import Confirm

        monkeypatch.setattr(Confirm, "ask", lambda *args, **kwargs: True)
        gatherer = RichInputGatherer()
        result = gatherer.prompt_yes_no("Continue?", default=False)
        assert result is True

    def test_prompt_yes_no_accepts_no(self, monkeypatch):
        """Test yes/no prompt accepts no response."""
        from rich.prompt import Confirm

        monkeypatch.setattr(Confirm, "ask", lambda *args, **kwargs: False)
        gatherer = RichInputGatherer()
        result = gatherer.prompt_yes_no("Continue?", default=True)
        assert result is False

    def test_prompt_choice_returns_selected(self, monkeypatch, capsys):
        """Test choice prompt returns selected option."""
        from rich.prompt import IntPrompt

        monkeypatch.setattr(IntPrompt, "ask", lambda *args, **kwargs: 2)
        gatherer = RichInputGatherer()
        choices = ["option1", "option2", "option3"]
        result = gatherer.prompt_choice("Select option", choices)
        assert result == "option2"

    def test_prompt_choice_with_default(self, monkeypatch, capsys):
        """Test choice prompt uses default when provided."""
        from rich.prompt import IntPrompt

        monkeypatch.setattr(IntPrompt, "ask", lambda *args, **kwargs: kwargs.get("default", 1))
        gatherer = RichInputGatherer()
        choices = ["option1", "option2", "option3"]
        result = gatherer.prompt_choice("Select option", choices, default="option2")
        assert result == "option2"

    def test_prompt_choice_retries_on_invalid(self, monkeypatch, capsys):
        """Test choice prompt retries on invalid selection."""
        from rich.prompt import IntPrompt

        inputs = iter([0, 4, 2])  # Invalid, invalid, then valid

        def mock_ask(*args, **kwargs):
            return next(inputs)

        monkeypatch.setattr(IntPrompt, "ask", mock_ask)
        gatherer = RichInputGatherer()
        choices = ["option1", "option2", "option3"]
        result = gatherer.prompt_choice("Select option", choices)
        assert result == "option2"
