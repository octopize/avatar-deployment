"""Path resolution helpers for generate-env output destinations."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from octopize_avatar_deploy.input_gatherer import InputGatherer
from octopize_avatar_deploy.steps.base import ValidationError, ValidationSuccess


@dataclass(frozen=True)
class ResolvedGenerateEnvPaths:
    """Resolved output paths for the selected generate-env components."""

    resolved_paths: dict[str, Path]
    prompted_output_paths: dict[str, str]


def resolve_generate_env_output_paths(
    *,
    selected_components: list[str],
    config: Mapping[str, Any],
    config_file: Path | None,
    interactive: bool,
    input_gatherer: InputGatherer,
    output_path_overrides: Mapping[str, Path] | None = None,
) -> ResolvedGenerateEnvPaths:
    """Resolve output paths for the selected components only."""
    configured_output_paths = _get_configured_output_paths(config)
    config_base_dir = config_file.parent if config_file is not None else None

    resolved_paths: dict[str, Path] = {}
    missing_components: list[str] = []

    for component in selected_components:
        override_path = (
            None if output_path_overrides is None else output_path_overrides.get(component)
        )
        if override_path is not None:
            resolved_path = _resolve_output_path(override_path, base_dir=Path.cwd())
            _validate_output_path(component, resolved_path)
            resolved_paths[component] = resolved_path
            continue

        configured_path = configured_output_paths.get(component)
        if configured_path is None:
            missing_components.append(component)
            continue

        resolved_path = _resolve_output_path(configured_path, base_dir=config_base_dir)
        _validate_output_path(component, resolved_path)
        resolved_paths[component] = resolved_path

    prompted_output_paths: dict[str, str] = {}
    if missing_components:
        if not interactive:
            missing_list = ", ".join(missing_components)
            raise ValueError(
                "Missing output path for selected component(s): "
                f"{missing_list}. Configure generate_env.output_paths or "
                "provide output_path_overrides."
            )

        prompt_base_dir = config_base_dir or Path.cwd()
        for component in missing_components:
            raw_value = input_gatherer.prompt(
                f"Output path for {component} env file",
                validate=lambda value, component=component, base_dir=prompt_base_dir: (
                    _validate_prompted_output_path(value, component=component, base_dir=base_dir)
                ),
                key=f"generate_env.output_paths.{component}",
            )
            resolved_path = _resolve_output_path(raw_value, base_dir=prompt_base_dir)
            resolved_paths[component] = resolved_path
            prompted_output_paths[component] = raw_value

    return ResolvedGenerateEnvPaths(
        resolved_paths=resolved_paths,
        prompted_output_paths=prompted_output_paths,
    )


def persist_generate_env_output_paths(
    *, config_file: Path, config_data: dict[str, Any], output_paths: Mapping[str, str]
) -> None:
    """Persist prompted output paths back into the same config file."""
    if not output_paths:
        return

    generate_env = config_data.get("generate_env")
    if generate_env is None:
        generate_env = {}
        config_data["generate_env"] = generate_env
    elif not isinstance(generate_env, dict):
        raise ValueError("Config key 'generate_env' must be a mapping")

    existing_output_paths = generate_env.get("output_paths")
    if existing_output_paths is None:
        existing_output_paths = {}
        generate_env["output_paths"] = existing_output_paths
    elif not isinstance(existing_output_paths, dict):
        raise ValueError("Config key 'generate_env.output_paths' must be a mapping")

    existing_output_paths.update(output_paths)

    with open(config_file, "w") as f:
        yaml.safe_dump(config_data, f, default_flow_style=False, sort_keys=False)


def _get_configured_output_paths(config: Mapping[str, Any]) -> dict[str, str]:
    generate_env = config.get("generate_env")
    if generate_env is None:
        return {}
    if not isinstance(generate_env, Mapping):
        raise ValueError("Config key 'generate_env' must be a mapping")

    output_paths = generate_env.get("output_paths")
    if output_paths is None:
        return {}
    if not isinstance(output_paths, Mapping):
        raise ValueError("Config key 'generate_env.output_paths' must be a mapping")

    normalized: dict[str, str] = {}
    for component, raw_path in output_paths.items():
        if not isinstance(component, str):
            raise ValueError(
                "Config key 'generate_env.output_paths' must use string component names"
            )
        if isinstance(raw_path, Path):
            normalized[component] = str(raw_path)
            continue
        if not isinstance(raw_path, str):
            raise ValueError(
                f"Config key 'generate_env.output_paths.{component}' must be a string path"
            )
        normalized[component] = raw_path
    return normalized


def _validate_prompted_output_path(
    value: str, *, component: str, base_dir: Path
) -> ValidationSuccess[str] | ValidationError:
    try:
        resolved_path = _resolve_output_path(value, base_dir=base_dir)
        _validate_output_path(component, resolved_path)
    except ValueError as exc:
        return ValidationError(str(exc))
    return ValidationSuccess(value)


def _resolve_output_path(raw_path: str | Path, *, base_dir: Path | None) -> Path:
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = (base_dir or Path.cwd()) / path
    return path


def _validate_output_path(component: str, output_path: Path) -> None:
    if output_path.exists() and output_path.is_dir():
        raise ValueError(
            f"Output path for component '{component}' points to a directory: {output_path}"
        )

    parent_dir = output_path.parent
    if not parent_dir.exists():
        raise ValueError(
            f"Output path parent directory does not exist for component '{component}': {parent_dir}"
        )
    if not parent_dir.is_dir():
        raise ValueError(
            f"Output path parent is not a directory for component '{component}': {parent_dir}"
        )
