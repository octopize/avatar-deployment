"""Tests for live_verifier module."""

from unittest.mock import MagicMock, patch

import pytest

from authentik_blueprint.live_verifier import (
    _filter_output,
    _find_docker_worker,
    _STEPPER_TEMPLATE,
    run,
    run_docker,
    run_kubernetes,
)


# ---------------------------------------------------------------------------
# _filter_output
# ---------------------------------------------------------------------------

class TestFilterOutput:
    def test_removes_json_log_lines(self):
        raw = '{"event": "Loaded config", "level": "debug"}\n  OK  [ 0] some.model | some-id'
        result = _filter_output(raw)
        assert '{"event"' not in result
        assert "OK" in result

    def test_removes_noise_prefixes(self):
        raw = "\n".join([
            "Imported related module",
            "Loaded app settings",
            "Starting authentik bootstrap",
            "Booting authentik",
            "Enabled enterprise",
            "MMDB database",
            "Defaulted container worker",
            "  OK  [  0] some.model | id",
            "  FAIL  [  1] other.model | id2",
        ])
        result = _filter_output(raw)
        assert "Imported" not in result
        assert "Loaded" not in result
        assert "OK" in result
        assert "FAIL" in result

    def test_empty_lines_removed(self):
        raw = "\n\n  OK  [0] x | y\n\n"
        result = _filter_output(raw)
        assert "  " not in result.split("\n")[0] or result.strip().startswith("OK")


# ---------------------------------------------------------------------------
# _STEPPER_TEMPLATE substitution
# ---------------------------------------------------------------------------

class TestStepperTemplate:
    def test_placeholder_replaced(self):
        code = _STEPPER_TEMPLATE.replace(
            "BLUEPRINT_NAME_PLACEHOLDER", "my-blueprint"
        )
        assert "BLUEPRINT_NAME_PLACEHOLDER" not in code
        assert "'my-blueprint'" in code

    def test_template_is_valid_python(self):
        import ast
        code = _STEPPER_TEMPLATE.replace("BLUEPRINT_NAME_PLACEHOLDER", "test")
        # Should parse without SyntaxError
        ast.parse(code)


# ---------------------------------------------------------------------------
# run_docker
# ---------------------------------------------------------------------------

class TestRunDocker:
    def test_auto_detects_container(self):
        with patch("authentik_blueprint.live_verifier._find_docker_worker", return_value="avatar_worker_1"), \
             patch("authentik_blueprint.live_verifier._run_command", return_value=0) as mock_run:
            result = run_docker(container=None, blueprint_name="my-bp", verbose=False)
        assert result == 0
        assert mock_run.call_args[0][0] == ["docker", "exec", "avatar_worker_1"]

    def test_explicit_container_used(self):
        with patch("authentik_blueprint.live_verifier._run_command", return_value=0) as mock_run:
            result = run_docker(container="my-container", blueprint_name="my-bp", verbose=False)
        assert result == 0
        assert mock_run.call_args[0][0] == ["docker", "exec", "my-container"]

    def test_no_container_found_returns_1(self):
        with patch("authentik_blueprint.live_verifier._find_docker_worker", return_value=None):
            result = run_docker(container=None, blueprint_name="my-bp", verbose=False)
        assert result == 1


# ---------------------------------------------------------------------------
# run_kubernetes
# ---------------------------------------------------------------------------

class TestRunKubernetes:
    def test_builds_kubectl_command_with_kubeconfig(self):
        with patch("authentik_blueprint.live_verifier._run_command", return_value=0) as mock_run:
            result = run_kubernetes(
                kubeconfig="/path/to/kubeconfig.yml",
                namespace="default",
                blueprint_name="my-bp",
                verbose=False,
            )
        assert result == 0
        cmd = mock_run.call_args[0][0]
        assert "kubectl" in cmd
        assert "--kubeconfig" in cmd
        assert "/path/to/kubeconfig.yml" in cmd
        assert "deployment/avatar-authentik-worker" in cmd

    def test_builds_kubectl_command_without_kubeconfig(self):
        with patch("authentik_blueprint.live_verifier._run_command", return_value=0) as mock_run:
            run_kubernetes(
                kubeconfig=None,
                namespace="staging",
                blueprint_name="my-bp",
                verbose=False,
            )
        cmd = mock_run.call_args[0][0]
        assert "--kubeconfig" not in cmd
        assert "-n" in cmd
        assert "staging" in cmd


# ---------------------------------------------------------------------------
# run (top-level dispatcher)
# ---------------------------------------------------------------------------

class TestRun:
    def test_uses_kubernetes_when_kubeconfig_provided(self):
        with patch("authentik_blueprint.live_verifier.run_kubernetes", return_value=0) as mock_k8s, \
             patch("authentik_blueprint.live_verifier.run_docker") as mock_docker:
            result = run(kubeconfig="/path/to/kube.yml")
        mock_k8s.assert_called_once()
        mock_docker.assert_not_called()
        assert result == 0

    def test_uses_docker_when_no_kubeconfig(self):
        with patch("authentik_blueprint.live_verifier.run_docker", return_value=0) as mock_docker, \
             patch("authentik_blueprint.live_verifier.run_kubernetes") as mock_k8s:
            result = run(kubeconfig=None)
        mock_docker.assert_called_once()
        mock_k8s.assert_not_called()
        assert result == 0
