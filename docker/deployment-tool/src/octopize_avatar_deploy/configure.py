#!/usr/bin/env python3
"""
Avatar Deployment Configuration Tool

This script coordinates the deployment configuration process by:
1. Loading configuration from files or user input
2. Executing deployment steps in sequence
3. Generating configuration files from templates
4. Managing deployment state for resumption

Usage:
    # Interactive mode
    python configure.py

    # Non-interactive mode with config file
    python configure.py --config config.yaml

    # Specify output directory
    python configure.py --output-dir /app/avatar
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, FileSystemLoader

from octopize_avatar_deploy.download_templates import (
    download_templates,
)
from octopize_avatar_deploy.input_gatherer import (
    ConsoleInputGatherer,
    InputGatherer,
    RichInputGatherer,
)
from octopize_avatar_deploy.printer import ConsolePrinter, Printer, RichPrinter
from octopize_avatar_deploy.state_manager import DeploymentState
from octopize_avatar_deploy.steps import (
    DatabaseStep,
    EmailStep,
    RequiredConfigStep,
    StorageStep,
    TelemetryStep,
)


class DeploymentConfigurator:
    """
    Coordinates Avatar deployment configuration using modular steps.

    This class acts as an executor that:
    - Loads defaults and configuration
    - Executes deployment steps in order
    - Generates configuration files from templates
    - Manages deployment state
    """

    def __init__(
        self,
        templates_dir: Path,
        output_dir: Path,
        defaults_file: Path | None = None,
        config: dict[str, Any] | None = None,
        use_state: bool = True,
        printer: Printer | None = None,
        input_gatherer: InputGatherer | None = None,
    ):
        """
        Initialize the configurator.

        Args:
            templates_dir: Path to templates directory
            output_dir: Path where configuration files will be generated
            defaults_file: Path to defaults.yaml file
            config: Optional pre-loaded configuration dict
            use_state: Whether to use state management for resuming
            printer: Optional printer for output (defaults to ConsolePrinter)
        """
        self.templates_dir = Path(templates_dir)
        self.output_dir = Path(output_dir)
        self.config = config or {}
        self.use_state = use_state

        # Use Rich implementations if in interactive terminal, otherwise Console
        if printer is None:
            # Only use Rich if stdout is a TTY (interactive terminal)
            if sys.stdout.isatty():
                self.printer: Printer = RichPrinter()
            else:
                self.printer = ConsolePrinter()
        else:
            self.printer = printer

        if input_gatherer is None:
            # Only use Rich if stdin is a TTY (interactive terminal)
            if sys.stdin.isatty():
                self.input_gatherer: InputGatherer = RichInputGatherer()
            else:
                self.input_gatherer = ConsoleInputGatherer()
        else:
            self.input_gatherer = input_gatherer

        # Initialize state manager
        self.state: DeploymentState | None
        if use_state:
            state_file = self.output_dir / ".deployment-state.yaml"
            self.state = DeploymentState(state_file)
        else:
            self.state = None

        # Load defaults
        self.defaults = self._load_defaults(defaults_file)

        # Initialize Jinja2 environment
        self.env = Environment(
            loader=FileSystemLoader(self.templates_dir),
            variable_start_string="{{",
            variable_end_string="}}",
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def _load_defaults(self, defaults_file: Path | None = None) -> dict[str, Any]:
        """Load default configuration from defaults.yaml."""
        if defaults_file and defaults_file.exists():
            with open(defaults_file) as f:
                return yaml.safe_load(f)
        else:
            # Try to find defaults.yaml in the same directory as this script
            script_dir = Path(__file__).parent
            default_defaults = script_dir / "defaults.yaml"
            if default_defaults.exists():
                with open(default_defaults) as f:
                    return yaml.safe_load(f)
            else:
                raise FileNotFoundError(
                    f"defaults.yaml not found at {defaults_file} or {default_defaults}"
                )

    def render_template(self, template_name: str, output_name: str) -> None:
        """
        Render a template file with configuration values.

        Args:
            template_name: Name of the template file
            output_name: Name of the output file
        """
        try:
            template = self.env.get_template(template_name)
            rendered = template.render(**self.config)

            output_path = self.output_dir / output_name
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(rendered)

            self.printer.print_success(f"Generated: {output_path}")
        except Exception as e:
            self.printer.print_error(f"Error rendering {template_name}: {e}")
            raise

    def generate_configs(self) -> None:
        """Generate all configuration files from templates."""
        self.printer.print_header("Generating Configuration Files")

        # Generate .env file
        self.render_template(".env.template", ".env")

        # Generate nginx.conf
        nginx_dir = self.output_dir / "nginx"
        nginx_dir.mkdir(parents=True, exist_ok=True)
        self.render_template("nginx.conf.template", "nginx/nginx.conf")

        self.printer.print()
        self.printer.print_success("Configuration files generated successfully!")

    def save_config_to_file(self, config_file: Path) -> None:
        """Save current configuration to a YAML file."""
        with open(config_file, "w") as f:
            yaml.dump(self.config, f, default_flow_style=False, sort_keys=False)
        self.printer.print()
        self.printer.print_success(f"Configuration saved to {config_file}")

    def write_secrets(self, secrets: dict[str, str]) -> None:
        """
        Write secrets to the .secrets/ directory.

        Args:
            secrets: Dictionary of {filename: secret_value}
        """
        secrets_dir = self.output_dir / ".secrets"
        secrets_dir.mkdir(parents=True, exist_ok=True)

        for secret_name, secret_value in secrets.items():
            secret_file = secrets_dir / secret_name
            secret_file.write_text(secret_value)

    def run(
        self,
        interactive: bool = True,
        config_file: Path | None = None,
        save_config: bool = False,
    ) -> None:
        """
        Run the configuration process using step-based architecture.

        Args:
            interactive: Whether to prompt for values interactively
            config_file: Path to YAML config file to load
            save_config: Whether to save configuration to file
        """
        # Check for existing state and prompt to resume or restart
        if self.state and self.state.has_started() and not self.state.is_complete():
            if interactive:
                self.state.print_status()
                self.printer.print_header("")
                response = self.input_gatherer.prompt_yes_no(
                    "Resume from where you left off?", default=True
                )
                if not response:
                    self.printer.print("Starting fresh configuration...")
                    self.state.reset()
                else:
                    self.printer.print("Resuming from last completed step...")
                    # Load saved config from state
                    self.config.update(self.state.get_config())
            else:
                # Non-interactive mode: always resume if state exists
                self.config.update(self.state.get_config())

        # Load configuration from file if provided
        if config_file and config_file.exists():
            self.printer.print(f"Loading configuration from {config_file}...")
            with open(config_file) as f:
                loaded_config = yaml.safe_load(f) or {}
            self.config.update(loaded_config)

        # Define deployment steps
        steps = [
            RequiredConfigStep(
                self.output_dir,
                self.defaults,
                self.config,
                interactive,
                self.printer,
                self.input_gatherer,
            ),
            EmailStep(
                self.output_dir,
                self.defaults,
                self.config,
                interactive,
                self.printer,
                self.input_gatherer,
            ),
            TelemetryStep(
                self.output_dir,
                self.defaults,
                self.config,
                interactive,
                self.printer,
                self.input_gatherer,
            ),
            DatabaseStep(
                self.output_dir,
                self.defaults,
                self.config,
                interactive,
                self.printer,
                self.input_gatherer,
            ),
            StorageStep(
                self.output_dir,
                self.defaults,
                self.config,
                interactive,
                self.printer,
                self.input_gatherer,
            ),
        ]

        self.printer.print_header("Avatar Deployment Configuration")
        self.printer.print()
        self.printer.print("Executing configuration steps...")
        self.printer.print()

        # Execute each step
        all_secrets = {}
        for i, step in enumerate(steps):
            step_name = f"step_{i}_{step.name}"

            # Skip if step already completed (when resuming)
            if self.state and self.state.is_step_completed(step_name):
                self.printer.print_step(step.description, skipped=True)
                continue

            self.printer.print_step(step.description)

            # Mark step as started in state
            if self.state:
                self.state.mark_step_started(step_name)

            # Collect configuration from step
            step_config = step.collect_config()
            self.config.update(step_config)

            # Generate secrets from step
            step_secrets = step.generate_secrets()
            all_secrets.update(step_secrets)

            # Validate step
            if not step.validate():
                raise ValueError(f"Validation failed for step: {step.name}")

            # Mark step as completed and save config to state
            if self.state:
                self.state.mark_step_completed(step_name)
                self.state.update_config(self.config)

        # Generate configuration files
        self.generate_configs()

        # Write all secrets
        if all_secrets:
            self.printer.print()
            self.printer.print(
                f"Writing {len(all_secrets)} secrets to .secrets/ directory..."
            )
            self.write_secrets(all_secrets)
            self.printer.print_success("Secrets written successfully")

        # Save config if requested
        if save_config:
            config_output = self.output_dir / "deployment-config.yaml"
            self.save_config_to_file(config_output)

        # Success message
        self.printer.print_header("Configuration Complete!")
        self.printer.print(f"\nConfiguration files generated in: {self.output_dir}")
        self.printer.print("\nNext steps:")
        self.printer.print("1. Review and edit the generated .env file")
        self.printer.print("2. Fill in any remaining secrets in .secrets/ directory")
        self.printer.print("3. Configure TLS certificates in the tls/ directory")
        self.printer.print("4. Run: docker compose up -d")


class DeploymentRunner:
    """
    High-level orchestrator for the Avatar deployment process.

    This class provides a CLI-independent entry point that coordinates:
    - Template downloading from GitHub
    - Template verification
    - Configuration generation via DeploymentConfigurator

    This allows the deployment process to be used programmatically
    without depending on command-line arguments.
    """

    def __init__(
        self,
        output_dir: Path | str,
        templates_dir: Path | str | None = None,
        download_branch: str = "main",
        skip_download: bool = False,
        verbose: bool = False,
        printer: Printer | None = None,
        input_gatherer: InputGatherer | None = None,
    ):
        """
        Initialize the deployment runner.

        Args:
            output_dir: Directory where configuration files will be generated
            templates_dir: Optional custom templates directory.
                         If None, uses output_dir/.avatar-templates
            download_branch: Git branch to download templates from
            skip_download: Skip template download (use existing cached templates)
            verbose: Enable verbose output
            printer: Optional printer for output (defaults to ConsolePrinter)
        """
        self.output_dir = Path(output_dir)
        self.download_branch = download_branch
        self.skip_download = skip_download
        self.verbose = verbose

        # Use Rich implementations if in interactive terminal, otherwise Console
        if printer is None:
            # Only use Rich if stdout is a TTY (interactive terminal)
            if sys.stdout.isatty():
                try:
                    self.printer: Printer = RichPrinter()
                except ImportError:
                    self.printer = ConsolePrinter()
            else:
                self.printer = ConsolePrinter()
        else:
            self.printer = printer

        if input_gatherer is None:
            # Only use Rich if stdin is a TTY (interactive terminal)
            if sys.stdin.isatty():
                try:
                    self.input_gatherer: InputGatherer = RichInputGatherer()
                except ImportError:
                    self.input_gatherer = ConsoleInputGatherer()
            else:
                self.input_gatherer = ConsoleInputGatherer()
        else:
            self.input_gatherer = input_gatherer

        # Determine templates directory
        if templates_dir:
            self.templates_dir = Path(templates_dir)
        else:
            self.templates_dir = self.output_dir / ".avatar-templates"

    def ensure_templates(self) -> bool:
        """
        Ensure templates are available by downloading or verifying cache.

        Returns:
            True if templates are available, False otherwise
        """
        if self.skip_download:
            if self.verbose:
                self.printer.print(
                    f"Skipping download, using cached templates from "
                    f"{self.templates_dir}"
                )
            return self._verify_templates()

        # Download templates from GitHub
        if self.verbose:
            self.printer.print("Downloading deployment templates from GitHub...")

        success = download_templates(
            output_dir=self.templates_dir,
            force=False,  # Use cached if available
            branch=self.download_branch,
            verbose=self.verbose,
        )

        if not success:
            self.printer.print_warning("Failed to download some templates")

        return self._verify_templates()

    def _verify_templates(self) -> bool:
        """
        Verify that required templates exist.

        Returns:
            True if templates are available, False otherwise
        """
        if not self.templates_dir.exists():
            if self.verbose:
                self.printer.print_error(
                    f"Templates directory not found: {self.templates_dir}"
                )
            return False

        template_files = list(self.templates_dir.glob("*.template"))
        if not template_files:
            if self.verbose:
                self.printer.print_error(
                    f"No template files found in {self.templates_dir}"
                )
            return False

        if self.verbose:
            self.printer.print_success(f"Found {len(template_files)} template files")

        return True

    def run(
        self,
        interactive: bool = True,
        config_file: Path | None = None,
        save_config: bool = False,
    ) -> None:
        """
        Run the complete deployment configuration process.

        Args:
            interactive: Whether to prompt for values interactively
            config_file: Optional YAML config file to load
            save_config: Whether to save configuration to file

        Raises:
            RuntimeError: If templates are not available
            KeyboardInterrupt: If user cancels the process
            Exception: For other errors during configuration
        """
        # Ensure templates are available
        if not self.ensure_templates():
            raise RuntimeError(
                f"Templates not available. Try running without --skip-download "
                f"to download from GitHub (branch: {self.download_branch})"
            )

        # Create and run configurator
        configurator = DeploymentConfigurator(
            templates_dir=self.templates_dir,
            output_dir=self.output_dir,
            printer=self.printer,
            input_gatherer=self.input_gatherer,
        )

        configurator.run(
            interactive=interactive,
            config_file=config_file,
            save_config=save_config,
        )


def main():
    """CLI entry point for Avatar deployment configuration."""
    parser = argparse.ArgumentParser(
        description="Avatar Deployment Configuration Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path.cwd(),
        help="Output directory for generated files (default: current directory)",
    )

    parser.add_argument(
        "--templates-dir",
        type=Path,
        help="Templates directory (default: output-dir/.avatar-templates)",
    )

    parser.add_argument(
        "--config",
        type=Path,
        help="YAML configuration file to load",
    )

    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Run in non-interactive mode (use defaults or config file)",
    )

    parser.add_argument(
        "--save-config",
        action="store_true",
        help="Save configuration to deployment-config.yaml",
    )

    parser.add_argument(
        "--download-branch",
        type=str,
        default="main",
        help="Git branch to download templates from (default: main)",
    )

    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Skip downloading templates (use cached versions)",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Verbose output",
    )

    args = parser.parse_args()

    # Check if we're in test mode
    test_printer = None
    test_input_gatherer = None
    if os.environ.get("AVATAR_DEPLOY_TEST_MODE") == "1":
        from octopize_avatar_deploy.cli_test_harness import (
            get_test_input_gatherer,
            get_test_printer,
        )

        test_printer = get_test_printer()
        test_input_gatherer = get_test_input_gatherer()

    # Create deployment runner
    runner = DeploymentRunner(
        output_dir=args.output_dir,
        templates_dir=args.templates_dir,
        download_branch=args.download_branch,
        skip_download=args.skip_download,
        verbose=args.verbose,
        printer=test_printer,
        input_gatherer=test_input_gatherer,
    )

    try:
        runner.run(
            interactive=not args.non_interactive,
            config_file=args.config,
            save_config=args.save_config,
        )
    except KeyboardInterrupt:
        print("\n\nConfiguration cancelled by user.")
        sys.exit(1)
    except RuntimeError as e:
        print(f"\n✗ Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
