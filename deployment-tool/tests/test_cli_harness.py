"""
Tests for CLI Test Harness

These tests verify that the CLI can be tested with pre-configured responses
and that output can be captured for debugging.
"""

import os
import tempfile
from pathlib import Path

import pytest

from octopize_avatar_deploy.cli_test_harness import (
    CLITestHarness,
    get_test_input_gatherer,
    get_test_printer,
    run_cli_test,
)
from octopize_avatar_deploy.input_gatherer import MockInputGatherer
from octopize_avatar_deploy.printer import FilePrinter, SilentPrinter


class TestCLITestHarness:
    """Tests for CLITestHarness context manager."""

    def test_harness_basic(self):
        """Test basic harness creation and context manager."""
        harness = CLITestHarness(
            responses={"test.1": "test1", "test.2": "test2"},
            args=["--help"],
            silent=True,
        )
        assert harness.responses == {"test.1": "test1", "test.2": "test2"}
        assert harness.args == ["--help"]
        assert harness.silent is True
        assert harness.log_file is None

    def test_harness_context_manager_sets_env(self):
        """Test that context manager sets up environment correctly."""
        responses = {"test.1": "response1", "test.2": "response2"}

        with CLITestHarness(responses=responses, silent=True):
            # Check environment variables are set
            assert os.environ.get("AVATAR_DEPLOY_TEST_MODE") == "1"
            assert os.environ.get("AVATAR_DEPLOY_TEST_SILENT") == "1"
            assert "AVATAR_DEPLOY_TEST_RESPONSES" in os.environ

            # Verify serialization works
            test_gatherer = get_test_input_gatherer()
            assert isinstance(test_gatherer, MockInputGatherer)

        # Check environment is cleaned up
        assert os.environ.get("AVATAR_DEPLOY_TEST_MODE") is None
        assert os.environ.get("AVATAR_DEPLOY_TEST_SILENT") is None
        assert os.environ.get("AVATAR_DEPLOY_TEST_RESPONSES") is None

    def test_serialize_deserialize_responses(self):
        """Test response serialization/deserialization."""
        # Test with mixed types
        original = {"test.1": "text1", "test.2": True, "test.3": False, "test.4": "text2"}

        serialized = CLITestHarness.serialize_responses(original)
        deserialized = CLITestHarness.deserialize_responses(serialized)

        assert deserialized == original

    def test_serialize_empty_responses(self):
        """Test serialization of empty response dict."""
        original = {}
        serialized = CLITestHarness.serialize_responses(original)
        deserialized = CLITestHarness.deserialize_responses(serialized)

        assert deserialized == {}
        assert serialized == "{}"

    def test_get_test_input_gatherer_no_test_mode(self):
        """Test that get_test_input_gatherer returns None when not in test mode."""
        # Ensure we're not in test mode
        os.environ.pop("AVATAR_DEPLOY_TEST_MODE", None)

        result = get_test_input_gatherer()
        assert result is None

    def test_get_test_input_gatherer_with_responses(self):
        """
        Test that get_test_input_gatherer returns MockInputGatherer
        with responses.
        """
        responses = {"test.1": "test1", "test.2": "test2", "test.3": True}

        with CLITestHarness(responses=responses):
            gatherer = get_test_input_gatherer()
            assert isinstance(gatherer, MockInputGatherer)
            # Verify responses are available
            assert gatherer.prompt("Prompt", key="test.1") == "test1"
            assert gatherer.prompt("Prompt", key="test.2") == "test2"
            assert gatherer.prompt_yes_no("Prompt", key="test.3") is True

    def test_get_test_printer_silent_mode(self):
        """Test that get_test_printer returns SilentPrinter in silent mode."""
        with CLITestHarness(responses=[], silent=True):
            printer = get_test_printer()
            assert isinstance(printer, SilentPrinter)

    def test_get_test_printer_file_mode(self):
        """Test that get_test_printer returns FilePrinter when log file specified."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            log_file = Path(tmp_dir) / "test.log"

            with CLITestHarness(responses=[], log_file=log_file):
                printer = get_test_printer()
                assert isinstance(printer, FilePrinter)

    def test_get_test_printer_no_test_mode(self):
        """Test that get_test_printer returns None when not in test mode."""
        os.environ.pop("AVATAR_DEPLOY_TEST_MODE", None)
        os.environ.pop("AVATAR_DEPLOY_TEST_SILENT", None)
        os.environ.pop("AVATAR_DEPLOY_TEST_LOG_FILE", None)

        result = get_test_printer()
        assert result is None


class TestFilePrinterLogging:
    """Tests for file printer logging functionality."""

    def test_file_printer_creates_log_file(self):
        """Test that file printer creates log file and writes to it."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            log_file = Path(tmp_dir) / "test.log"

            printer = FilePrinter(log_file)
            printer.print("Test message")
            printer.print_success("Success message")
            printer.print_error("Error message")

            # Verify file was created and contains messages
            assert log_file.exists()
            content = log_file.read_text()
            assert "Test message" in content
            assert "Success message" in content
            assert "Error message" in content

    def test_file_printer_append_mode(self):
        """Test that file printer can append to existing log."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            log_file = Path(tmp_dir) / "test.log"

            # Write initial content
            printer1 = FilePrinter(log_file)
            printer1.print("First message")

            # Append more content
            printer2 = FilePrinter(log_file, append=True)
            printer2.print("Second message")

            # Verify both messages are in file
            content = log_file.read_text()
            assert "First message" in content
            assert "Second message" in content

    def test_file_printer_overwrite_mode(self):
        """Test that file printer overwrites existing log by default."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            log_file = Path(tmp_dir) / "test.log"

            # Write initial content
            printer1 = FilePrinter(log_file)
            printer1.print("First message")

            # Overwrite with new content
            printer2 = FilePrinter(log_file, append=False)
            printer2.print("Second message")

            # Verify only second message is in file
            content = log_file.read_text()
            assert "First message" not in content
            assert "Second message" in content

    def test_file_printer_creates_parent_directories(self):
        """Test that file printer creates parent directories if needed."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            log_file = Path(tmp_dir) / "subdir" / "nested" / "test.log"

            printer = FilePrinter(log_file)
            printer.print("Test message")

            # Verify parent directories were created
            assert log_file.exists()
            assert log_file.parent.exists()
            assert "Test message" in log_file.read_text()


class TestConvenienceFunction:
    """Tests for run_cli_test convenience function."""

    def test_run_cli_test_basic(self):
        """Test basic usage of run_cli_test."""
        # Test with --help which should exit successfully
        exit_code = run_cli_test(
            responses=[],
            args=["--help"],
            silent=True,
        )

        # --help exits with 0
        assert exit_code == 0

    def test_run_cli_test_with_log_file(self):
        """Test run_cli_test with file logging."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            log_file = Path(tmp_dir) / "test.log"

            exit_code = run_cli_test(
                responses=[],
                args=["--help"],
                log_file=log_file,
            )

            # --help should exit successfully even with logging
            assert exit_code == 0
            # Note: help output goes to stdout, not via printer,
            # so log file may be empty or may not exist


