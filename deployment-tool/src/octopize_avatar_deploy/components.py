"""Component registry for per-component .env generation."""

from __future__ import annotations

from dataclasses import dataclass

from octopize_avatar_deploy.output_spec import OutputSpec
from octopize_avatar_deploy.steps.authentik_blueprint import AuthentikBlueprintStep
from octopize_avatar_deploy.steps.base import DeploymentStep
from octopize_avatar_deploy.steps.database import DatabaseStep
from octopize_avatar_deploy.steps.email import EmailStep
from octopize_avatar_deploy.steps.logging import LoggingStep
from octopize_avatar_deploy.steps.required import RequiredConfigStep
from octopize_avatar_deploy.steps.target_environment import TargetEnvironmentStep
from octopize_avatar_deploy.steps.telemetry import TelemetryStep
from octopize_avatar_deploy.steps.user import UserStep


@dataclass
class ComponentEnvSpec:
    """Specification for a component's .env generation."""

    name: str
    description: str
    step_classes: list[type[DeploymentStep]]
    output_specs: list[OutputSpec]


def _build_registry() -> dict[str, ComponentEnvSpec]:
    """Build the component registry."""
    return {
        "api": ComponentEnvSpec(
            name="api",
            description="API server environment (DB, SSO, logging, email, telemetry, storage)",
            step_classes=[
                RequiredConfigStep,
                DatabaseStep,
                TargetEnvironmentStep,
                AuthentikBlueprintStep,
                EmailStep,
                LoggingStep,
                TelemetryStep,
                UserStep,
            ],
            output_specs=[OutputSpec("api.env.template", "api/.env")],
        ),
        "web": ComponentEnvSpec(
            name="web",
            description="Web server environment (API URL, storage URL, SSO URL)",
            step_classes=[
                RequiredConfigStep,
                TargetEnvironmentStep,
            ],
            output_specs=[OutputSpec("web.env.template", "web/.env")],
        ),
        "python_client": ComponentEnvSpec(
            name="python_client",
            description="Python client environment (API URL, storage URL)",
            step_classes=[
                RequiredConfigStep,
                TargetEnvironmentStep,
            ],
            output_specs=[OutputSpec("python_client.env.template", "python_client/.env")],
        ),
    }


COMPONENT_REGISTRY: dict[str, ComponentEnvSpec] = _build_registry()


def get_component(name: str) -> ComponentEnvSpec:
    """Get a component spec by name.

    Raises ValueError for unknown components.
    """
    if name not in COMPONENT_REGISTRY:
        available = ", ".join(COMPONENT_REGISTRY.keys())
        raise ValueError(f"Unknown component '{name}'. Available: {available}")
    return COMPONENT_REGISTRY[name]


def get_all_components() -> dict[str, ComponentEnvSpec]:
    """Get all registered components."""
    return COMPONENT_REGISTRY
