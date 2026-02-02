#!/usr/bin/env python3
"""Tests for deployment state manager."""

import pytest
import yaml

from octopize_avatar_deploy.state_manager import DeploymentState


class TestDeploymentState:
    """Test the DeploymentState class."""

    @pytest.fixture
    def temp_state_file(self, tmp_path):
        """Create a temporary state file path."""
        return tmp_path / ".deployment-state.yaml"

    @pytest.fixture
    def state(self, temp_state_file):
        """Create a DeploymentState instance."""
        # Use representative step names matching the pattern from configure.py
        steps = [
            "step_0_required_config",
            "step_1_database",
            "step_2_authentik",
            "step_3_storage",
            "step_4_email",
            "step_5_user",
            "step_6_telemetry",
            "step_7_logging",
        ]
        return DeploymentState(temp_state_file, steps=steps)

    @pytest.fixture
    def custom_steps_state(self, temp_state_file):
        """Create a DeploymentState instance with custom steps."""
        steps = ["step1", "step2", "step3"]
        return DeploymentState(temp_state_file, steps=steps)

    def test_init_creates_initial_state(self, state):
        """Test that initialization creates proper state structure."""
        assert "version" in state.state
        assert "steps" in state.state
        assert "config" in state.state
        assert "step_data" in state.state
        assert "user_secrets_provided" in state.state

    def test_init_requires_steps(self, temp_state_file):
        """Test that steps parameter is required."""
        # DeploymentState requires steps parameter
        with pytest.raises(TypeError):
            DeploymentState(temp_state_file)

    def test_init_uses_custom_steps(self, custom_steps_state):
        """Test that custom steps are used when provided."""
        assert custom_steps_state.steps == ["step1", "step2", "step3"]
        assert "step1" in custom_steps_state.state["steps"]
        assert "step2" in custom_steps_state.state["steps"]
        assert "step3" in custom_steps_state.state["steps"]

    def test_all_steps_start_not_started(self, state):
        """Test that all steps initially have 'not-started' status."""
        for step in state.steps:
            assert state.get_step_status(step) == "not-started"

    def test_save_creates_file(self, state, temp_state_file):
        """Test that save creates a state file."""
        state.save()
        assert temp_state_file.exists()

    def test_save_creates_parent_directory(self, tmp_path):
        """Test that save creates parent directory if needed."""
        nested_path = tmp_path / "nested" / "dir" / "state.yaml"
        state = DeploymentState(nested_path, steps=["step_0_test"])
        state.save()
        assert nested_path.exists()
        assert nested_path.parent.exists()

    def test_save_preserves_data(self, state, temp_state_file):
        """Test that save preserves state data."""
        state.state["config"]["test_key"] = "test_value"
        state.save()

        # Reload from file
        with open(temp_state_file) as f:
            saved_state = yaml.safe_load(f)

        assert saved_state["config"]["test_key"] == "test_value"

    def test_load_existing_state(self, temp_state_file):
        """Test loading an existing state file."""
        steps = ["step_0_test", "step_1_test"]
        # Create an initial state
        state1 = DeploymentState(temp_state_file, steps=steps)
        state1.state["config"]["loaded"] = True
        state1.save()

        # Load existing state
        state2 = DeploymentState(temp_state_file, steps=steps)
        assert state2.state["config"]["loaded"] is True

    def test_mark_step_started(self, state):
        """Test marking a step as started."""
        step_name = state.steps[0]
        state.mark_step_started(step_name)
        assert state.get_step_status(step_name) == "in-progress"

    def test_mark_step_completed(self, state):
        """Test marking a step as completed."""
        step_name = state.steps[0]
        state.mark_step_completed(step_name)
        assert state.get_step_status(step_name) == "completed"

    def test_is_step_completed(self, state):
        """Test checking if a step is completed."""
        step_name = state.steps[0]
        assert not state.is_step_completed(step_name)

        state.mark_step_completed(step_name)
        assert state.is_step_completed(step_name)

    def test_get_step_status_unknown_step(self, state):
        """Test getting status of unknown step returns 'not-started'."""
        assert state.get_step_status("nonexistent_step") == "not-started"

    def test_get_next_step(self, custom_steps_state):
        """Test getting the next step to execute."""
        # Initially, first step should be next
        assert custom_steps_state.get_next_step() == "step1"

        # Mark first step as completed
        custom_steps_state.mark_step_completed("step1")
        assert custom_steps_state.get_next_step() == "step2"

        # Mark second step as completed
        custom_steps_state.mark_step_completed("step2")
        assert custom_steps_state.get_next_step() == "step3"

    def test_get_next_step_all_completed(self, custom_steps_state):
        """Test that get_next_step returns None when all steps are complete."""
        for step in custom_steps_state.steps:
            custom_steps_state.mark_step_completed(step)

        assert custom_steps_state.get_next_step() is None

    def test_update_config(self, state):
        """Test updating configuration."""
        config_data = {"key1": "value1", "key2": "value2"}
        state.update_config(config_data)

        assert state.state["config"]["key1"] == "value1"
        assert state.state["config"]["key2"] == "value2"

    def test_update_config_merges(self, state):
        """Test that update_config merges with existing config."""
        state.update_config({"key1": "value1"})
        state.update_config({"key2": "value2"})

        assert state.state["config"]["key1"] == "value1"
        assert state.state["config"]["key2"] == "value2"

    def test_get_config(self, state):
        """Test getting configuration."""
        state.state["config"]["test"] = "value"
        config = state.get_config()

        assert config["test"] == "value"

    def test_get_config_returns_copy(self, state):
        """Test that get_config returns a copy, not reference."""
        state.state["config"]["test"] = "original"
        config = state.get_config()
        config["test"] = "modified"

        # Original should be unchanged
        assert state.state["config"]["test"] == "original"

    def test_mark_user_secret_provided(self, state):
        """Test marking a user secret as provided."""
        state.mark_user_secret_provided("secret1", True)
        assert state.state["user_secrets_provided"]["secret1"] is True

    def test_mark_user_secret_not_provided(self, state):
        """Test marking a user secret as not provided."""
        state.mark_user_secret_provided("secret1", False)
        assert state.state["user_secrets_provided"]["secret1"] is False

    def test_is_user_secret_provided(self, state):
        """Test checking if a user secret was provided."""
        assert not state.is_user_secret_provided("secret1")

        state.mark_user_secret_provided("secret1", True)
        assert state.is_user_secret_provided("secret1")

    def test_is_user_secret_provided_default_false(self, state):
        """Test that unknown secrets default to False."""
        assert not state.is_user_secret_provided("nonexistent_secret")

    def test_reset(self, state):
        """Test resetting state."""
        # Modify state
        state.mark_step_completed(state.steps[0])
        state.update_config({"key": "value"})
        state.mark_user_secret_provided("secret1", True)

        # Reset
        state.reset()

        # Verify everything is reset
        assert all(s == "not-started" for s in state.state["steps"].values())
        assert state.state["config"] == {}
        assert state.state["user_secrets_provided"] == {}

    def test_delete(self, state, temp_state_file):
        """Test deleting state file."""
        state.save()
        assert temp_state_file.exists()

        state.delete()
        assert not temp_state_file.exists()

    def test_delete_nonexistent_file(self, state, temp_state_file):
        """Test that deleting nonexistent file doesn't raise error."""
        assert not temp_state_file.exists()
        state.delete()  # Should not raise

    def test_has_started(self, state):
        """Test checking if configuration has started."""
        assert not state.has_started()

        state.mark_step_started(state.steps[0])
        assert state.has_started()

    def test_has_started_with_completed_step(self, state):
        """Test has_started returns True for completed steps."""
        state.mark_step_completed(state.steps[0])
        assert state.has_started()

    def test_is_complete(self, custom_steps_state):
        """Test checking if all steps are completed."""
        assert not custom_steps_state.is_complete()

        # Complete all but one
        for step in custom_steps_state.steps[:-1]:
            custom_steps_state.mark_step_completed(step)
        assert not custom_steps_state.is_complete()

        # Complete the last one
        custom_steps_state.mark_step_completed(custom_steps_state.steps[-1])
        assert custom_steps_state.is_complete()

    def test_get_progress_summary(self, custom_steps_state):
        """Test getting progress summary."""
        assert custom_steps_state.get_progress_summary() == "0/3 steps completed"

        custom_steps_state.mark_step_completed("step1")
        assert custom_steps_state.get_progress_summary() == "1/3 steps completed"

        custom_steps_state.mark_step_completed("step2")
        assert custom_steps_state.get_progress_summary() == "2/3 steps completed"

        custom_steps_state.mark_step_completed("step3")
        assert custom_steps_state.get_progress_summary() == "3/3 steps completed"

    def test_print_status(self, custom_steps_state, capsys):
        """Test printing status."""
        custom_steps_state.print_status()
        captured = capsys.readouterr()

        assert "Deployment Configuration Status" in captured.out
        assert "0/3 steps completed" in captured.out
        assert "Step1" in captured.out

    def test_print_status_with_progress(self, custom_steps_state, capsys):
        """Test printing status with some steps completed."""
        custom_steps_state.mark_step_completed("step1")
        custom_steps_state.mark_step_started("step2")
        custom_steps_state.print_status()

        captured = capsys.readouterr()
        assert "1/3 steps completed" in captured.out
        # Next step should be step2 since it's in-progress (not completed)
        assert "Next step: Step2" in captured.out

    def test_print_status_complete(self, custom_steps_state, capsys):
        """Test printing status when complete."""
        for step in custom_steps_state.steps:
            custom_steps_state.mark_step_completed(step)

        custom_steps_state.print_status()
        captured = capsys.readouterr()

        assert "Configuration is complete!" in captured.out
        assert "3/3 steps completed" in captured.out

    def test_state_persists_across_instances(self, temp_state_file):
        """Test that state persists when creating new instances."""
        # Create first instance and modify state
        state1 = DeploymentState(temp_state_file, steps=["a", "b", "c"])
        state1.mark_step_completed("a")
        state1.update_config({"test": "value"})
        state1.save()

        # Create second instance and verify state
        state2 = DeploymentState(temp_state_file, steps=["a", "b", "c"])
        assert state2.is_step_completed("a")
        assert state2.state["config"]["test"] == "value"

    def test_yaml_format(self, state, temp_state_file):
        """Test that saved YAML is properly formatted."""
        state.update_config({"test_key": "test_value"})
        state.save()

        with open(temp_state_file) as f:
            content = f.read()

        # Verify it's valid YAML
        data = yaml.safe_load(content)
        assert data is not None
        assert data["version"] == "1.0"

    def test_step_data_structure_exists(self, state):
        """Test that step_data structure exists for storing step-specific data."""
        assert "step_data" in state.state
        assert isinstance(state.state["step_data"], dict)

    def test_concurrent_modifications(self, temp_state_file):
        """Test handling of state when modified by different instances."""
        state1 = DeploymentState(temp_state_file, steps=["a", "b"])

        # Modify through first instance
        state1.mark_step_completed("a")

        # Second instance should load the updated state
        state2_fresh = DeploymentState(temp_state_file, steps=["a", "b"])
        assert state2_fresh.is_step_completed("a")
