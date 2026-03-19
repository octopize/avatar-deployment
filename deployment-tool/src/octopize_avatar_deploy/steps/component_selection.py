"""Component selection step for dev mode."""

from __future__ import annotations

from typing import Any

from octopize_avatar_deploy.deployment_mode import DeploymentMode

from .base import DeploymentStep, TemplateRenderer


class ComponentSelectionStep(DeploymentStep):
    """Collect which components should get standalone dev-mode env files."""

    name = "component_selection"
    description = "Select components to run outside Docker"
    modes = [DeploymentMode.DEV]

    COMPONENT_LABELS = {
        "api": "API server",
        "web": "Web server",
    }

    def collect_config(self) -> dict[str, Any]:
        """Collect the selected components without rendering files."""
        selected = self._normalize_selected_components(self.config.get("DEV_COMPONENTS", []))

        if self.interactive:
            self.printer.print("\n--- Component .env Generation ---")
            self.printer.print(
                "Generate .env files for components you want to run outside Docker.\n"
                "This is useful for hot-reload development of specific services."
            )

            selected = []
            for name, label in self.COMPONENT_LABELS.items():
                if self.prompt_yes_no(
                    f"Generate .env for {label} ({name})?",
                    default=False,
                    key=f"component_selection.{name}",
                ):
                    selected.append(name)

        if not selected:
            self.printer.print("No components selected for external .env generation.")
            return {}

        return {"DEV_COMPONENTS": selected}

    def after_config_generation(self, render_template: TemplateRenderer) -> None:
        """Render the selected component env files after config collection is complete."""
        from octopize_avatar_deploy.components import get_component

        selected = self._normalize_selected_components(self.config.get("DEV_COMPONENTS", []))
        for component_name in selected:
            component = get_component(component_name)
            for output_spec in component.output_specs:
                render_template(output_spec.template_name, output_spec.output_path)

    def generate_secrets(self) -> dict[str, str]:
        """No secrets needed for component selection."""
        return {}

    def _normalize_selected_components(self, value: Any) -> list[str]:
        """Normalize and validate the selected components."""
        from octopize_avatar_deploy.components import get_component

        if isinstance(value, str):
            normalized = value.replace(",", " ").split()
        elif isinstance(value, list):
            normalized = [str(item).strip() for item in value]
        else:
            normalized = []

        selected: list[str] = []
        for name in normalized:
            if not name:
                continue
            get_component(name)
            selected.append(name)

        return selected
