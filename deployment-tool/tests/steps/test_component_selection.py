"""Tests for ComponentSelectionStep."""

import pytest

from octopize_avatar_deploy.steps.component_selection import ComponentSelectionStep


class TestComponentSelectionStep:
    @pytest.fixture
    def defaults(self):
        return {}

    def test_non_interactive_no_components(self, tmp_path, defaults):
        """Non-interactive with no DEV_COMPONENTS does nothing."""
        step = ComponentSelectionStep(tmp_path, defaults, {}, interactive=False)
        assert step.collect_config() == {}

        rendered: list[tuple[str, str]] = []
        step.after_config_generation(lambda template, output: rendered.append((template, output)))
        assert rendered == []

    def test_non_interactive_with_components_list(self, tmp_path, defaults):
        """Non-interactive DEV_COMPONENTS list is collected without rendering."""
        config = {"DEV_COMPONENTS": ["web"]}
        step = ComponentSelectionStep(tmp_path, defaults, config, interactive=False)

        result = step.collect_config()

        assert result == {"DEV_COMPONENTS": ["web"]}

    def test_after_config_generation_renders_selected_components(self, tmp_path, defaults):
        """Selected components are rendered through the post-generation hook."""
        config = {"DEV_COMPONENTS": ["api", "web"]}
        step = ComponentSelectionStep(tmp_path, defaults, config, interactive=False)

        rendered: list[tuple[str, str]] = []
        step.after_config_generation(lambda template, output: rendered.append((template, output)))

        assert rendered == [
            ("api.env.template", "api/.env"),
            ("web.env.template", "web/.env"),
        ]

    def test_non_interactive_with_components_string(self, tmp_path, defaults):
        """DEV_COMPONENTS string supports comma and whitespace separators."""
        config = {"DEV_COMPONENTS": "api, web"}
        step = ComponentSelectionStep(tmp_path, defaults, config, interactive=False)

        result = step.collect_config()

        assert result["DEV_COMPONENTS"] == ["api", "web"]

    def test_unknown_component_raises(self, tmp_path, defaults):
        """Unknown configured components fail fast."""
        step = ComponentSelectionStep(
            tmp_path,
            defaults,
            {"DEV_COMPONENTS": ["worker"]},
            interactive=False,
        )

        with pytest.raises(ValueError, match="Unknown component"):
            step.collect_config()

    def test_generate_secrets_empty(self, tmp_path, defaults):
        step = ComponentSelectionStep(tmp_path, defaults, {}, interactive=False)
        assert step.generate_secrets() == {}

    def test_step_metadata(self, tmp_path, defaults):
        step = ComponentSelectionStep(tmp_path, defaults, {}, interactive=False)
        assert step.name == "component_selection"

        from octopize_avatar_deploy.deployment_mode import DeploymentMode

        assert DeploymentMode.DEV in step.modes
        assert DeploymentMode.PRODUCTION not in step.modes
