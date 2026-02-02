#!/usr/bin/env python3
"""
State Manager for Avatar Deployment Configuration

Manages deployment configuration state to support resuming interrupted configurations.
"""

from pathlib import Path
from typing import Any

import yaml


class DeploymentState:
    """Manages the state of a deployment configuration."""

    def __init__(self, state_file: Path, steps: list[str]):
        """
        Initialize the state manager.

        Args:
            state_file: Path to the state file
            steps: List of step names to track. If None, uses DEFAULT_STEPS
        """
        self.state_file = state_file
        self.steps = steps
        self.state = self._load_state()

    def _load_state(self) -> dict[str, Any]:
        """Load state from file or create new state."""
        if self.state_file.exists():
            with open(self.state_file) as f:
                return yaml.safe_load(f) or self._create_initial_state()
        return self._create_initial_state()

    def _create_initial_state(self) -> dict[str, Any]:
        """Create initial state structure."""
        return {
            "version": "1.0",
            "steps": dict.fromkeys(self.steps, "not-started"),
            "config": {},
            "step_data": {},  # Store step-specific data
            "user_secrets_provided": {},  # Track which user secrets were provided
        }

    def save(self) -> None:
        """Save current state to file."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, "w") as f:
            yaml.dump(self.state, f, default_flow_style=False, sort_keys=False)

    def get_step_status(self, step: str) -> str:
        """Get the status of a step."""
        return self.state["steps"].get(step, "not-started")

    def mark_step_started(self, step: str) -> None:
        """Mark a step as in-progress."""
        self.state["steps"][step] = "in-progress"
        self.save()

    def mark_step_completed(self, step: str) -> None:
        """Mark a step as completed."""
        self.state["steps"][step] = "completed"
        self.save()

    def is_step_completed(self, step: str) -> bool:
        """Check if a step is completed."""
        return self.get_step_status(step) == "completed"

    def get_next_step(self) -> str | None:
        """Get the next step that needs to be executed."""
        for step in self.steps:
            if not self.is_step_completed(step):
                return step
        return None

    def update_config(self, config: dict[str, Any]) -> None:
        """Update configuration in state."""
        self.state["config"].update(config)
        self.save()

    def get_config(self) -> dict[str, Any]:
        """Get current configuration from state."""
        return self.state["config"].copy()

    def mark_user_secret_provided(self, secret_name: str, provided: bool = True) -> None:
        """Mark whether a user secret was provided."""
        self.state["user_secrets_provided"][secret_name] = provided
        self.save()

    def is_user_secret_provided(self, secret_name: str) -> bool:
        """Check if a user secret was provided."""
        return self.state["user_secrets_provided"].get(secret_name, False)

    def reset(self) -> None:
        """Reset state to initial values."""
        self.state = self._create_initial_state()
        self.save()

    def delete(self) -> None:
        """Delete the state file."""
        if self.state_file.exists():
            self.state_file.unlink()

    def has_started(self) -> bool:
        """Check if any configuration has been started."""
        return any(status != "not-started" for status in self.state["steps"].values())

    def is_complete(self) -> bool:
        """Check if all steps are completed."""
        return all(status == "completed" for status in self.state["steps"].values())

    def get_progress_summary(self) -> str:
        """Get a human-readable progress summary."""
        completed = sum(1 for s in self.state["steps"].values() if s == "completed")
        total = len(self.steps)
        return f"{completed}/{total} steps completed"

    def print_status(self, printer=None) -> None:
        """
        Print current status.

        Args:
            printer: Optional printer to use for output. If None, uses built-in print().
        """
        _print = printer.print if printer else print

        _print("\n" + "=" * 60)
        _print("Deployment Configuration Status")
        _print("=" * 60)
        _print(f"\n{self.get_progress_summary()}\n")

        for step in self.steps:
            status = self.get_step_status(step)
            icon = "✓" if status == "completed" else "○" if status == "not-started" else "◐"
            _print(f"  {icon} {step.replace('_', ' ').title()}: {status}")

        if self.is_complete():
            _print("\n✓ Configuration is complete!")
        elif self.has_started():
            next_step = self.get_next_step()
            if next_step:
                _print(f"\n→ Next step: {next_step.replace('_', ' ').title()}")
