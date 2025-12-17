"""Simple deploy workflow for the image-server preset."""

from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional
from urllib import request

from infra.lambda_api import LambdaAPIError, LambdaClient
from presets.loader import Preset, PresetValidationError, load_preset, load_state, save_state

STATE_FILE = Path(".intelligensi_instances.json")
PRESET_DIR = Path("presets")


@dataclass
class DeploymentState:
    preset: str
    instance_id: str
    ip: str


class DeploymentError(RuntimeError):
    pass


def _expand(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    return os.path.expanduser(os.path.expandvars(value))


def _get_preset(name: str) -> Preset:
    try:
        preset = load_preset(PRESET_DIR, name)
    except PresetValidationError as exc:
        raise DeploymentError(str(exc))

    preset.lambda_api_key = _expand(preset.lambda_api_key) or os.getenv("LAMBDA_API_KEY")
    preset.ssh_private_key_path = _expand(preset.ssh_private_key_path or os.getenv("SSH_PRIVATE_KEY"))
    preset.ssh_key_name = _expand(preset.ssh_key_name) or os.getenv("LAMBDA_SSH_KEY_NAME")

    if not preset.lambda_api_key:
        raise DeploymentError("Lambda API key must be provided via preset or LAMBDA_API_KEY env var")
    if not preset.ssh_key_name:
        raise DeploymentError("ssh_key_name must be set in preset or LAMBDA_SSH_KEY_NAME env var")
    if not preset.ssh_private_key_path:
        raise DeploymentError("ssh_private_key_path must be set in preset or SSH_PRIVATE_KEY env var")

    return preset


def _read_states() -> Dict[str, DeploymentState]:
    raw = load_state(STATE_FILE)
    states: Dict[str, DeploymentState] = {}
    for key, value in raw.items():
        if not isinstance(value, dict):
            continue
        try:
            states[key] = DeploymentState(
                preset=value["preset"], instance_id=value["instance_id"], ip=value["ip"]
            )
        except KeyError:
            continue
    return states


def _write_states(states: Dict[str, DeploymentState]) -> None:
    payload = {k: {"preset": v.preset, "instance_id": v.instance_id, "ip": v.ip} for k, v in states.items()}
    save_state(STATE_FILE, payload)


def _ssh(ip: str, key_path: str, user: str, command: str, retries: int = 20, delay: int = 5) -> None:
    ssh_cmd = [
        "ssh",
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "UserKnownHostsFile=/dev/null",
        "-o",
        "ConnectTimeout=5",
        "-i",
        key_path,
        f"{user}@{ip}",
        command,
    ]

    for attempt in range(1, retries + 1):
        process = subprocess.run(ssh_cmd, capture_output=True, text=True)

        if process.returncode == 0:
            return

        print(
            f"[SSH] Attempt {attempt}/{retries} failed "
            f"({process.stderr.strip() or process.stdout.strip()}), retrying in {delay}s..."
        )
        time.sleep(delay)

    raise DeploymentError(
        f"SSH failed after {retries} attempts: "
        f"{process.stderr or process.stdout}"
    )


def _build_env_flags(env: Dict[str, str]) -> str:
    """
    Build docker -e flags with guaranteed env var expansion.
    Fails fast if ${VAR} was not resolved.
    """
    parts = []

    for key, value in env.items():
        if value is None:
            continue

        expanded = _expand(value)

        # HARD FAIL if still unresolved
        if expanded.startswith("${") and expanded.endswith("}"):
            raise DeploymentError(
                f"Environment variable {key} was not resolved (value={value}). "
                f"Did you forget to export it or load .env.local?"
            )

        parts.append(f"-e {key}='{expanded}'")

    return " ".join(parts)


def _bootstrap_remote(preset: Preset, state: DeploymentState) -> None:
    key_path = preset.ssh_private_key_path
    if not key_path:
        raise DeploymentError("ssh_private_key_path is required")

    # --- PATCHED DOCKER INSTALLATION ---
    # Remove old conflicting packages
    remove_old = (
        "sudo apt-get remove -y docker docker-engine docker.io containerd runc || true"
    )
    _ssh(state.ip, key_path, preset.ssh_username, remove_old)

    # Update apt and install dependencies
    prep_install = (
        "sudo apt-get update -y && "
        "sudo apt-get install -y ca-certificates curl gnupg lsb-release"
    )
    _ssh(state.ip, key_path, preset.ssh_username, prep_install)

    # Add Docker GPG key
    add_key = (
        "sudo mkdir -m 0755 -p /etc/apt/keyrings && "
        "curl -fsSL https://download.docker.com/linux/ubuntu/gpg | "
        "sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg"
    )
    _ssh(state.ip, key_path, preset.ssh_username, add_key)

    # Add Docker repository
    add_repo = (
        'echo "deb [arch=$(dpkg --print-architecture) '
        'signed-by=/etc/apt/keyrings/docker.gpg] '
        'https://download.docker.com/linux/ubuntu '
        '$(lsb_release -cs) stable" | '
        'sudo tee /etc/apt/sources.list.d/docker.list > /dev/null'
    )
    _ssh(state.ip, key_path, preset.ssh_username, add_repo)

    # Install Docker from official source
    install_docker = (
        "sudo apt-get update -y && "
        "sudo apt-get install -y docker-ce docker-ce-cli containerd.io "
        "docker-buildx-plugin docker-compose-plugin"
    )
    _ssh(state.ip, key_path, preset.ssh_username, install_docker)

    # Enable Docker
    _ssh(state.ip, key_path, preset.ssh_username, "sudo systemctl enable --now docker")

    env_flags = _build_env_flags(preset.env)

    print(f"[ENV] Injecting env vars: {', '.join(preset.env.keys())}")
    run_cmd = (
        f"sudo docker pull {preset.docker_image} && "
        f"sudo docker rm -f image-server || true && "
        f"sudo docker run --gpus all -d -p {preset.port}:{preset.port} "
        f"{env_flags + ' ' if env_flags else ''}--name image-server {preset.docker_image}"
    )
    _ssh(state.ip, key_path, preset.ssh_username, run_cmd)


def deploy_preset(name: str) -> DeploymentState:
    preset = _get_preset(name)

    # 🔐 Required runtime secrets
    required_envs = ["HF_TOKEN"]
    for var in required_envs:
        if not os.getenv(var):
            raise DeploymentError(
                f"Missing required environment variable: {var}"
            )

    states = _read_states()
    if name in states:
        raise DeploymentError(f"Preset '{name}' already deployed at {states[name].ip}")

    client = LambdaClient(api_key=preset.lambda_api_key, region=preset.region)  # type: ignore[arg-type]
    try:
        created = client.create_instance(instance_type=preset.instance_type, ssh_key_name=preset.ssh_key_name)  # type: ignore[arg-type]
        instance = client.wait_for_instance(created.id)
    except LambdaAPIError as exc:
        raise DeploymentError(str(exc))

    if not instance.ip:
        raise DeploymentError("Instance did not return a public IP")

    deployment_state = DeploymentState(preset=name, instance_id=instance.id, ip=instance.ip)
    states[name] = deployment_state
    _write_states(states)

    _bootstrap_remote(preset, deployment_state)

    return deployment_state


def _http_get(url: str, timeout: int = 5) -> Optional[Dict]:
    req = request.Request(url)
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode()
            return json.loads(body)
    except Exception:
        return None


def status_preset(name: str) -> str:
    states = _read_states()
    if name not in states:
        return f"Preset '{name}' is not currently deployed"

    state = states[name]
    preset = _get_preset(name)
    start = time.time()
    health_url = f"http://{state.ip}:{preset.port}{preset.health_path}"
    data = _http_get(health_url)
    if not data:
        return f"{name}: DOWN (unable to reach {health_url})"
    latency = int((time.time() - start) * 1000)
    status = data.get("status", "unknown") if isinstance(data, dict) else "unknown"
    return f"{name}: UP (status={status}, latency={latency}ms, ip={state.ip})"


def shutdown_preset(name: str) -> None:
    states = _read_states()
    if name not in states:
        return

    preset = _get_preset(name)
    state = states[name]
    client = LambdaClient(api_key=preset.lambda_api_key, region=preset.region)  # type: ignore[arg-type]
    try:
        client.delete_instance(state.instance_id)
    except LambdaAPIError as exc:
        raise DeploymentError(str(exc))

    states.pop(name, None)
    _write_states(states)
