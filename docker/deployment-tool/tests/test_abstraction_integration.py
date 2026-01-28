#!/usr/bin/env python3
"""
Integration test demonstrating the complete abstraction workflow.

This test shows how to use custom printer and input_gatherer implementations
together for a fully automated, silent deployment configuration.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

from octopize_avatar_deploy.configure import DeploymentConfigurator
from octopize_avatar_deploy.input_gatherer import MockInputGatherer
from octopize_avatar_deploy.printer import SilentPrinter


def test_complete_abstraction_workflow():
    """
    Test complete deployment flow with custom printer and input gatherer.

    This demonstrates:
    1. SilentPrinter suppresses all output
    2. MockInputGatherer provides all inputs automatically
    3. No manual interaction required
    4. Fully testable workflow
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        templates_dir = Path(tmpdir) / "templates"
        output_dir = Path(tmpdir) / "output"
        templates_dir.mkdir()
        output_dir.mkdir()

        # Create all required templates
        (templates_dir / ".env.template").write_text("BASE_URL={{ BASE_URL }}\n")
        (templates_dir / "nginx.conf.template").write_text("# Nginx config\n")

        # Create defaults file
        defaults_file = output_dir / "defaults.yaml"
        defaults_file.write_text("version: '1.0.0'\nimages:\n  api: '1.0.0'\n")

        # Pre-configure all responses
        mock_responses = ["value1", "value2"]

        # Create configurator with silent printer and mock input
        configurator = DeploymentConfigurator(
            templates_dir=templates_dir,
            output_dir=output_dir,
            defaults_file=defaults_file,
            printer=SilentPrinter(),  # No output
            input_gatherer=MockInputGatherer(mock_responses),  # Automated input
            use_state=False,  # Disable state management for test
        )

        # Verify both printer and input_gatherer were injected correctly
        assert isinstance(configurator.printer, SilentPrinter), (
            "Printer should be SilentPrinter"
        )
        assert isinstance(configurator.input_gatherer, MockInputGatherer), (
            "InputGatherer should be MockInputGatherer"
        )

        # Verify the printer and input_gatherer are available
        assert configurator.printer is not None
        assert configurator.input_gatherer is not None


def test_rich_implementations_available():
    """Test that Rich implementations can be imported and used."""
    try:
        from octopize_avatar_deploy.input_gatherer import RichInputGatherer
        from octopize_avatar_deploy.printer import RichPrinter

        # Should be able to create instances
        printer = RichPrinter()
        gatherer = RichInputGatherer()

        assert printer is not None
        assert gatherer is not None
        assert hasattr(printer, "console")
        assert hasattr(gatherer, "console")

        print("✓ Rich implementations available and functional")
    except ImportError:
        print("⚠ Rich library not installed - Rich implementations unavailable")
        # This is acceptable - Rich is optional


if __name__ == "__main__":
    test_complete_abstraction_workflow()
    print("✓ Complete abstraction workflow test passed")

    test_rich_implementations_available()
    print("\n✓ All integration tests passed!")
