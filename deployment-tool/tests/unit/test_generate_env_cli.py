from __future__ import annotations

import argparse
import sys
from argparse import Namespace
from pathlib import Path
from types import ModuleType

import pytest

from octopize_avatar_deploy import configure
from octopize_avatar_deploy.components import get_all_components


class DummyRunner:
    init_kwargs = None
    run_kwargs = None

    def __init__(self, **kwargs):
        type(self).init_kwargs = kwargs

    def run(self, **kwargs):
        type(self).run_kwargs = kwargs


def test_run_generate_env_passes_output_path_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    dummy_module = ModuleType("octopize_avatar_deploy.generate_env")
    dummy_module.GenerateEnvRunner = DummyRunner
    monkeypatch.setitem(sys.modules, "octopize_avatar_deploy.generate_env", dummy_module)

    args = Namespace(
        components=["web"],
        api_output_path=Path("/tmp/api.env"),
        web_output_path=Path("/tmp/web.env"),
        python_client_output_path=Path("/tmp/python.env"),
        output_paths=[("web", Path("/tmp/override-web.env"))],
        template_from="github",
        verbose=True,
        non_interactive=True,
        config=Path("/tmp/config.yaml"),
        target="staging",
        api_url="https://api.example.com",
        storage_url="https://storage.example.com",
        sso_url="https://sso.example.com",
    )

    configure._run_generate_env(args, printer=None, input_gatherer=None)

    assert DummyRunner.init_kwargs["output_dir"] == Path.cwd()
    assert DummyRunner.init_kwargs["components"] == ["web"]
    assert DummyRunner.run_kwargs["interactive"] is False
    assert DummyRunner.run_kwargs["config_file"] == Path("/tmp/config.yaml")
    assert DummyRunner.run_kwargs["target"] == "staging"
    assert DummyRunner.run_kwargs["output_path_overrides"] == {
        "api": Path("/tmp/api.env"),
        "web": Path("/tmp/override-web.env"),
        "python_client": Path("/tmp/python.env"),
    }


def test_run_generate_env_defaults_to_all_components(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dummy_module = ModuleType("octopize_avatar_deploy.generate_env")
    dummy_module.GenerateEnvRunner = DummyRunner
    monkeypatch.setitem(sys.modules, "octopize_avatar_deploy.generate_env", dummy_module)

    args = Namespace(
        components=None,
        api_output_path=None,
        web_output_path=None,
        python_client_output_path=None,
        output_paths=None,
        template_from="github",
        verbose=False,
        non_interactive=False,
        config=None,
        target=None,
        api_url=None,
        storage_url=None,
        sso_url=None,
    )

    configure._run_generate_env(args, printer=None, input_gatherer=None)

    assert DummyRunner.init_kwargs["components"] == list(get_all_components().keys())
    assert DummyRunner.run_kwargs["interactive"] is True
    assert DummyRunner.run_kwargs["output_path_overrides"] == {}


@pytest.mark.parametrize(
    ("value", "expected_component", "expected_path"),
    [
        ("api=./api/.env", "api", Path("./api/.env")),
        ("python_client=/tmp/python-client.env", "python_client", Path("/tmp/python-client.env")),
    ],
)
def test_parse_component_output_path(
    value: str, expected_component: str, expected_path: Path
) -> None:
    component, path = configure._parse_component_output_path(value)

    assert component == expected_component
    assert path == expected_path


@pytest.mark.parametrize(
    "value",
    ["api", "=./api/.env", "api=", "unknown=./x.env"],
)
def test_parse_component_output_path_rejects_invalid_values(value: str) -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        configure._parse_component_output_path(value)
