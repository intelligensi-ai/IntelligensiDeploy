"""Simple deploy workflow for the image-server preset."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib import request

from infra.lambda_api import LambdaAPIError, LambdaClient, rank_gpu_options
from intelligensi_deploy.agent.repair_engine import build_repair_record, classify_failure
from presets.loader import Preset, PresetValidationError, load_preset, load_state, save_state

STATE_FILE = Path(".intelligensi_instances.json")
WORKFLOW_STATE_FILE = Path(".intelligensi_state.json")
RUNTIME_STATE_FILE = Path(".intelligensi_runtime.json")
REPAIR_STATE_FILE = Path(".intelligensi_repairs.json")
LOG_FILE = Path("deploy.log")
PRESET_DIR = Path("presets")
CAPACITY_FALLBACK_LIMIT = 3


@dataclass
class DeploymentState:
    preset: str
    instance_id: str
    ip: str
    port: int = 8080
    health_path: str = "/health"
    service: str = ""


class DeploymentError(RuntimeError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return fallback


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2))


def _append_deploy_log(message: str) -> None:
    LOG_FILE.open("a", encoding="utf-8").write(f"{message}\n")


def _record_workflow_event(from_state: str, to_state: str, context: Dict[str, Any]) -> None:
    state = _safe_json(WORKFLOW_STATE_FILE, {"current_state": "idle", "history": []})
    if not isinstance(state, dict):
        state = {"current_state": "idle", "history": []}
    history = state.get("history")
    if not isinstance(history, list):
        history = []
        state["history"] = history
    history.append(
        {
            "timestamp": _utc_now(),
            "from_state": from_state,
            "to_state": to_state,
            "context": context,
        }
    )
    state["current_state"] = to_state
    _write_json(WORKFLOW_STATE_FILE, state)


def _record_runtime_selection(preset_name: str, instance_type: str, region: str, status: str) -> None:
    runtime = _safe_json(RUNTIME_STATE_FILE, {"version": 1, "fleet": {}, "executionHistory": []})
    if not isinstance(runtime, dict):
        runtime = {"version": 1, "fleet": {}, "executionHistory": []}
    history = runtime.get("executionHistory")
    if not isinstance(history, list):
        history = []
        runtime["executionHistory"] = history
    history.append(
        {
            "storedAt": _utc_now(),
            "workload": {"id": preset_name, "name": preset_name, "type": "image_generation"},
            "providerType": "lambda",
            "routeReason": f"Selected {instance_type} in {region} for Lambda launch.",
            "action": {
                "commands": ["python3 cli/intelligensi_deploy.py deploy " + preset_name],
                "notes": [status],
                "instance": {
                    "id": f"pending-{preset_name}",
                    "name": preset_name,
                    "providerType": "lambda",
                    "status": "provisioning",
                    "workloadAssigned": "image_generation",
                    "service": "image-server",
                    "hourlyCostUsd": 0,
                    "updatedAt": _utc_now(),
                    "metadata": {"instance_type": instance_type, "region": region},
                },
            },
        }
    )
    _write_json(RUNTIME_STATE_FILE, runtime)


def _record_repair(logs: List[str], error_text: str, retry_number: int, retry_limit: int, result: str) -> None:
    repair_state = _safe_json(REPAIR_STATE_FILE, {"version": 1, "repairs": []})
    if not isinstance(repair_state, dict):
        repair_state = {"version": 1, "repairs": []}
    repairs = repair_state.get("repairs")
    if not isinstance(repairs, list):
        repairs = []
        repair_state["repairs"] = repairs
    record = build_repair_record(logs, error_text, retry_number=retry_number, retry_limit=retry_limit)
    record["stored_at"] = _utc_now()
    record["result"] = result
    repairs.append(record)
    repair_state["latest"] = record
    _write_json(REPAIR_STATE_FILE, repair_state)


def _is_capacity_or_shape_error(error_text: str) -> bool:
    category = classify_failure([], error_text).category
    return category in {"lambda_capacity", "lambda_shape_drift"}


def _candidate_instance_types(client: LambdaClient, preset: Preset) -> List[str]:
    selected = preset.instance_type
    try:
        options = client.list_available_gpu_options(region=preset.region)
        ranked = rank_gpu_options(preset.name, options, preset.region)
    except LambdaAPIError as exc:
        _append_deploy_log(f"[LAMBDA] Availability lookup failed before launch: {exc}")
        return [selected]

    candidates = [selected]
    for option in ranked:
        if option.available and option.instance_type_name not in candidates:
            candidates.append(option.instance_type_name)
        if len(candidates) >= CAPACITY_FALLBACK_LIMIT:
            break
    return candidates


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
                preset=value["preset"],
                instance_id=value["instance_id"],
                ip=value["ip"],
                port=int(value.get("port", 8080)),
                health_path=str(value.get("health_path", "/health")),
                service=str(value.get("service", "")),
            )
        except KeyError:
            continue
    return states


def _write_states(states: Dict[str, DeploymentState]) -> None:
    payload = {
        k: {
            "preset": v.preset,
            "instance_id": v.instance_id,
            "ip": v.ip,
            "port": v.port,
            "health_path": v.health_path,
            "service": v.service,
        }
        for k, v in states.items()
    }
    save_state(STATE_FILE, payload)


def _instance_is_active(status: str) -> bool:
    normalized = (status or "").strip().lower()
    return normalized not in {
        "",
        "terminated",
        "terminating",
        "deleted",
        "destroyed",
        "stopped",
        "failed",
        "not_found",
    }


def _drop_stale_deployment_state(name: str, states: Dict[str, DeploymentState], reason: str) -> None:
    stale = states.pop(name, None)
    if stale:
        _write_states(states)
        _append_deploy_log(
            f"[STATE] Removed stale deployment record for {name} "
            f"({stale.instance_id} at {stale.ip}): {reason}"
        )
        _record_workflow_event(
            "planning",
            "planning",
            {
                "preset": name,
                "removed_stale_instance_id": stale.instance_id,
                "removed_stale_ip": stale.ip,
                "reason": reason,
            },
        )


def _reconcile_existing_deployment(name: str, states: Dict[str, DeploymentState], client: LambdaClient) -> None:
    existing = states.get(name)
    if not existing:
        return

    try:
        instance = client.get_instance(existing.instance_id)
    except LambdaAPIError as exc:
        if exc.status == 404:
            _drop_stale_deployment_state(name, states, "Lambda API reported instance not found.")
            return
        raise DeploymentError(f"Preset '{name}' already deployed at {existing.ip}; status check failed: {exc}")

    if _instance_is_active(instance.status):
        ip = instance.ip or existing.ip
        raise DeploymentError(
            f"Preset '{name}' already deployed at {ip} "
            f"(Lambda status: {instance.status}, instance_id: {existing.instance_id})"
        )

    _drop_stale_deployment_state(
        name,
        states,
        f"Lambda status is {instance.status}; allowing redeploy.",
    )


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


def _required_env_vars(preset: Preset) -> List[str]:
    required = {
        value[2:-1]
        for value in preset.env.values()
        if isinstance(value, str) and value.startswith("${") and value.endswith("}")
    }
    if preset.lambda_api_key and preset.lambda_api_key.startswith("${") and preset.lambda_api_key.endswith("}"):
        required.add(preset.lambda_api_key[2:-1])
    registry_password_env = getattr(preset, "registry_password_env", "")
    if registry_password_env:
        required.add(registry_password_env)
    return sorted(required)


def _service_name(preset: Preset) -> str:
    service = preset.service or preset.name
    return "".join(char if char.isalnum() or char in "_.-" else "-" for char in service)


def _docker_login_prefix(preset: Preset) -> str:
    registry_url = getattr(preset, "registry_url", "")
    registry_password_env = getattr(preset, "registry_password_env", "")
    if not registry_url or not registry_password_env:
        return ""

    token = os.getenv(registry_password_env, "")
    if not token:
        raise DeploymentError(
            f"Missing required environment variable: {registry_password_env}. "
            f"It is needed to pull {preset.docker_image} from {registry_url}."
        )

    username = getattr(preset, "registry_username", "") or "oauth2"
    return (
        f"printf %s {shlex.quote(token)} | "
        f"sudo docker login {shlex.quote(registry_url)} "
        f"-u {shlex.quote(username)} --password-stdin && "
    )


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

    configure_nvidia_runtime = (
        "if command -v nvidia-ctk >/dev/null 2>&1; then "
        "sudo nvidia-ctk runtime configure --runtime=docker && "
        "sudo systemctl restart docker; "
        "fi"
    )
    _ssh(state.ip, key_path, preset.ssh_username, configure_nvidia_runtime)

    env_flags = _build_env_flags(preset.env)
    service_name = _service_name(preset)
    docker_login = _docker_login_prefix(preset)

    print(f"[ENV] Injecting env vars: {', '.join(preset.env.keys())}")
    run_cmd = (
        f"{docker_login}"
        f"sudo docker pull {preset.docker_image} && "
        f"sudo docker rm -f {service_name} || true && "
        f"sudo docker run --gpus all -d -p {preset.port}:{preset.port} "
        f"{env_flags + ' ' if env_flags else ''}--name {service_name} {preset.docker_image}"
    )
    _ssh(state.ip, key_path, preset.ssh_username, run_cmd)


def deploy_preset(name: str) -> DeploymentState:
    preset = _get_preset(name)

    # Required runtime and registry secrets. Validate before launching a paid VM.
    for var in _required_env_vars(preset):
        if not os.getenv(var):
            raise DeploymentError(
                f"Missing required environment variable: {var}"
            )

    client = LambdaClient(api_key=preset.lambda_api_key, region=preset.region)  # type: ignore[arg-type]
    states = _read_states()
    _reconcile_existing_deployment(name, states, client)

    candidates = _candidate_instance_types(client, preset)
    attempted: List[Dict[str, str]] = []
    instance = None
    last_error: Optional[str] = None
    _record_workflow_event(
        "planning",
        "provisioning",
        {"preset": name, "provider": "lambda", "candidate_instance_types": candidates},
    )

    for attempt_index, instance_type in enumerate(candidates, start=1):
        _append_deploy_log(f"[LAMBDA] Launch attempt {attempt_index}/{len(candidates)} with {instance_type} in {preset.region}")
        attempted.append({"instance_type": instance_type, "region": preset.region})
        try:
            created = client.create_instance(instance_type=instance_type, ssh_key_name=preset.ssh_key_name)  # type: ignore[arg-type]
            instance = client.wait_for_instance(created.id)
            preset.instance_type = instance_type
            _record_runtime_selection(name, instance_type, preset.region, "Lambda instance launch succeeded.")
            _record_workflow_event(
                "provisioning",
                "building",
                {"preset": name, "selected_instance_type": instance_type, "attempted": attempted},
            )
            break
        except LambdaAPIError as exc:
            last_error = str(exc)
            _append_deploy_log(f"[LAMBDA] Launch failed for {instance_type}: {last_error}")
            retry_allowed = attempt_index < len(candidates) and _is_capacity_or_shape_error(last_error)
            _record_repair(
                [f"Launch failed for {instance_type}: {last_error}"],
                last_error,
                retry_number=attempt_index - 1,
                retry_limit=CAPACITY_FALLBACK_LIMIT,
                result="retrying" if retry_allowed else "manual_required",
            )
            _record_workflow_event(
                "provisioning",
                "provisioning" if retry_allowed else "error",
                {
                    "preset": name,
                    "failed_instance_type": instance_type,
                    "error": last_error,
                    "retry_allowed": retry_allowed,
                    "attempted": attempted,
                },
            )
            if not retry_allowed:
                break

    if instance is None:
        raise DeploymentError(last_error or "Lambda launch failed before returning an instance")

    if not instance.ip:
        raise DeploymentError("Instance did not return a public IP")

    deployment_state = DeploymentState(
        preset=name,
        instance_id=instance.id,
        ip=instance.ip,
        port=preset.port,
        health_path=preset.health_path,
        service=getattr(preset, "service", "") or name,
    )
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
