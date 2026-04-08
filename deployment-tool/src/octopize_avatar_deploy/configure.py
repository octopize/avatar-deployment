#!/usr/bin/env python3
"""
Avatar Deployment Configuration Tool

This script coordinates the deployment configuration process by:
1. Loading configuration from files or user input
2. Executing deployment steps in sequence
3. Generating configuration files from templates
4. Managing deployment state for resumption

Usage:
    # Interactive Docker deployment configuration
    octopize-deploy-tool deploy --output-dir /app/avatar

    # Non-interactive deployment configuration
    octopize-deploy-tool deploy --config config.yaml --non-interactive

    # Generate local component env files in component-specific paths
    octopize-deploy-tool generate-env --api-output-path ./api/.env --web-output-path ./web/.env
"""

import argparse
import os
import shutil
import sys
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined

from octopize_avatar_deploy.deployment_mode import DeploymentMode
from octopize_avatar_deploy.download_templates import (
    GitHubTemplateProvider,
    LocalTemplateProvider,
    TemplateProvider,
    verify_required_files,
)
from octopize_avatar_deploy.input_gatherer import (
    ConsoleInputGatherer,
    InputGatherer,
    RichInputGatherer,
)
from octopize_avatar_deploy.output_spec import OutputSpec
from octopize_avatar_deploy.printer import ConsolePrinter, Printer, RichPrinter
from octopize_avatar_deploy.state_manager import DeploymentState
from octopize_avatar_deploy.steps import (
    ApiLocalSourceStep,
    AuthentikBlueprintStep,
    AuthentikStep,
    ComponentSelectionStep,
    DatabaseStep,
    DeploymentStep,
    EmailStep,
    LoggingStep,
    NginxTlsStep,
    RequiredConfigStep,
    StorageStep,
    TelemetryStep,
    UserStep,
    WebLocalSourceStep,
)
from octopize_avatar_deploy.version_compat import (
    SCRIPT_VERSION,
    VersionError,
    validate_template_version,
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

    # Default step classes (can be overridden in tests)
    DEFAULT_STEP_CLASSES: list[type[DeploymentStep]] = [
        RequiredConfigStep,
        NginxTlsStep,
        DatabaseStep,
        AuthentikStep,
        AuthentikBlueprintStep,
        StorageStep,
        EmailStep,
        UserStep,
        WebLocalSourceStep,  # Dev mode only - prompts for Web local source paths
        ApiLocalSourceStep,  # Dev mode only - prompts for API local source paths
        TelemetryStep,
        LoggingStep,
        ComponentSelectionStep,  # Dev mode only - generates per-component .env files
    ]

    DEFAULT_OUTPUT_SPECS: list[OutputSpec] = [
        OutputSpec(".env.template", ".env"),
        OutputSpec("nginx.conf.template", "nginx/nginx.conf"),
        OutputSpec("docker-compose.yml.template", "docker-compose.yml"),
    ]

    def __init__(
        self,
        templates_dir: Path,
        output_dir: Path,
        defaults_file: Path | None = None,
        config: dict[str, Any] | None = None,
        use_state: bool = True,
        printer: Printer | None = None,
        input_gatherer: InputGatherer | None = None,
        step_classes: list[type[DeploymentStep]] | None = None,
        mode: DeploymentMode = DeploymentMode.PRODUCTION,
        output_specs: list[OutputSpec] | None = None,
        include_deployment_assets: bool = True,
        strict_templates: bool = False,
    ) -> None:
        """
        Initialize the configurator.

        Args:
            templates_dir: Path to templates directory
            output_dir: Path where configuration files will be generated
            defaults_file: Path to defaults.yaml file
            config: Optional pre-loaded configuration dict
            use_state: Whether to use state management for resuming
            printer: Optional printer for output (defaults to ConsolePrinter)
            input_gatherer: Optional input gatherer (defaults to ConsoleInputGatherer)
            step_classes: Optional list of step classes to use (defaults to DEFAULT_STEP_CLASSES)
            mode: Deployment mode (DeploymentMode.PRODUCTION or DeploymentMode.DEV)
            output_specs: Optional list of OutputSpec for template rendering
                (defaults to DEFAULT_OUTPUT_SPECS)
            include_deployment_assets: Whether to generate deployment-specific
                supporting files such as the blueprint, branding assets, and
                compose override.
            strict_templates: Whether the primary configured outputs should fail
                fast on missing template variables.
        """
        self.templates_dir = Path(templates_dir)
        self.output_dir = Path(output_dir)
        self.config = config or {}
        self.use_state = use_state
        self.mode = mode
        self.output_specs = output_specs or self.DEFAULT_OUTPUT_SPECS
        self.include_deployment_assets = include_deployment_assets
        self.strict_templates = strict_templates

        # Add deployment mode to config early so steps can access it
        self.config["deployment_mode"] = str(mode)

        # Filter step classes based on deployment mode
        all_step_classes = step_classes or self.DEFAULT_STEP_CLASSES
        self.step_classes = [cls for cls in all_step_classes if mode in cls.modes]

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
            # Derive step names from step classes
            step_names = [
                f"step_{i}_{step_class.name}" for i, step_class in enumerate(self.step_classes)
            ]
            self.state = DeploymentState(state_file, steps=step_names)
        else:
            self.state = None

        # Load defaults
        self.defaults = self._load_defaults(defaults_file)

        # Initialize Jinja2 environment
        env_kwargs = {
            "loader": FileSystemLoader(self.templates_dir),
            "variable_start_string": "{{",
            "variable_end_string": "}}",
            "trim_blocks": True,
            "lstrip_blocks": True,
        }
        self.env = Environment(
            **env_kwargs,
        )
        self.strict_env = Environment(
            loader=FileSystemLoader(self.templates_dir),
            variable_start_string="{{",
            variable_end_string="}}",
            trim_blocks=True,
            lstrip_blocks=True,
            undefined=StrictUndefined,
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

    def render_template(self, template_name: str, output_name: str, strict: bool = False) -> None:
        """
        Render a template file with configuration values.

        Args:
            template_name: Name of the template file
            output_name: Name of the output file
        """
        try:
            env = self.strict_env if strict else self.env
            template = env.get_template(template_name)
            rendered = template.render(**self.config)

            output_path = self.output_dir / output_name
            output_path.parent.mkdir(parents=True, exist_ok=True)
            content = rendered if rendered.endswith("\n") else rendered + "\n"
            output_path.write_text(content)

            self.printer.print_success(f"Generated: {output_path}")
        except Exception as e:
            self.printer.print_error(f"Error rendering {template_name}: {e}")
            raise

    def generate_configs(self) -> None:
        """Generate all configuration files from templates."""

        self.printer.print_header("Generating Configuration Files")

        # Render templates from output_specs
        for spec in self.output_specs:
            output_path = Path(spec.output_path)
            if output_path.parent != Path("."):
                (self.output_dir / output_path.parent).mkdir(parents=True, exist_ok=True)
            self.render_template(
                spec.template_name,
                spec.output_path,
                strict=self.strict_templates,
            )

        if self.include_deployment_assets:
            # Generate Authentik blueprint (copy as-is; uses !Env tags resolved at runtime)
            authentik_dir = self.output_dir / "authentik"
            authentik_dir.mkdir(parents=True, exist_ok=True)
            blueprint_src = self.templates_dir / "authentik" / "octopize-avatar-blueprint.yaml"
            blueprint_dst = authentik_dir / "octopize-avatar-blueprint.yaml"
            shutil.copy2(blueprint_src, blueprint_dst)
            self.printer.print_success(f"Copied: {blueprint_dst}")

            # Copy translations.json for i18n prompt expressions
            translations_src = self.templates_dir / "authentik" / "translations.json"
            translations_dst = authentik_dir / "translations.json"
            if translations_src.exists():
                shutil.copy2(translations_src, translations_dst)
                self.printer.print_success(f"Copied: {translations_dst}")

            # Generate compose.override.yaml for dev mode
            if self.mode == DeploymentMode.DEV:
                override_template = self.templates_dir / "compose.override.yaml.template"
                if override_template.exists():
                    self.render_template("compose.override.yaml.template", "compose.override.yaml")
                else:
                    self.printer.print_warning(
                        "Dev mode enabled but compose.override.yaml.template not found. "
                        "Skipping override file generation."
                    )

            # Copy authentik custom templates (email templates)
            custom_templates_src = self.templates_dir / "authentik" / "custom-templates"
            custom_templates_dst = self.output_dir / "authentik" / "custom-templates"
            if custom_templates_src.exists():
                custom_templates_dst.mkdir(parents=True, exist_ok=True)
                for template_file in custom_templates_src.glob("*.html"):
                    shutil.copy2(template_file, custom_templates_dst / template_file.name)
                self.printer.print_success(f"Copied: email templates to {custom_templates_dst}")

            # Copy authentik branding files
            branding_src = self.templates_dir / "authentik" / "branding"
            branding_dst = self.output_dir / "authentik" / "branding"
            if branding_src.exists():
                branding_dst.mkdir(parents=True, exist_ok=True)
                for branding_file in branding_src.glob("*"):
                    if branding_file.is_file():
                        shutil.copy2(branding_file, branding_dst / branding_file.name)
                self.printer.print_success(f"Copied: branding files to {branding_dst}")

            # Copy authentik custom CSS
            css_src = self.templates_dir / "authentik" / "css"
            css_dst = self.output_dir / "authentik" / "css"
            if css_src.exists():
                css_dst.mkdir(parents=True, exist_ok=True)
                for css_file in css_src.glob("*"):
                    if css_file.is_file():
                        shutil.copy2(css_file, css_dst / css_file.name)
                self.printer.print_success(f"Copied: custom CSS to {css_dst}")

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
                self.state.print_status(self.printer)
                self.printer.print_header("")
                response = self.input_gatherer.prompt_yes_no(
                    "Resume from where you left off?", default=True, key="resume.continue"
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
            try:
                with open(config_file) as f:
                    loaded_config = yaml.safe_load(f) or {}
                self.config.update(loaded_config)
            except yaml.YAMLError as e:
                raise RuntimeError(f"Failed to parse YAML config file: {e}") from e
            except Exception as e:
                raise RuntimeError(f"Failed to load config file: {e}") from e

        # Instantiate deployment steps
        steps = [
            step_class(
                self.output_dir,
                self.defaults,
                self.config,
                interactive,
                self.printer,
                self.input_gatherer,
            )
            for step_class in self.step_classes
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

        for step in steps:
            step.after_config_generation(
                lambda template_name, output_name: self.render_template(
                    template_name,
                    output_name,
                    strict=True,
                )
            )

        self.printer.print()
        self.printer.print_success("Configuration files generated successfully!")

        # Write all secrets
        if all_secrets:
            self.printer.print()
            self.printer.print(f"Writing {len(all_secrets)} secrets to .secrets/ directory...")
            self.write_secrets(all_secrets)
            self.printer.print_success("Secrets written successfully")

        # Save config if requested
        if save_config:
            config_output = self.output_dir / "deployment-config.yaml"
            self.save_config_to_file(config_output)

        if self.config.get("_generate_env_mode", False):
            self.printer.print_header("Generate-env Complete!")
            return

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
        template_from: str | Path = "github",
        verbose: bool = False,
        printer: Printer | None = None,
        input_gatherer: InputGatherer | None = None,
        mode: DeploymentMode = DeploymentMode.PRODUCTION,
    ) -> None:
        """
        Initialize the deployment runner.

        Args:
            output_dir: Directory where configuration files will be generated
            template_from: Either 'github' to download from the repo, or a path
                         to local templates directory
            verbose: Enable verbose output
            printer: Optional printer for output (defaults to ConsolePrinter)
            input_gatherer: Optional input gatherer for prompts
            mode: Deployment mode (DeploymentMode.PRODUCTION or DeploymentMode.DEV)
        """
        self.output_dir = Path(output_dir)
        self.template_from = template_from
        self.verbose = verbose
        self.mode = mode
        self.template_provider: TemplateProvider
        self.template_source: Path | None = None

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

        # Templates are always stored in output_dir/.avatar-templates
        self.templates_dir = self.output_dir / ".avatar-templates"

        self.template_provider = self._init_template_provider()

    def _init_template_provider(self) -> TemplateProvider:
        if self.template_from == "github":
            return GitHubTemplateProvider(branch="main", verbose=self.verbose)

        self.template_source = Path(self.template_from)
        return LocalTemplateProvider(source_dir=str(self.template_source), verbose=self.verbose)

    def ensure_templates(self) -> bool:
        """
        Ensure templates are available by downloading from GitHub or copying from local path.

        Returns:
            True if templates are available, False otherwise
        """
        if self.template_source and not self.template_source.exists():
            self.printer.print_error(f"Template source directory not found: {self.template_source}")
            return False

        if self.template_from == "github":
            if self.template_provider.check_cached_templates(self.templates_dir):
                if self.verbose:
                    self.printer.print(f"Templates already cached in {self.templates_dir}/")
                return self._verify_templates()

            if self.verbose:
                self.printer.print("Downloading deployment templates from GitHub...")
        else:
            if self.template_source and self.verbose:
                self.printer.print(f"Copying templates from {self.template_source}")

        success = self.template_provider.provide_all(self.templates_dir)
        if not success:
            if self.template_from == "github":
                self.printer.print_error("Failed to download templates from GitHub")
            else:
                self.printer.print_warning("Failed to copy some templates")
            return False

        return self._verify_templates()

    def _verify_templates(self) -> bool:
        """
        Verify that required templates exist.

        Returns:
            True if templates are available, False otherwise
        """
        if not self.templates_dir.exists():
            if self.verbose:
                self.printer.print_error(f"Templates directory not found: {self.templates_dir}")
            return False

        is_valid, error_message, total_files = verify_required_files(self.templates_dir)
        if not is_valid:
            if self.verbose and error_message:
                self.printer.print_error(error_message)
            return False

        if self.verbose:
            self.printer.print_success(f"Found all {total_files} required template files")

        # Validate template version compatibility
        return self._validate_template_version()

    def _validate_template_version(self) -> bool:
        """
        Validate that the template version is compatible with the script version.

        Returns:
            True if compatible, False otherwise
        """
        version_file = self.templates_dir / ".template-version"

        if not version_file.exists():
            if self.verbose:
                self.printer.print_warning(
                    "No .template-version file found, skipping version check"
                )
            return True

        try:
            validate_template_version(
                version_file=version_file,
                script_version=SCRIPT_VERSION,
                verbose=self.verbose,
            )
            if self.verbose:
                self.printer.print_success(
                    f"Template version is compatible with script version {SCRIPT_VERSION}"
                )
            return True
        except VersionError as e:
            self.printer.print_error(str(e))
            return False

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
            FileNotFoundError: If config file is specified but doesn't exist
            yaml.YAMLError: If config file has invalid YAML syntax
            ValueError: If config file has invalid values
            KeyboardInterrupt: If user cancels the process
            Exception: For other errors during configuration
        """
        # Validate config file if provided
        if config_file is not None:
            if not config_file.exists():
                self.printer.print_error(f"Config file not found: {config_file}")
                raise FileNotFoundError(f"Config file not found: {config_file}")

            # Try to load and validate the YAML
            try:
                with open(config_file) as f:
                    config_data = yaml.safe_load(f)

                if config_data is None:
                    self.printer.print_error(f"Config file is empty: {config_file}")
                    raise ValueError(f"Config file is empty: {config_file}")

                if not isinstance(config_data, dict):
                    self.printer.print_error(
                        f"Config file must contain a YAML dictionary, "
                        f"got {type(config_data).__name__}"
                    )
                    raise ValueError(
                        f"Config file must contain a YAML dictionary, "
                        f"got {type(config_data).__name__}"
                    )

            except yaml.YAMLError as e:
                self.printer.print_error(f"Invalid YAML syntax in config file: {config_file}")
                self.printer.print_error(str(e))
                raise

        # Ensure templates are available
        if not self.ensure_templates():
            raise RuntimeError(
                "Templates not available. Use --template-from github to download from the "
                "repository, or provide a valid local path."
            )

        # Create and run configurator
        configurator = DeploymentConfigurator(
            templates_dir=self.templates_dir,
            output_dir=self.output_dir,
            printer=self.printer,
            input_gatherer=self.input_gatherer,
            mode=self.mode,
        )

        configurator.run(
            interactive=interactive,
            config_file=config_file,
            save_config=save_config,
        )


def _add_shared_cli_args(parser: argparse.ArgumentParser) -> None:
    """Add CLI arguments shared across deploy and generate-env."""
    parser.add_argument(
        "--template-from",
        type=str,
        default="github",
        help="Template source: 'github' to download from repo, or path to local templates "
        "directory (default: github)",
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
        "--verbose",
        action="store_true",
        help="Verbose output",
    )


def _add_deploy_cli_args(parser: argparse.ArgumentParser) -> None:
    """Add CLI arguments for the deploy subcommand."""
    _add_shared_cli_args(parser)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path.cwd(),
        help="Output directory for generated files (default: current directory)",
    )
    parser.add_argument(
        "--save-config",
        action="store_true",
        help="Save configuration to deployment-config.yaml",
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["production", "dev"],
        default="production",
        help="Deployment mode: production (default) or dev",
    )


def _parse_component_output_path(value: str) -> tuple[str, Path]:
    """Parse a COMPONENT=PATH output override from the CLI."""
    from octopize_avatar_deploy.components import get_component

    component, separator, raw_path = value.partition("=")
    if not separator or not component or not raw_path:
        raise argparse.ArgumentTypeError("Output path overrides must use COMPONENT=PATH syntax")

    try:
        get_component(component)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc

    return component, Path(raw_path)


def _add_generate_env_cli_args(parser: argparse.ArgumentParser) -> None:
    """Add CLI arguments for the generate-env subcommand."""
    from octopize_avatar_deploy.components import get_all_components

    component_names = ", ".join(get_all_components().keys())

    _add_shared_cli_args(parser)
    parser.add_argument(
        "--component",
        action="append",
        dest="components",
        metavar="NAME",
        help=(
            f"Component to generate .env for (repeatable: {component_names}). "
            "If omitted, generates all registered components into their default paths."
        ),
    )
    parser.add_argument(
        "--api-output-path",
        type=Path,
        help="Write the API env file to this path instead of the default component path",
    )
    parser.add_argument(
        "--web-output-path",
        type=Path,
        help="Write the web env file to this path instead of the default component path",
    )
    parser.add_argument(
        "--python-client-output-path",
        type=Path,
        help=(
            "Write the python_client env file to this path instead of the default component path"
        ),
    )
    parser.add_argument(
        "--output-path",
        action="append",
        dest="output_paths",
        metavar="COMPONENT=PATH",
        type=_parse_component_output_path,
        help=(
            "Repeatable component output override in COMPONENT=PATH form. "
            "Use this for future components or to override convenience flags."
        ),
    )
    parser.add_argument(
        "--target",
        type=str,
        help="Named environment preset from config file (e.g., prod, staging, local)",
    )
    parser.add_argument(
        "--api-url",
        type=str,
        help="Override API URL",
    )
    parser.add_argument(
        "--storage-url",
        type=str,
        help="Override storage public URL",
    )
    parser.add_argument(
        "--sso-url",
        type=str,
        help="Override SSO provider URL",
    )


def _build_parser() -> argparse.ArgumentParser:
    """Build the top-level CLI parser."""
    parser = argparse.ArgumentParser(
        description="Avatar Deployment Configuration Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    deploy_parser = subparsers.add_parser(
        "deploy",
        help="Generate Docker deployment configuration",
    )
    _add_deploy_cli_args(deploy_parser)

    gen_parser = subparsers.add_parser(
        "generate-env",
        help="Generate per-component .env files using component output paths",
        description=(
            "Generate per-component .env files using each component's default output "
            "path, or override specific destinations with --*-output-path / "
            "--output-path COMPONENT=PATH."
        ),
    )
    _add_generate_env_cli_args(gen_parser)

    return parser


def main() -> None:
    """CLI entry point for Avatar deployment configuration."""
    parser = _build_parser()

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

    try:
        if args.command == "deploy":
            _run_deploy(args, test_printer, test_input_gatherer)
        elif args.command == "generate-env":
            _run_generate_env(args, test_printer, test_input_gatherer)
        else:
            raise RuntimeError(f"Unsupported command: {args.command}")
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


def _run_deploy(
    args: argparse.Namespace,
    printer: Printer | None,
    input_gatherer: InputGatherer | None,
) -> None:
    """Run the deploy subcommand."""
    mode = DeploymentMode(getattr(args, "mode", "production"))

    runner = DeploymentRunner(
        output_dir=args.output_dir,
        template_from=args.template_from,
        verbose=args.verbose,
        printer=printer,
        input_gatherer=input_gatherer,
        mode=mode,
    )

    runner.run(
        interactive=not args.non_interactive,
        config_file=args.config,
        save_config=getattr(args, "save_config", False),
    )


def _run_generate_env(
    args: argparse.Namespace,
    printer: Printer | None,
    input_gatherer: InputGatherer | None,
) -> None:
    """Run the generate-env subcommand."""
    from octopize_avatar_deploy.components import get_all_components
    from octopize_avatar_deploy.generate_env import GenerateEnvRunner

    components = args.components or list(get_all_components().keys())
    output_path_overrides = {
        component: path
        for component, path in (
            ("api", args.api_output_path),
            ("web", args.web_output_path),
            ("python_client", args.python_client_output_path),
        )
        if path is not None
    }
    output_path_overrides.update(dict(args.output_paths or []))

    runner = GenerateEnvRunner(
        output_dir=Path.cwd(),
        components=components,
        template_from=args.template_from,
        verbose=args.verbose,
        printer=printer,
        input_gatherer=input_gatherer,
    )

    runner.run(
        interactive=not args.non_interactive,
        config_file=args.config,
        target=args.target,
        api_url=args.api_url,
        storage_url=args.storage_url,
        sso_url=args.sso_url,
        output_path_overrides=output_path_overrides,
    )


if __name__ == "__main__":
    main()
