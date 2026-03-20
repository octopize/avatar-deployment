"""Tests for component registry."""

import pytest

from octopize_avatar_deploy.components import (
    COMPONENT_REGISTRY,
    get_all_components,
    get_component,
)
from octopize_avatar_deploy.output_spec import OutputSpec


class TestComponentRegistry:
    def test_api_component_exists(self):
        spec = get_component("api")
        assert spec.name == "api"
        assert len(spec.step_classes) > 0
        assert len(spec.output_specs) == 1
        assert spec.output_specs[0] == OutputSpec("api.env.template", "api/.env")

    def test_web_component_exists(self):
        spec = get_component("web")
        assert spec.name == "web"
        assert len(spec.step_classes) > 0
        assert len(spec.output_specs) == 1
        assert spec.output_specs[0] == OutputSpec("web.env.template", "web/.env")

    def test_python_client_component_exists(self):
        spec = get_component("python_client")
        assert spec.name == "python_client"
        assert len(spec.step_classes) > 0
        assert len(spec.output_specs) == 1
        assert spec.output_specs[0] == OutputSpec(
            "python_client.env.template", "python_client/.env"
        )

    def test_unknown_component_raises(self):
        with pytest.raises(ValueError, match="Unknown component"):
            get_component("nonexistent")

    def test_get_all_components(self):
        components = get_all_components()
        assert "api" in components
        assert "web" in components
        assert "python_client" in components
        assert len(components) == 3

    def test_api_has_more_steps_than_web(self):
        """API component needs more config steps than web."""
        api = get_component("api")
        web = get_component("web")
        assert len(api.step_classes) > len(web.step_classes)

    def test_all_step_classes_are_valid(self):
        """All registered step classes should be DeploymentStep subclasses."""
        from octopize_avatar_deploy.steps.base import DeploymentStep

        for name, spec in COMPONENT_REGISTRY.items():
            for step_cls in spec.step_classes:
                assert issubclass(step_cls, DeploymentStep), (
                    f"Component '{name}' has invalid step class: {step_cls}"
                )
