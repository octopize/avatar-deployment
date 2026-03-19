"""Generate per-component .env files for local development."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml

from octopize_avatar_deploy.components import get_component
from octopize_avatar_deploy.configure import DeploymentConfigurator
from octopize_avatar_deploy.input_gatherer import (
    ConsoleInputGatherer,
    InputGatherer,
    RichInputGatherer,
)
from octopize_avatar_deploy.output_spec import OutputSpec
from octopize_avatar_deploy.printer import ConsolePrinter, Printer, RichPrinter
from octopize_avatar_deploy.steps.base import DeploymentStep
from octopize_avatar_deploy.template_provisioning import TemplateProvisioner


class GenerateEnvRunner:
    """Orchestrate per-component env file generation."""

    def __init__(
        self,
        output_dir: Path,
        components: list[str],
        template_from: str | Path = "github",
        verbose: bool = False,
        printer: Printer | None = None,
        input_gatherer: InputGatherer | None = None,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.components = components
        self.template_from = template_from
        self.verbose = verbose

        if printer is None:
            if sys.stdout.isatty():
                self.printer: Printer = RichPrinter()
            else:
                self.printer = ConsolePrinter()
        else:
            self.printer = printer

        if input_gatherer is None:
            if sys.stdin.isatty():
                self.input_gatherer: InputGatherer = RichInputGatherer()
            else:
                self.input_gatherer = ConsoleInputGatherer()
        else:
            self.input_gatherer = input_gatherer

        for name in components:
            get_component(name)

    def _collect_step_classes(self) -> list[type[DeploymentStep]]:
        """Collect unique step classes from all selected components, preserving order."""
        seen: set[type[DeploymentStep]] = set()
        steps: list[type[DeploymentStep]] = []
        for name in self.components:
            spec = get_component(name)
            for step_cls in spec.step_classes:
                if step_cls not in seen:
                    seen.add(step_cls)
                    steps.append(step_cls)
        return steps

    def _collect_output_specs(self) -> list[OutputSpec]:
        """Collect output specs from all selected components."""
        specs: list[OutputSpec] = []
        for name in self.components:
            specs.extend(get_component(name).output_specs)
        return specs

    def _load_config(self, config_file: Path | None) -> dict[str, Any]:
        """Load and validate the generate-env config file once."""
        if config_file is None:
            return {}

        if not config_file.exists():
            raise FileNotFoundError(f"Config file not found: {config_file}")

        try:
            with open(config_file) as f:
                config_data = yaml.safe_load(f)
        except yaml.YAMLError:
            raise
        except Exception as e:  # pragma: no cover - mirrors deployment runner behavior
            raise RuntimeError(f"Failed to load config file: {e}") from e

        if config_data is None:
            raise ValueError(f"Config file is empty: {config_file}")
        if not isinstance(config_data, dict):
            raise ValueError(
                f"Config file must contain a YAML dictionary, got {type(config_data).__name__}"
            )

        config = dict(config_data)
        environments = config.pop("environments", None)
        if environments is not None:
            config["_environments_config"] = environments

        return config

    def run(
        self,
        interactive: bool = True,
        config_file: Path | None = None,
        target: str | None = None,
        api_url: str | None = None,
        storage_url: str | None = None,
        sso_url: str | None = None,
    ) -> None:
        """Run the generate-env process."""
        config = self._load_config(config_file)
        config["_generate_env_mode"] = True

        if target:
            config["_target_environment"] = target

        if api_url:
            config["AVATAR_API_URL"] = api_url
        if storage_url:
            config["AVATAR_STORAGE_ENDPOINT_PUBLIC_URL"] = storage_url
        if sso_url:
            config["SSO_PROVIDER_URL"] = sso_url

        provisioner = TemplateProvisioner(
            output_dir=self.output_dir,
            template_from=self.template_from,
            verbose=self.verbose,
            printer=self.printer,
        )
        if not provisioner.ensure_templates():
            raise RuntimeError(
                "Templates not available. Use --template-from to specify template source."
            )

        configurator = DeploymentConfigurator(
            templates_dir=provisioner.templates_dir,
            output_dir=self.output_dir,
            config=config,
            use_state=False,
            printer=self.printer,
            input_gatherer=self.input_gatherer,
            step_classes=self._collect_step_classes(),
            output_specs=self._collect_output_specs(),
            include_deployment_assets=False,
            strict_templates=True,
        )
        configurator.run(
            interactive=interactive,
            config_file=None,
            save_config=False,
        )
