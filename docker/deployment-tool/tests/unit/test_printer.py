#!/usr/bin/env python3
"""Tests for printer abstraction."""

import pytest

from octopize_avatar_deploy.printer import ConsolePrinter, SilentPrinter


class TestConsolePrinter:
    """Test the ConsolePrinter implementation."""

    def test_print(self, capsys):
        """Test basic print functionality."""
        printer = ConsolePrinter()
        printer.print("Hello World")

        captured = capsys.readouterr()
        assert "Hello World" in captured.out

    def test_print_empty(self, capsys):
        """Test printing empty line."""
        printer = ConsolePrinter()
        printer.print()

        captured = capsys.readouterr()
        assert captured.out == "\n"

    def test_print_header(self, capsys):
        """Test header printing."""
        printer = ConsolePrinter()
        printer.print_header("Test Header")

        captured = capsys.readouterr()
        assert "=" * 60 in captured.out
        assert "Test Header" in captured.out

    def test_print_header_custom_width(self, capsys):
        """Test header with custom width."""
        printer = ConsolePrinter()
        printer.print_header("Test", width=40)

        captured = capsys.readouterr()
        assert "=" * 40 in captured.out

    def test_print_success(self, capsys):
        """Test success message printing."""
        printer = ConsolePrinter()
        printer.print_success("Operation successful")

        captured = capsys.readouterr()
        assert "✓ Operation successful" in captured.out

    def test_print_error(self, capsys):
        """Test error message printing."""
        printer = ConsolePrinter()
        printer.print_error("Something went wrong")

        captured = capsys.readouterr()
        assert "✗ Something went wrong" in captured.out

    def test_print_warning(self, capsys):
        """Test warning message printing."""
        printer = ConsolePrinter()
        printer.print_warning("Be careful")

        captured = capsys.readouterr()
        assert "⚠ Be careful" in captured.out

    def test_print_step_normal(self, capsys):
        """Test step header printing."""
        printer = ConsolePrinter()
        printer.print_step("Configure Email")

        captured = capsys.readouterr()
        assert "--- Configure Email ---" in captured.out

    def test_print_step_skipped(self, capsys):
        """Test step header with skipped indicator."""
        printer = ConsolePrinter()
        printer.print_step("Configure Email", skipped=True)

        captured = capsys.readouterr()
        assert "--- Configure Email [SKIPPED - already completed] ---" in captured.out


class TestSilentPrinter:
    """Test the SilentPrinter implementation."""

    def test_print_silent(self, capsys):
        """Test that silent printer produces no output."""
        printer = SilentPrinter()
        printer.print("Hello World")

        captured = capsys.readouterr()
        assert captured.out == ""

    def test_print_header_silent(self, capsys):
        """Test that header is silent."""
        printer = SilentPrinter()
        printer.print_header("Test Header")

        captured = capsys.readouterr()
        assert captured.out == ""

    def test_print_success_silent(self, capsys):
        """Test that success messages are silent."""
        printer = SilentPrinter()
        printer.print_success("Success!")

        captured = capsys.readouterr()
        assert captured.out == ""

    def test_print_error_silent(self, capsys):
        """Test that error messages are silent."""
        printer = SilentPrinter()
        printer.print_error("Error!")

        captured = capsys.readouterr()
        assert captured.out == ""

    def test_print_warning_silent(self, capsys):
        """Test that warning messages are silent."""
        printer = SilentPrinter()
        printer.print_warning("Warning!")

        captured = capsys.readouterr()
        assert captured.out == ""

    def test_print_step_silent(self, capsys):
        """Test that step messages are silent."""
        printer = SilentPrinter()
        printer.print_step("Step 1")
        printer.print_step("Step 2", skipped=True)

        captured = capsys.readouterr()
        assert captured.out == ""
