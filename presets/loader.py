"""Preset loading utilities for IntelligensiDeploy."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

try:
    import yaml
except ImportError:  # pragma: no cover - fallback when PyYAML is unavailable
    yaml = None


class PresetValidationError(Exception):
    """Raised when a preset file is invalid."""


@dataclass
class Preset:
    """Concrete preset definition for a deployment target."""

    name: str
    instance_type: str = ""
    docker_image: str = ""
    env: Dict[str, str] = field(default_factory=dict)
    port: int = 8080
    health_path: str = "/health"
    lambda_api_key: str | None = None
    region: str = "us-east-1"
    ssh_key_name: str | None = None
    ssh_private_key_path: str | None = None
    ssh_username: str = "ubuntu"
    provider: str | None = None
    service: str | None = None
    deployment_mode: str | None = None
    environment: str | None = None
    disk_size_gb: int | None = None
    registry_url: str | None = None
    registry_username: str | None = None
    registry_password_env: str | None = None

    @classmethod
    def from_dict(cls, name: str, data: Dict) -> "Preset":
        classic_shape = "instance_type" in data and "docker_image" in data
        provider_shape = "provider" in data and "service" in data

        if not classic_shape and not provider_shape:
            raise PresetValidationError(
                f"Preset '{name}' must define either classic deployment fields "
                f"(instance_type, docker_image) or provider fields (provider, service)"
            )

        env = data.get("env") or {}
        if not isinstance(env, dict):
            raise PresetValidationError("env must be a mapping of key/value pairs")

        docker_image = data.get("docker_image", data.get("image", ""))
        port_value = data.get("port", data.get("service_port", 8080))
        health_path = data.get("health_path", "/health")
        registry = data.get("registry") or {}
        if not isinstance(registry, dict):
            raise PresetValidationError("registry must be a mapping when provided")

        return cls(
            name=name,
            instance_type=str(data.get("instance_type", "")),
            docker_image=str(docker_image),
            env={str(k): str(v) for k, v in env.items()},
            port=int(port_value),
            health_path=str(health_path),
            lambda_api_key=data.get("lambda_api_key"),
            region=str(data.get("region", "us-east-1")),
            ssh_key_name=data.get("ssh_key_name"),
            ssh_private_key_path=data.get("ssh_private_key_path"),
            ssh_username=str(data.get("ssh_username", "ubuntu")),
            provider=str(data["provider"]) if data.get("provider") is not None else None,
            service=str(data["service"]) if data.get("service") is not None else None,
            deployment_mode=str(data["deployment_mode"]) if data.get("deployment_mode") is not None else None,
            environment=str(data["environment"]) if data.get("environment") is not None else None,
            disk_size_gb=int(data["disk_size_gb"]) if data.get("disk_size_gb") is not None else None,
            registry_url=str(registry["url"]) if registry.get("url") is not None else None,
            registry_username=str(registry["username"]) if registry.get("username") is not None else None,
            registry_password_env=str(registry["password_env"]) if registry.get("password_env") is not None else None,
        )


def load_presets(presets_dir: Path) -> List[Preset]:
    """Load all presets from the provided directory."""

    presets: List[Preset] = []
    for preset_file in sorted(presets_dir.glob("*.yaml")):
        data = _load_yaml(preset_file)
        if not isinstance(data, dict):
            raise PresetValidationError(f"Preset file {preset_file} must define a mapping")
        presets.append(Preset.from_dict(preset_file.stem, data))
    return presets


def load_preset(presets_dir: Path, name: str) -> Preset:
    """Load a single preset by name."""

    preset_file = presets_dir / f"{name}.yaml"
    if not preset_file.exists():
        raise PresetValidationError(f"Preset '{name}' not found in {presets_dir}")

    data = _load_yaml(preset_file)
    if not isinstance(data, dict):
        raise PresetValidationError(f"Preset file {preset_file} must define a mapping")

    return Preset.from_dict(name, data)


def _load_yaml(preset_file: Path) -> Dict:
    text = preset_file.read_text()
    if yaml:
        return yaml.safe_load(text) or {}

    return _parse_minimal_yaml(text, preset_file)


def _parse_minimal_yaml(text: str, preset_file: Path) -> Dict:
    """Parse a tiny subset of YAML (mappings only) when PyYAML is unavailable."""

    root: Dict[str, object] = {}
    stack: list[tuple[int, Dict[str, object]]] = [(0, root)]

    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue

        indent = len(line) - len(line.lstrip(" "))
        key, _, value = line.strip().partition(":")
        value = value.strip()

        while stack and indent < stack[-1][0]:
            stack.pop()
        if not stack:
            raise PresetValidationError(f"Invalid indentation in {preset_file}")

        current = stack[-1][1]
        if not isinstance(current, dict):
            raise PresetValidationError(f"Unexpected structure in {preset_file}")

        if value == "":
            new_map: Dict[str, object] = {}
            current[key] = new_map
            stack.append((indent + 2, new_map))
            continue

        if (value.startswith("\"") and value.endswith("\"")) or (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]

        current[key] = value

    return root


def save_state(state_path: Path, state: Dict) -> None:
    state_path.write_text(json.dumps(state, indent=2))


def load_state(state_path: Path) -> Dict:
    if not state_path.exists():
        return {}
    try:
        return json.loads(state_path.read_text())
    except json.JSONDecodeError:
        return {}
