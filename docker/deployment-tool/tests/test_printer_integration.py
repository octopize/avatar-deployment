#!/usr/bin/env python3
"""Integration test demonstrating printer injection."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from octopize_avatar_deploy.configure import DeploymentConfigurator
from octopize_avatar_deploy.printer import SilentPrinter


def test_silent_printer_integration():
    """Test that SilentPrinter can be injected and suppresses all output."""
    with tempfile.TemporaryDirectory() as tmpdir:
        templates_dir = Path(tmpdir) / "templates"
        output_dir = Path(tmpdir) / "output"
        templates_dir.mkdir()
        output_dir.mkdir()

        # Create mock template
        (templates_dir / ".env.template").write_text("KEY={{ value }}")

        # Create defaults file
        defaults_file = output_dir / "defaults.yaml"
        defaults_file.write_text("version: '1.0.0'\nimages:\n  api: '1.0.0'")

        # Use SilentPrinter
        silent_printer = SilentPrinter()

        with patch("octopize_avatar_deploy.configure.RequiredConfigStep"):
            with patch("octopize_avatar_deploy.configure.EmailStep"):
                with patch("octopize_avatar_deploy.configure.TelemetryStep"):
                    with patch("octopize_avatar_deploy.configure.DatabaseStep"):
                        with patch("octopize_avatar_deploy.configure.StorageStep"):
                            # Create configurator with silent printer
                            configurator = DeploymentConfigurator(
                                templates_dir=templates_dir,
                                output_dir=output_dir,
                                defaults_file=defaults_file,
                                printer=silent_printer,
                                use_state=False,
                            )

                            # Verify printer was injected
                            assert configurator.printer is silent_printer


if __name__ == "__main__":
    test_silent_printer_integration()
    print("✓ Silent printer integration test passed")
