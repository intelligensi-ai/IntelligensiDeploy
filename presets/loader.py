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
    instance_type: str
    docker_image: str
    env: Dict[str, str] = field(default_factory=dict)
    port: int = 8080
    health_path: str = "/health"
    lambda_api_key: str | None = None
    region: str = "us-east-1"
    ssh_key_name: str | None = None
    ssh_private_key_path: str | None = None
    ssh_username: str = "ubuntu"

    @classmethod
    def from_dict(cls, name: str, data: Dict) -> "Preset":
        required = ["instance_type", "docker_image", "port", "health_path"]
        missing = [field for field in required if field not in data]
        if missing:
            raise PresetValidationError(f"Preset '{name}' is missing fields: {', '.join(missing)}")

        env = data.get("env") or {}
        if not isinstance(env, dict):
            raise PresetValidationError("env must be a mapping of key/value pairs")

        return cls(
            name=name,
            instance_type=str(data["instance_type"]),
            docker_image=str(data["docker_image"]),
            env={str(k): str(v) for k, v in env.items()},
            port=int(data["port"]),
            health_path=str(data["health_path"]),
            lambda_api_key=data.get("lambda_api_key"),
            region=str(data.get("region", "us-east-1")),
            ssh_key_name=data.get("ssh_key_name"),
            ssh_private_key_path=data.get("ssh_private_key_path"),
            ssh_username=str(data.get("ssh_username", "ubuntu")),
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