class TestEnvironmentCleanup:
    """Tests to ensure environment variables are properly cleaned up."""

    def test_original_env_restored_on_success(self):
        """Test that original environment is restored after successful context."""
        # Set some original values
        os.environ["AVATAR_DEPLOY_TEST_MODE"] = "original"
        original_value = os.environ.get("AVATAR_DEPLOY_TEST_MODE")

        with CLITestHarness(responses={"test": "test"}, silent=True):
            # In context, value should be "1"
            assert os.environ.get("AVATAR_DEPLOY_TEST_MODE") == "1"

        # After context, original value should be restored
        assert os.environ.get("AVATAR_DEPLOY_TEST_MODE") == original_value

        # Clean up
        del os.environ["AVATAR_DEPLOY_TEST_MODE"]

    def test_original_env_restored_on_exception(self):
        """Test that original environment is restored even if exception occurs."""
        os.environ["AVATAR_DEPLOY_TEST_MODE"] = "original"
        original_value = os.environ.get("AVATAR_DEPLOY_TEST_MODE")

        try:
            with CLITestHarness(responses={"test": "test"}, silent=True):
                assert os.environ.get("AVATAR_DEPLOY_TEST_MODE") == "1"
                raise ValueError("Test exception")
        except ValueError:
            pass

        # After exception, original value should be restored
        assert os.environ.get("AVATAR_DEPLOY_TEST_MODE") == original_value

        # Clean up
        del os.environ["AVATAR_DEPLOY_TEST_MODE"]

    def test_env_removed_if_not_originally_set(self):
        """Test that env vars are removed if they weren't originally set."""
        # Ensure not set initially
        os.environ.pop("AVATAR_DEPLOY_TEST_MODE", None)
        os.environ.pop("AVATAR_DEPLOY_TEST_SILENT", None)

        with CLITestHarness(responses={"test": "test"}, silent=True):
            # Variables should be set in context
            assert os.environ.get("AVATAR_DEPLOY_TEST_MODE") == "1"
            assert os.environ.get("AVATAR_DEPLOY_TEST_SILENT") == "1"

        # After context, variables should be removed (not just empty)
        assert "AVATAR_DEPLOY_TEST_MODE" not in os.environ
        assert "AVATAR_DEPLOY_TEST_SILENT" not in os.environ
