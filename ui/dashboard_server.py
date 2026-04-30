"""Local dashboard server for IntelligensiDeploy.

Serves the admin UI plus JSON endpoints backed by the existing deployment
state, instance state, preset files, and optional logs.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib import request
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
UI_DIR = ROOT / "ui"
STATE_PATH = ROOT / ".intelligensi_state.json"
INSTANCE_PATH = ROOT / ".intelligensi_instances.json"
LOG_PATH = ROOT / "deploy.log"
PRESET_DIR = ROOT / "presets"
NEBIUS_CONFIG_PATH = ROOT / ".intelligensi_nebius_config.json"
NEBIUS_SECRET_PATH = ROOT / ".intelligensi_nebius_secrets.json"
LAMBDA_CONFIG_PATH = ROOT / ".intelligensi_lambda_config.json"
LAMBDA_SECRET_PATH = ROOT / ".intelligensi_lambda_secrets.json"
LAMBDA_AVAILABILITY_PATH = ROOT / ".intelligensi_lambda_availability.json"
LAMBDA_HEALTH_PATH = ROOT / ".intelligensi_lambda_health.json"
LAMBDA_INSTANCE_STATUS_PATH = ROOT / ".intelligensi_lambda_instance_status.json"
REPAIR_STATE_PATH = ROOT / ".intelligensi_repairs.json"
RUNTIME_STATE_PATH = ROOT / ".intelligensi_runtime.json"
PREVIEW_IMAGE_DIR = UI_DIR / "images"
PREVIEW_VIDEO_DIR = UI_DIR / "videos"
PREVIEW_HISTORY_PATH = ROOT / ".intelligensi_preview_history.json"
ACTIVE_DEPLOY: Dict[str, Any] = {"process": None, "preset": None}
ACTIVE_DEPLOY_LOCK = threading.Lock()

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from intelligensi_deploy.agent.auto_fix_suggester import suggest_fixes
from intelligensi_deploy.agent.repair_engine import build_repair_record
from infra.lambda_api import LambdaAPIError, LambdaClient
from presets.loader import PresetValidationError, load_preset


def _safe_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return fallback


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2))
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def _tail_lines(path: Path, limit: int) -> List[str]:
    if not path.exists():
        return []
    try:
        lines = path.read_text(errors="ignore").splitlines()
    except OSError:
        return []
    return lines[-limit:]


def _load_presets() -> List[Dict[str, Any]]:
    presets: List[Dict[str, Any]] = []
    for preset_path in sorted(PRESET_DIR.glob("*.yaml")):
        presets.append(
            {
                "name": preset_path.stem,
                "path": str(preset_path.relative_to(ROOT)),
                "modified_at": preset_path.stat().st_mtime,
            }
        )
    return presets


def _preset_names() -> set[str]:
    return {preset["name"] for preset in _load_presets()}


def _start_preset_deploy(preset: str) -> Dict[str, Any]:
    preset_path = PRESET_DIR / f"{preset}.yaml"
    if not preset_path.exists():
        raise FileNotFoundError(preset)

    command = [sys.executable, "cli/intelligensi_deploy.py", "deploy", preset]
    if preset == "ltx-worker-nebius-dev":
        command = ["bash", "scripts/deploy_ltx_worker.sh", "dev"]

    with ACTIVE_DEPLOY_LOCK:
        process = ACTIVE_DEPLOY.get("process")
        if process is not None and process.poll() is None:
            return {
                "ok": False,
                "already_running": True,
                "preset": ACTIVE_DEPLOY.get("preset"),
                "pid": process.pid,
            }

        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        log_handle = LOG_PATH.open("a", encoding="utf-8")
        log_handle.write(f"\n[UI] Starting deployment for preset {preset}\n")
        log_handle.flush()

        lambda_config = load_lambda_config()
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        lambda_env_map = {
            "api_key": "LAMBDALABS_API_KEY",
            "ghcr_token": "GHCR_TOKEN",
            "hf_token": "HF_TOKEN",
            "ssh_key_name": "LAMBDA_SSH_KEY_NAME",
            "ssh_private_key_path": "SSH_PRIVATE_KEY",
        }
        for config_key, env_key in lambda_env_map.items():
            value = lambda_config.get(config_key, "").strip()
            if value:
                env[env_key] = value
        runtime = _preset_runtime_profile(preset)
        model_id = str(runtime.get("model_id") or lambda_config.get("model_id", "")).strip()
        if model_id:
            if preset in {"ltx-worker-lambda", "ltx-2.3-worker-lambda"}:
                env["LTX_MODEL_ID"] = model_id
            else:
                env["MODEL_ID"] = model_id
        process = subprocess.Popen(
            command,
            cwd=str(ROOT),
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            env=env,
        )
        ACTIVE_DEPLOY["process"] = process
        ACTIVE_DEPLOY["preset"] = preset
        return {"ok": True, "preset": preset, "pid": process.pid}


def _empty_lambda_config() -> Dict[str, str]:
    return {
        "api_key": "",
        "ghcr_token": "",
        "hf_token": "",
        "region": "us-east-1",
        "instance_type": "gpu_1x_a10",
        "ssh_key_name": "intelligensi-lambda",
        "ssh_private_key_path": "~/.ssh/intelligensi_lambda",
        "ssh_username": "ubuntu",
        "docker_image": "ghcr.io/intelligensi-ai/intelligensi-image-server:latest",
        "model_id": "black-forest-labs/FLUX.1-schnell",
        "service_port": "8080",
        "health_path": "/health",
    }


def load_lambda_config() -> Dict[str, str]:
    config = _empty_lambda_config()
    public_data = _safe_json(LAMBDA_CONFIG_PATH, {})
    secret_data = _safe_json(LAMBDA_SECRET_PATH, {})

    if isinstance(public_data, dict):
        for key, value in public_data.items():
            if key in config and value is not None:
                config[key] = str(value)
    if isinstance(secret_data, dict):
        for key, value in secret_data.items():
            if key in config and value is not None:
                config[key] = str(value)
    return config


def _mask_lambda_config(config: Dict[str, str]) -> Dict[str, str]:
    masked = config.copy()
    for key in ("api_key", "ghcr_token", "hf_token"):
        if masked.get(key):
            masked[key] = ""
    return masked


def save_lambda_config(payload: Dict[str, Any]) -> Dict[str, str]:
    current = load_lambda_config()
    allowed_keys = set(current.keys())
    updated = current.copy()

    for key, value in payload.items():
        if key not in allowed_keys:
            continue
        incoming = str(value).strip()
        if key in {"api_key", "ghcr_token", "hf_token"} and incoming == "":
            continue
        updated[key] = incoming

    public_fields = {
        "region",
        "instance_type",
        "ssh_key_name",
        "ssh_private_key_path",
        "ssh_username",
        "docker_image",
        "model_id",
        "service_port",
        "health_path",
    }
    secret_fields = {"api_key", "ghcr_token", "hf_token"}

    _write_json(LAMBDA_CONFIG_PATH, {key: updated[key] for key in public_fields})
    _write_json(LAMBDA_SECRET_PATH, {key: updated[key] for key in secret_fields})
    return updated


def build_lambda_export_block(config: Dict[str, str]) -> str:
    ordered_pairs = [
        ("LAMBDALABS_API_KEY", config.get("api_key", "")),
        ("GHCR_TOKEN", config.get("ghcr_token", "")),
        ("HF_TOKEN", config.get("hf_token", "")),
        ("LAMBDA_SSH_KEY_NAME", config.get("ssh_key_name", "")),
        ("SSH_PRIVATE_KEY", config.get("ssh_private_key_path", "")),
    ]
    return "\n".join(f"export {key}={_shell_quote(value)}" for key, value in ordered_pairs)


def build_lambda_commands(config: Dict[str, str]) -> List[str]:
    return [
        build_lambda_export_block(config),
        "python3 cli/intelligensi_deploy.py deploy image-server-v13",
        "python3 cli/intelligensi_deploy.py status image-server-v13",
    ]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_lambda_availability() -> Dict[str, Any]:
    payload = _safe_json(LAMBDA_AVAILABILITY_PATH, {})
    return payload if isinstance(payload, dict) else {}


def _lambda_availability_response() -> Dict[str, Any]:
    config = load_lambda_config()
    availability = load_lambda_availability()
    selected = availability.get("selected_option")
    options = availability.get("options", [])
    if not isinstance(options, list):
        options = []
    recommended = next((option for option in options if isinstance(option, dict) and option.get("available")), None)
    if not isinstance(selected, dict):
        selected = next(
            (
                option
                for option in options
                if isinstance(option, dict)
                and option.get("instance_type_name") == config.get("instance_type")
                and option.get("region_name") == config.get("region")
            ),
            None,
        )
    return {
        "ok": not bool(availability.get("error")),
        "config": _mask_lambda_config(config),
        "path": str(LAMBDA_AVAILABILITY_PATH.relative_to(ROOT)) if LAMBDA_AVAILABILITY_PATH.exists() else None,
        "checked_at": availability.get("checked_at"),
        "region": availability.get("region") or config.get("region"),
        "options": options,
        "recommended_option": recommended,
        "selected_option": selected,
        "error": availability.get("error"),
        "has_api_key": bool(config.get("api_key")),
    }


def refresh_lambda_availability() -> Dict[str, Any]:
    config = load_lambda_config()
    api_key = config.get("api_key", "").strip()
    region = config.get("region", "").strip() or "us-east-1"
    selected_type = config.get("instance_type", "").strip()
    if not api_key:
        payload = {
            "checked_at": _utc_now(),
            "region": region,
            "options": [],
            "selected_option": None,
            "error": "Missing Lambda API key. Save it in Lambda Config before refreshing availability.",
        }
        _write_json(LAMBDA_AVAILABILITY_PATH, payload)
        return _lambda_availability_response()

    try:
        client = LambdaClient(api_key=api_key, region=region, timeout=20)
        options = [option.to_dict() for option in client.list_available_gpu_options(region=region)]
        selected = next((option for option in options if option.get("instance_type_name") == selected_type), None)
        payload = {
            "checked_at": _utc_now(),
            "region": region,
            "options": options,
            "selected_option": selected,
            "error": None,
        }
    except LambdaAPIError as exc:
        payload = {
            "checked_at": _utc_now(),
            "region": region,
            "options": [],
            "selected_option": None,
            "error": str(exc),
        }
    _write_json(LAMBDA_AVAILABILITY_PATH, payload)
    return _lambda_availability_response()


def select_lambda_gpu_option(payload: Dict[str, Any]) -> Dict[str, Any]:
    instance_type = str(payload.get("instance_type_name") or "").strip()
    region = str(payload.get("region_name") or "").strip()
    if not instance_type:
        raise ValueError("Missing instance_type_name")

    config_payload: Dict[str, str] = {"instance_type": instance_type}
    if region:
        config_payload["region"] = region
    save_lambda_config(config_payload)

    availability = load_lambda_availability()
    options = availability.get("options", [])
    selected = None
    if isinstance(options, list):
        selected = next(
            (
                option
                for option in options
                if isinstance(option, dict)
                and option.get("instance_type_name") == instance_type
                and (not region or option.get("region_name") == region)
            ),
            None,
        )
    if selected is None:
        selected = {
            "instance_type_name": instance_type,
            "region_name": region,
            "available": False,
            "availability_reason": "Selected manually before availability refresh.",
        }
    availability["selected_option"] = selected
    availability["region"] = region or availability.get("region") or load_lambda_config().get("region")
    availability["updated_at"] = _utc_now()
    _write_json(LAMBDA_AVAILABILITY_PATH, availability)
    return _lambda_availability_response()


def load_repair_state() -> Dict[str, Any]:
    payload = _safe_json(REPAIR_STATE_PATH, {"version": 1, "repairs": []})
    return payload if isinstance(payload, dict) else {"version": 1, "repairs": []}


def repair_state_response() -> Dict[str, Any]:
    state = load_repair_state()
    repairs = state.get("repairs", [])
    if not isinstance(repairs, list):
        repairs = []
    latest = state.get("latest")
    if not isinstance(latest, dict) and repairs:
        latest = repairs[-1] if isinstance(repairs[-1], dict) else None
    return {
        "ok": True,
        "path": str(REPAIR_STATE_PATH.relative_to(ROOT)) if REPAIR_STATE_PATH.exists() else None,
        "latest": latest,
        "repairs": repairs[-20:],
    }


def analyze_latest_logs_for_repair(limit: int = 120) -> Dict[str, Any]:
    lines = _tail_lines(LOG_PATH, limit)
    repair_state = load_repair_state()
    repairs = repair_state.get("repairs")
    if not isinstance(repairs, list):
        repairs = []
        repair_state["repairs"] = repairs

    error_text = "\n".join(lines[-20:])
    record = build_repair_record(lines, error_text, retry_number=0, retry_limit=1)
    record["stored_at"] = _utc_now()
    record["source"] = "deploy.log"
    record["prompt"] = "intelligensi_deploy/agent/prompts/deployment_log_healer.md"
    if record.get("classification", {}).get("category") == "missing_env_file":
        record["manual_values_needed"] = [
            "Lambda API key",
            "Lambda SSH private key path",
            "GHCR token",
            "HF_TOKEN",
        ]
        record["safe_local_action"] = (
            "Use the dashboard Lambda Config panel for the current Lambda-first flow. "
            "The LTX service.env example has been removed."
        )
        record["result"] = "manual_values_required"
    if record.get("classification", {}).get("category") == "provider_host_config_missing":
        record["manual_values_needed"] = [
            "NEBIUS_IP",
            "SSH_USERNAME",
            "NEBIUS_SSH_PRIVATE_KEY_PATH",
        ]
        record["safe_local_action"] = (
            "Create services/ltx-worker/provider.nebius.env from the example and put host/SSH settings there. "
            "Keep LTX model settings in services/ltx-worker/model.env."
        )
        record["result"] = "manual_values_required"

    repairs.append(record)
    repair_state["latest"] = record
    _write_json(REPAIR_STATE_PATH, repair_state)
    return repair_state_response()


def _load_lambda_target(preset: str = "image-server-v13") -> Dict[str, Any]:
    instances = _safe_json(INSTANCE_PATH, {})
    if not isinstance(instances, dict):
        instances = {}
    target = instances.get(preset)
    if not isinstance(target, dict):
        for name, value in instances.items():
            if isinstance(value, dict) and value.get("preset") == preset:
                target = value
                break
    if not isinstance(target, dict):
        raise KeyError(preset)

    config = load_lambda_config()
    runtime = _preset_runtime_profile(preset)
    return {
        "preset": preset,
        "instance_id": str(target.get("instance_id") or target.get("id") or ""),
        "ip": str(target.get("ip") or target.get("publicIp") or ""),
        "port": int(target.get("port") or runtime.get("port") or config.get("service_port") or 8080),
        "health_path": target.get("health_path") or runtime.get("health_path") or config.get("health_path") or "/health",
        "service": target.get("service") or runtime.get("service") or preset,
        "docker_image": runtime.get("docker_image") or config.get("docker_image") or "",
        "model_id": runtime.get("model_id") or config.get("model_id") or "",
        "ssh_username": config.get("ssh_username") or "ubuntu",
        "ssh_private_key_path": os.path.expanduser(os.path.expandvars(config.get("ssh_private_key_path") or "")),
    }


def _write_lambda_health(payload: Dict[str, Any]) -> Dict[str, Any]:
    _write_json(LAMBDA_HEALTH_PATH, payload)
    return payload


def lambda_health_response() -> Dict[str, Any]:
    payload = _safe_json(LAMBDA_HEALTH_PATH, {})
    if not isinstance(payload, dict):
        payload = {}
    try:
        target = _load_lambda_target(str(payload.get("preset") or "image-server-v13"))
    except KeyError:
        target = {"preset": "image-server-v13"}
    return {
        "ok": True,
        "path": str(LAMBDA_HEALTH_PATH.relative_to(ROOT)) if LAMBDA_HEALTH_PATH.exists() else None,
        "target": target,
        "latest": payload if payload else None,
    }


def _write_lambda_instance_status(payload: Dict[str, Any]) -> Dict[str, Any]:
    _write_json(LAMBDA_INSTANCE_STATUS_PATH, payload)
    return payload


def _clear_local_lambda_deployment(preset: str, target: Dict[str, Any], reason: str) -> None:
    instances = _safe_json(INSTANCE_PATH, {})
    if isinstance(instances, dict):
        instances.pop(preset, None)
        _write_json(INSTANCE_PATH, instances)

    runtime = _safe_json(RUNTIME_STATE_PATH, {"version": 1, "fleet": {}, "executionHistory": []})
    if isinstance(runtime, dict):
        fleet = runtime.get("fleet", {})
        if isinstance(fleet, dict):
            for key, value in list(fleet.items()):
                if key == target.get("instance_id") or key == preset or (
                    isinstance(value, dict) and value.get("id") in {target.get("instance_id"), preset}
                ):
                    if not isinstance(value, dict):
                        value = {}
                    value["status"] = "destroyed"
                    value["updatedAt"] = _utc_now()
                    fleet[key] = value
        runtime.setdefault("executionHistory", [])
        if isinstance(runtime["executionHistory"], list):
            runtime["executionHistory"].append(
                {
                    "storedAt": _utc_now(),
                    "workload": {"id": preset, "name": preset, "type": "image_generation"},
                    "providerType": "lambda",
                    "routeReason": reason,
                    "action": {
                        "commands": ["POST /instance-operations/terminate"],
                        "notes": [reason],
                        "instance": {
                            "id": target.get("instance_id", ""),
                            "name": preset,
                            "providerType": "lambda",
                            "status": "destroyed",
                            "service": "image-server",
                            "updatedAt": _utc_now(),
                        },
                    },
                }
            )
        _write_json(RUNTIME_STATE_PATH, runtime)


def lambda_instance_status_response() -> Dict[str, Any]:
    payload = _safe_json(LAMBDA_INSTANCE_STATUS_PATH, {})
    if not isinstance(payload, dict):
        payload = {}
    try:
        target = _load_lambda_target(str(payload.get("preset") or "image-server-v13"))
    except KeyError:
        target = {"preset": "image-server-v13"}
    return {
        "ok": True,
        "path": str(LAMBDA_INSTANCE_STATUS_PATH.relative_to(ROOT)) if LAMBDA_INSTANCE_STATUS_PATH.exists() else None,
        "target": target,
        "latest": payload if payload else None,
    }


def poll_lambda_instance_status(preset: str = "image-server-v13") -> Dict[str, Any]:
    try:
        target = _load_lambda_target(preset)
    except KeyError:
        payload = {
            "ok": False,
            "checked_at": _utc_now(),
            "preset": preset,
            "running": False,
            "error": f"No deployment record found for {preset}.",
        }
        return _write_lambda_instance_status(payload)

    config = load_lambda_config()
    api_key = config.get("api_key", "").strip()
    if not api_key:
        payload = {
            "ok": False,
            "checked_at": _utc_now(),
            "preset": preset,
            "target": target,
            "running": False,
            "error": "Missing Lambda API key. Save a valid key to poll or cancel the cloud instance.",
        }
        return _write_lambda_instance_status(payload)

    try:
        instance = LambdaClient(api_key=api_key, region=config.get("region", "us-east-1"), timeout=12).get_instance(target["instance_id"])
        status = (instance.status or "unknown").lower()
        running = status in {"active", "running", "booting", "unhealthy"}
        payload = {
            "ok": True,
            "checked_at": _utc_now(),
            "preset": preset,
            "target": target,
            "instance": {"id": instance.id, "ip": instance.ip, "status": instance.status},
            "running": running,
            "status": instance.status,
        }
        return _write_lambda_instance_status(payload)
    except LambdaAPIError as exc:
        missing = exc.status == 404
        payload = {
            "ok": False,
            "checked_at": _utc_now(),
            "preset": preset,
            "target": target,
            "running": False,
            "missing": missing,
            "error": str(exc),
        }
        return _write_lambda_instance_status(payload)


def cleanup_stale_lambda_instance(preset: str = "image-server-v13") -> Dict[str, Any]:
    status = poll_lambda_instance_status(preset)
    latest_status = str(status.get("status") or status.get("instance", {}).get("status") or "").lower()
    missing = bool(status.get("missing"))
    if status.get("running") and latest_status not in {"terminated", "deleted", "destroyed"}:
        return {
            "ok": False,
            "cleaned": False,
            "preset": preset,
            "status": status,
            "error": "Lambda reports this instance is still running. Use Cancel & Delete Instance instead.",
        }

    target = status.get("target") if isinstance(status.get("target"), dict) else None
    if not target:
        try:
            target = _load_lambda_target(preset)
        except KeyError:
            return {"ok": True, "cleaned": False, "preset": preset, "message": "No local deployment record found."}

    reason = "Cleared stale local deployment state after Lambda reported the instance was terminated or missing."
    if missing:
        reason = "Cleared stale local deployment state after Lambda reported the instance was missing."
    _clear_local_lambda_deployment(preset, target, reason)
    _write_lambda_instance_status({**status, "running": False, "cleaned": True, "message": reason})
    LOG_PATH.open("a", encoding="utf-8").write(
        f"[UI] Cleared stale Lambda deployment record for {preset} at {_utc_now()}\n"
    )
    return {"ok": True, "cleaned": True, "preset": preset, "status": status, "message": reason}


def check_lambda_health(preset: str = "image-server-v13", timeout: int = 8) -> Dict[str, Any]:
    try:
        target = _load_lambda_target(preset)
    except KeyError:
        payload = {
            "ok": False,
            "healthy": False,
            "checked_at": _utc_now(),
            "preset": preset,
            "error": f"No deployment record found for {preset}.",
        }
        return _write_lambda_health(payload)

    url = f"http://{target['ip']}:{target['port']}{target['health_path']}"
    started = datetime.now(timezone.utc)
    try:
        req = request.Request(url)
        with request.urlopen(req, timeout=timeout) as response:
            body = response.read().decode(errors="ignore")
            latency_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
            payload = {
                "ok": True,
                "healthy": 200 <= response.status < 300,
                "checked_at": _utc_now(),
                "preset": preset,
                "url": url,
                "status_code": response.status,
                "latency_ms": latency_ms,
                "body": body[:1200],
                "target": target,
            }
            return _write_lambda_health(payload)
    except Exception as exc:
        remote = _check_lambda_health_over_ssh(target, timeout=timeout)
        if remote.get("healthy"):
            payload = {
                "ok": False,
                "healthy": False,
                "remote_healthy": True,
                "checked_at": _utc_now(),
                "preset": preset,
                "url": url,
                "error": str(exc),
                "target": target,
                "diagnosis": "lambda_firewall_ingress_blocked",
                "message": (
                    "The service is healthy on the Lambda instance, but the public "
                    "health URL is not reachable. Lambda firewall rules likely only "
                    f"allow SSH/22; open TCP/{target['port']} or use the SSH tunnel command."
                ),
                "ssh_check": remote,
                "ssh_tunnel_command": _ssh_tunnel_command(target),
            }
            return _write_lambda_health(payload)
        payload = {
            "ok": False,
            "healthy": False,
            "remote_healthy": False,
            "checked_at": _utc_now(),
            "preset": preset,
            "url": url,
            "error": str(exc),
            "target": target,
            "ssh_check": remote,
        }
        return _write_lambda_health(payload)


def _ssh_lambda(target: Dict[str, Any], command: str, timeout: int = 40) -> Dict[str, Any]:
    key_path = target.get("ssh_private_key_path", "")
    if not key_path:
        return {"ok": False, "returncode": 255, "stdout": "", "stderr": "Missing SSH private key path."}
    ssh_cmd = [
        "ssh",
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "UserKnownHostsFile=/dev/null",
        "-o",
        "ConnectTimeout=8",
        "-i",
        key_path,
        f"{target.get('ssh_username', 'ubuntu')}@{target.get('ip')}",
        command,
    ]
    try:
        process = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=timeout)
        return {
            "ok": process.returncode == 0,
            "returncode": process.returncode,
            "stdout": process.stdout[-6000:],
            "stderr": process.stderr[-6000:],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "returncode": 124,
            "stdout": (exc.stdout or "")[-6000:] if isinstance(exc.stdout, str) else "",
            "stderr": "SSH command timed out.",
        }
    except OSError as exc:
        return {"ok": False, "returncode": 255, "stdout": "", "stderr": str(exc)}


def _ssh_tunnel_command(target: Dict[str, Any]) -> str:
    local_port = int(target.get("port") or 8080)
    remote_port = int(target.get("port") or 8080)
    key_path = target.get("ssh_private_key_path") or "~/.ssh/intelligensi_lambda"
    user = target.get("ssh_username") or "ubuntu"
    ip = target.get("ip") or "INSTANCE_IP"
    return (
        f"ssh -i {shlex.quote(key_path)} -L {local_port}:127.0.0.1:{remote_port} "
        f"{shlex.quote(user)}@{shlex.quote(ip)}"
    )


def _check_lambda_health_over_ssh(target: Dict[str, Any], timeout: int = 8) -> Dict[str, Any]:
    port = int(target.get("port") or 8080)
    health_path = str(target.get("health_path") or "/health")
    if not health_path.startswith("/"):
        health_path = "/" + health_path
    local_url = f"http://127.0.0.1:{port}{health_path}"
    command = (
        f"curl -fsS --max-time {int(timeout)} {shlex.quote(local_url)}; "
        "echo; "
        "sudo docker ps -a --filter name=image-server --format "
        "'{{.Names}} {{.Status}} {{.Ports}}'"
    )
    result = _ssh_lambda(target, command, timeout=max(timeout + 12, 24))
    stdout = result.get("stdout", "")
    stderr = result.get("stderr", "")
    normalized_stdout = stdout.replace(" ", "").lower()
    return {
        "ok": result.get("ok", False),
        "healthy": result.get("ok", False) and (
            '"status":"ok"' in normalized_stdout
            or '"status":"ready"' in normalized_stdout
        ),
        "url": local_url,
        "stdout": stdout[-4000:],
        "stderr": stderr[-4000:],
        "returncode": result.get("returncode"),
    }


def _record_health_repair(health: Dict[str, Any], action: Dict[str, Any], result: str) -> Dict[str, Any]:
    repair_state = load_repair_state()
    repairs = repair_state.get("repairs")
    if not isinstance(repairs, list):
        repairs = []
        repair_state["repairs"] = repairs
    error_text = health.get("error") or f"Health check failed for {health.get('url', 'Lambda service')}"
    record = build_repair_record([error_text, action.get("stdout", ""), action.get("stderr", "")], error_text, retry_number=0, retry_limit=1)
    record["stored_at"] = _utc_now()
    record["result"] = result
    record["health_url"] = health.get("url")
    record["remote_action"] = action
    repairs.append(record)
    repair_state["latest"] = record
    _write_json(REPAIR_STATE_PATH, repair_state)
    return record


def heal_lambda_health(preset: str = "image-server-v13") -> Dict[str, Any]:
    before = check_lambda_health(preset=preset, timeout=8)
    if before.get("healthy"):
        return {"ok": True, "healed": False, "message": "Service is already healthy.", "before": before, "after": before}
    if before.get("remote_healthy") and before.get("diagnosis") == "lambda_firewall_ingress_blocked":
        return {
            "ok": False,
            "healed": False,
            "message": before.get("message"),
            "diagnosis": before.get("diagnosis"),
            "ssh_tunnel_command": before.get("ssh_tunnel_command"),
            "before": before,
            "after": before,
        }

    target = before.get("target") or _load_lambda_target(preset)
    remote_command = (
        "set -o pipefail; "
        "echo '[heal] docker ps before'; sudo docker ps -a --filter name=image-server; "
        "echo '[heal] recent logs'; sudo docker logs --tail 80 image-server 2>&1 || true; "
        "echo '[heal] restart image-server'; "
        "sudo docker restart image-server || sudo docker start image-server || true; "
        "sleep 8; "
        "echo '[heal] docker ps after'; sudo docker ps -a --filter name=image-server; "
        "echo '[heal] local container health'; curl -fsS --max-time 8 http://127.0.0.1:8080/health"
    )
    action = _ssh_lambda(target, remote_command, timeout=70)
    after = check_lambda_health(preset=preset, timeout=12)
    result = "healed" if after.get("healthy") else "manual_required"
    repair = _record_health_repair(before, action, result)
    payload = {
        "ok": after.get("healthy", False),
        "healed": after.get("healthy", False),
        "before": before,
        "after": after,
        "remote_action": action,
        "repair": repair,
    }
    _write_lambda_health({**after, "last_heal": payload})
    return payload


def cancel_lambda_instance(preset: str = "image-server-v13") -> Dict[str, Any]:
    try:
        target = _load_lambda_target(preset)
    except KeyError:
        return {
            "ok": False,
            "cancelled": False,
            "preset": preset,
            "error": f"No deployment record found for {preset}.",
        }

    config = load_lambda_config()
    api_key = config.get("api_key", "").strip()
    if not api_key:
        return {
            "ok": False,
            "cancelled": False,
            "preset": preset,
            "target": target,
            "error": "Missing Lambda API key. Save a valid key before cancelling the cloud instance.",
        }

    reason = "Operator cancelled the active Lambda instance from the dashboard."
    already_missing = False
    try:
        LambdaClient(api_key=api_key, region=config.get("region", "us-east-1"), timeout=20).delete_instance(target["instance_id"])
    except LambdaAPIError as exc:
        if exc.status == 404:
            already_missing = True
            reason = "Lambda API reported the instance was already missing; local state was cleared."
        else:
            return {
                "ok": False,
                "cancelled": False,
                "preset": preset,
                "target": target,
                "error": str(exc),
            }

    _clear_local_lambda_deployment(preset, target, reason)

    _write_lambda_health(
        {
            "ok": True,
            "healthy": False,
            "checked_at": _utc_now(),
            "preset": preset,
            "target": target,
            "cancelled": True,
            "message": reason,
        }
    )
    LOG_PATH.open("a", encoding="utf-8").write(
        f"[UI] Cancelled Lambda instance {target['instance_id']} for {preset} at {_utc_now()}\n"
    )
    _write_lambda_instance_status(
        {
            "ok": True,
            "checked_at": _utc_now(),
            "preset": preset,
            "target": target,
            "running": False,
            "status": "missing" if already_missing else "delete_requested",
            "cancelled": True,
            "message": reason,
        }
    )
    return {"ok": True, "cancelled": True, "already_missing": already_missing, "preset": preset, "target": target}


PREVIEW_RESOLUTIONS = [
    {"label": "256 square", "width": 256, "height": 256},
    {"label": "512 square", "width": 512, "height": 512},
    {"label": "768 square", "width": 768, "height": 768},
    {"label": "1024 square", "width": 1024, "height": 1024},
    {"label": "HD 16:9 safe", "width": 1280, "height": 704},
    {"label": "Full HD 16:9 safe", "width": 1920, "height": 1056},
    {"label": "2K QHD safe", "width": 2560, "height": 1440},
    {"label": "4K UHD safe", "width": 3840, "height": 2144},
]


def _detect_preview_inference(model_id: str, docker_image: str, requested: str = "auto") -> str:
    requested = (requested or "auto").strip().lower()
    if requested in {"image", "video"}:
        return requested
    text = f"{model_id} {docker_image}".lower()
    if any(needle in text for needle in ("ltx", "video", "wan", "hunyuan")):
        return "video"
    return "image"


def _model_from_preset_env(env: Dict[str, str]) -> str:
    value = env.get("LTX_MODEL_ID") or env.get("MODEL_ID") or env.get("model_id") or ""
    if value.startswith("${") and value.endswith("}"):
        env_name = value[2:-1]
        return os.getenv(env_name, "Lightricks/LTX-Video" if env_name == "LTX_MODEL_ID" else "")
    return value


def service_profiles_response() -> Dict[str, Any]:
    profiles: List[Dict[str, Any]] = []
    presets = []
    for preset_file in sorted(PRESET_DIR.glob("*.yaml")):
        try:
            presets.append(load_preset(PRESET_DIR, preset_file.stem))
        except PresetValidationError:
            continue

    for preset in presets:
        if not preset.docker_image:
            continue
        model_id = _model_from_preset_env(preset.env)
        profiles.append(
            {
                "id": preset.name,
                "name": preset.service or preset.name,
                "preset": preset.name,
                "provider": preset.provider or "lambda",
                "service": preset.service or preset.name,
                "docker_image": preset.docker_image,
                "model_id": model_id,
                "port": preset.port,
                "health_path": preset.health_path,
                "inference": _detect_preview_inference(model_id, preset.docker_image),
            }
        )

    seen: set[str] = set()
    unique_profiles = []
    for profile in profiles:
        key = profile["id"]
        if key in seen:
            continue
        seen.add(key)
        unique_profiles.append(profile)
    return {"ok": True, "profiles": unique_profiles}


def _profile_by_id(profile_id: str) -> Optional[Dict[str, Any]]:
    for profile in service_profiles_response().get("profiles", []):
        if isinstance(profile, dict) and profile.get("id") == profile_id:
            return profile
    return None


def _preset_runtime_profile(preset_name: str) -> Dict[str, Any]:
    try:
        preset = load_preset(PRESET_DIR, preset_name)
    except PresetValidationError:
        return {}
    model_id = _model_from_preset_env(preset.env)
    return {
        "preset": preset.name,
        "provider": preset.provider or "",
        "service": preset.service or preset.name,
        "docker_image": preset.docker_image,
        "model_id": model_id,
        "port": preset.port,
        "health_path": preset.health_path,
        "inference": _detect_preview_inference(model_id, preset.docker_image),
    }


def inference_preview_config() -> Dict[str, Any]:
    config = load_lambda_config()
    profiles = service_profiles_response().get("profiles", [])
    selected = next(
        (
            profile
            for profile in profiles
            if isinstance(profile, dict)
            and profile.get("docker_image") == config.get("docker_image")
        ),
        None,
    )
    selected_model_id = selected.get("model_id") if isinstance(selected, dict) else config.get("model_id", "")
    selected_docker_image = selected.get("docker_image") if isinstance(selected, dict) else config.get("docker_image", "")
    inference = _detect_preview_inference(selected_model_id or "", selected_docker_image or "")
    return {
        "ok": True,
        "detected_inference": inference,
        "model_id": selected_model_id or "",
        "docker_image": selected_docker_image or "",
        "selected_profile_id": selected.get("id") if isinstance(selected, dict) else "",
        "profiles": profiles,
        "resolutions": PREVIEW_RESOLUTIONS,
        "limits": {
            "image": {"max_width": 4096, "max_height": 4096, "note": "Large Flux renders can be slow or run out of VRAM."},
            "video": {
                "max_width": 3840,
                "max_height": 2160,
                "max_frames": 100000,
                "max_inference_steps": 12,
                "note": "LTX preview accepts long durations, but A10 generation may fail with CUDA out-of-memory or timeouts at high resolution/duration.",
            },
        },
    }


def preview_history_response() -> Dict[str, Any]:
    payload = _safe_json(PREVIEW_HISTORY_PATH, {"version": 1, "items": []})
    if not isinstance(payload, dict):
        payload = {"version": 1, "items": []}
    items = payload.get("items")
    if not isinstance(items, list):
        items = []
    return {"ok": True, "items": items[:50], "path": str(PREVIEW_HISTORY_PATH.relative_to(ROOT))}


def _slug_from_prompt(prompt: str) -> str:
    words = re.findall(r"[a-z0-9]+", prompt.lower())[:6]
    return "_".join(words) or "preview"


def _record_preview_history(item: Dict[str, Any]) -> None:
    payload = _safe_json(PREVIEW_HISTORY_PATH, {"version": 1, "items": []})
    if not isinstance(payload, dict):
        payload = {"version": 1, "items": []}
    items = payload.get("items")
    if not isinstance(items, list):
        items = []
        payload["items"] = items
    items.insert(0, item)
    del items[100:]
    _write_json(PREVIEW_HISTORY_PATH, payload)


def _int_from_payload(payload: Dict[str, Any], key: str, default: int) -> int:
    try:
        return int(payload.get(key, default))
    except (TypeError, ValueError):
        return default


def _ltx_frame_count(seconds: int, fps: int, requested_frames: int) -> int:
    if requested_frames > 0:
        frames = requested_frames
    else:
        frames = max(1, seconds * fps)
    if frames <= 1:
        return 1
    # LTX produces cleaner clips when frame count follows 8n + 1.
    return max(9, ((frames - 1) // 8) * 8 + 1)


def _ltx_dimension(value: int) -> int:
    return max(32, (value // 32) * 32)


def _request_json(url: str, payload: Dict[str, Any], timeout: int) -> Dict[str, Any]:
    req = request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode())


def _get_json(url: str, timeout: int) -> Dict[str, Any]:
    with request.urlopen(request.Request(url), timeout=timeout) as response:
        return json.loads(response.read().decode())


def _request_json_via_lambda(target: Dict[str, Any], path: str, payload: Dict[str, Any], timeout: int) -> Dict[str, Any]:
    port = int(target.get("port") or 8080)
    endpoint = path if path.startswith("/") else f"/{path}"
    url = f"http://127.0.0.1:{port}{endpoint}"
    code = (
        "import json,sys,urllib.request,urllib.error;"
        "url=sys.argv[1];"
        "payload=sys.argv[2].encode();"
        "req=urllib.request.Request(url,data=payload,headers={'Content-Type':'application/json'},method='POST');"
        "\ntry:\n"
        " print(urllib.request.urlopen(req,timeout=int(sys.argv[3])).read().decode())\n"
        "except urllib.error.HTTPError as e:\n"
        " body=e.read().decode(errors='ignore')\n"
        " print(body or json.dumps({'error': str(e)}))\n"
        " sys.exit(2)\n"
    )
    command = f"python3 -c {shlex.quote(code)} {shlex.quote(url)} {shlex.quote(json.dumps(payload))} {int(timeout)}"
    result = _ssh_lambda(target, command, timeout=timeout + 20)
    stdout = result.get("stdout") or "{}"
    if not result.get("ok"):
        try:
            error_payload = json.loads(stdout)
        except json.JSONDecodeError:
            error_payload = {}
        message = error_payload.get("error") if isinstance(error_payload, dict) else ""
        raise RuntimeError(message or result.get("stderr") or stdout or "Remote preview request failed.")
    return json.loads(stdout)


def _get_json_via_lambda(target: Dict[str, Any], path: str, timeout: int) -> Dict[str, Any]:
    port = int(target.get("port") or 8080)
    endpoint = path if path.startswith("/") else f"/{path}"
    url = f"http://127.0.0.1:{port}{endpoint}"
    code = (
        "import json,sys,urllib.request;"
        "print(urllib.request.urlopen(sys.argv[1],timeout=int(sys.argv[2])).read().decode())"
    )
    command = f"python3 -c {shlex.quote(code)} {shlex.quote(url)} {int(timeout)}"
    result = _ssh_lambda(target, command, timeout=timeout + 20)
    if not result.get("ok"):
        raise RuntimeError(result.get("stderr") or result.get("stdout") or "Remote preview poll failed.")
    return json.loads(result.get("stdout") or "{}")


def _preview_filename(prefix: str, extension: str, prompt: str = "") -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    slug = _slug_from_prompt(prompt)
    return f"{prefix}_{slug}_{stamp}_{uuid.uuid4().hex[:8]}.{extension}"


def _run_preview_image(prompt: str, width: int, height: int, target: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    import base64

    if width > 4096 or height > 4096:
        raise ValueError("Image preview currently supports up to 4096 pixels per side.")
    request_payload = {"prompt": prompt, "width": width, "height": height}
    if target:
        payload = _request_json_via_lambda(target, "/generate", request_payload, timeout=900)
    else:
        payload = _request_json(
            "http://127.0.0.1:8080/generate",
            request_payload,
            timeout=900,
        )
    encoded = payload.get("image_base64")
    if not isinstance(encoded, str) or not encoded:
        raise ValueError("Image server did not return image_base64.")
    PREVIEW_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    filename = _preview_filename("preview_image", "png", prompt)
    output_path = PREVIEW_IMAGE_DIR / filename
    output_path.write_bytes(base64.b64decode(encoded))
    return {
        "ok": True,
        "inference": "image",
        "path": str(output_path.relative_to(ROOT)),
        "url": f"/images/{filename}",
        "width": width,
        "height": height,
    }


def _copy_ltx_output(job_id: str, output_path: str, prompt: str) -> Path:
    target = _load_lambda_target("ltx-worker-lambda")
    remote_tmp = f"/tmp/{job_id}.mp4"
    copy_command = (
        f"sudo docker cp ltx-worker:{shlex.quote(output_path)} {shlex.quote(remote_tmp)} "
        f"&& sudo chown ubuntu:ubuntu {shlex.quote(remote_tmp)}"
    )
    action = _ssh_lambda(target, copy_command, timeout=120)
    if not action.get("ok"):
        raise RuntimeError(action.get("stderr") or action.get("stdout") or "Remote docker cp failed.")
    PREVIEW_VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    filename = _preview_filename("preview_video", "mp4", prompt)
    local_path = PREVIEW_VIDEO_DIR / filename
    subprocess.run(
        [
            "scp",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "UserKnownHostsFile=/dev/null",
            "-i",
            target["ssh_private_key_path"],
            f"{target['ssh_username']}@{target['ip']}:{remote_tmp}",
            str(local_path),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=180,
    )
    return local_path


def _run_preview_video(
    prompt: str,
    width: int,
    height: int,
    frames: int,
    steps: int,
    guidance: float,
    fps: int,
    target: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if width > 3840 or height > 2160:
        raise ValueError("Current LTX Lambda profile is capped at 4K UHD, 3840x2160.")
    if steps > 12:
        raise ValueError("Current LTX Lambda profile is capped at 12 inference steps.")
    request_payload = {
        "prompt": prompt,
        "width": width,
        "height": height,
        "num_frames": frames,
        "num_inference_steps": steps,
        "guidance_scale": guidance,
        "fps": fps,
    }
    job = _request_json_via_lambda(target, "/", request_payload, timeout=60) if target else _request_json(
        "http://127.0.0.1:8000/",
        request_payload,
        timeout=60,
    )
    job_id = str(job.get("id", ""))
    if not job_id:
        raise ValueError("LTX worker did not return a job id.")
    latest = job
    for _ in range(180):
        latest = _get_json_via_lambda(target, f"/jobs/{job_id}", timeout=30) if target else _get_json(
            f"http://127.0.0.1:8000/jobs/{job_id}",
            timeout=30,
        )
        status = latest.get("status")
        if status == "completed":
            output_path = str(latest.get("output") or f"/app/outputs/{job_id}.mp4")
            local_path = _copy_ltx_output(job_id, output_path, prompt)
            return {
                "ok": True,
                "inference": "video",
                "job": latest,
                "path": str(local_path.relative_to(ROOT)),
                "url": f"/videos/{local_path.name}",
                "width": width,
                "height": height,
                "frames": frames,
                "seconds": round(frames / fps, 2) if fps else None,
                "steps": steps,
            }
        if status == "error":
            raise RuntimeError(str(latest.get("error") or "LTX job failed."))
        time.sleep(5)
    raise TimeoutError(f"LTX job {job_id} did not complete within the preview timeout.")


def run_inference_preview(payload: Dict[str, Any]) -> Dict[str, Any]:
    config = load_lambda_config()
    started = time.time()
    prompt = str(payload.get("prompt") or "").strip()
    if not prompt:
        raise ValueError("Prompt is required.")
    width = _int_from_payload(payload, "width", 768)
    height = _int_from_payload(payload, "height", 768)
    profile = _profile_by_id(str(payload.get("profile_id") or ""))
    model_id = str((profile or {}).get("model_id") or payload.get("model_id") or config.get("model_id", ""))
    docker_image = str((profile or {}).get("docker_image") or payload.get("docker_image") or config.get("docker_image", ""))
    preview_target = None
    if isinstance(profile, dict) and profile.get("provider") == "lambda":
        try:
            preview_target = _load_lambda_target(str(profile.get("preset") or profile.get("id") or ""))
        except KeyError:
            preview_target = None
    inference = _detect_preview_inference(
        model_id,
        docker_image,
        str(payload.get("inference") or "auto"),
    )
    if inference == "image":
        result = _run_preview_image(prompt, width, height, preview_target)
        fps = None
    else:
        width = _ltx_dimension(width)
        height = _ltx_dimension(height)
        steps = _int_from_payload(payload, "num_inference_steps", 8)
        fps = _int_from_payload(payload, "fps", 24)
        seconds = _int_from_payload(payload, "duration_seconds", 1)
        requested_frames = _int_from_payload(payload, "num_frames", 0)
        frames = _ltx_frame_count(seconds, fps, requested_frames)
        try:
            guidance = float(payload.get("guidance_scale", 3.5))
        except (TypeError, ValueError):
            guidance = 3.5
        result = _run_preview_video(prompt, width, height, frames, steps, guidance, fps, preview_target)

    render_seconds = round(time.time() - started, 2)
    history_item = {
        "id": uuid.uuid4().hex,
        "created_at": _utc_now(),
        "name": _slug_from_prompt(prompt).replace("_", " ").title(),
        "prompt": prompt,
        "inference": result.get("inference"),
        "profile_id": (profile or {}).get("id", ""),
        "service": (profile or {}).get("service", ""),
        "model_id": model_id,
        "docker_image": docker_image,
        "width": result.get("width", width),
        "height": result.get("height", height),
        "frames": result.get("frames"),
        "seconds": result.get("seconds"),
        "fps": fps,
        "steps": result.get("steps"),
        "render_seconds": render_seconds,
        "path": result.get("path"),
        "url": result.get("url"),
    }
    _record_preview_history(history_item)
    result["history_item"] = history_item
    result["render_seconds"] = render_seconds
    return result


def _empty_nebius_config() -> Dict[str, str]:
    return {
        "project_id": "",
        "api_token": "",
        "ssh_public_key_path": "",
        "ssh_private_key_path": "",
        "ssh_username": "ubuntu",
        "public_ip": "",
        "instance_name": "intelligensi-comfyui",
        "gpu_shape": "gpu-standard-1",
        "disk_size_gb": "400",
        "region": "eu-north1",
        "zone": "eu-north1-a",
    }


def load_nebius_config() -> Dict[str, str]:
    config = _empty_nebius_config()
    public_data = _safe_json(NEBIUS_CONFIG_PATH, {})
    secret_data = _safe_json(NEBIUS_SECRET_PATH, {})

    if isinstance(public_data, dict):
        for key, value in public_data.items():
            if key in config and value is not None:
                config[key] = str(value)
    if isinstance(secret_data, dict):
        for key, value in secret_data.items():
            if key in config and value is not None:
                config[key] = str(value)
    return config


def _mask_secret_config(config: Dict[str, str]) -> Dict[str, str]:
    masked = config.copy()
    if masked.get("api_token"):
        masked["api_token"] = ""
    if masked.get("ssh_private_key_path"):
        masked["ssh_private_key_path"] = ""
    return masked


def save_nebius_config(payload: Dict[str, Any]) -> Dict[str, str]:
    current = load_nebius_config()
    allowed_keys = set(current.keys())
    updated = current.copy()

    for key, value in payload.items():
        if key not in allowed_keys:
            continue
        updated[key] = str(value).strip()

    public_fields = {
        "project_id",
        "ssh_public_key_path",
        "ssh_username",
        "public_ip",
        "instance_name",
        "gpu_shape",
        "disk_size_gb",
        "region",
        "zone",
    }
    secret_fields = {"api_token", "ssh_private_key_path"}

    _write_json(NEBIUS_CONFIG_PATH, {key: updated[key] for key in public_fields})
    _write_json(NEBIUS_SECRET_PATH, {key: updated[key] for key in secret_fields})
    return updated


def _shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def build_nebius_export_block(config: Dict[str, str]) -> str:
    ordered_pairs = [
        ("NEBIUS_PROJECT_ID", config.get("project_id", "")),
        ("NEBIUS_API_TOKEN", config.get("api_token", "")),
        ("NEBIUS_SSH_PUBLIC_KEY_PATH", config.get("ssh_public_key_path", "")),
        ("NEBIUS_SSH_PRIVATE_KEY_PATH", config.get("ssh_private_key_path", "")),
        ("NEBIUS_SSH_USERNAME", config.get("ssh_username", "")),
        ("NEBIUS_PUBLIC_IP", config.get("public_ip", "")),
        ("NEBIUS_INSTANCE_NAME", config.get("instance_name", "")),
        ("NEBIUS_GPU_SHAPE", config.get("gpu_shape", "")),
        ("NEBIUS_DISK_SIZE_GB", config.get("disk_size_gb", "")),
        ("NEBIUS_REGION", config.get("region", "")),
        ("NEBIUS_ZONE", config.get("zone", "")),
    ]
    return "\n".join(f"export {key}={_shell_quote(value)}" for key, value in ordered_pairs)


def build_nebius_commands(config: Dict[str, str]) -> List[str]:
    return [
        build_nebius_export_block(config),
        "./scripts/provision_nebius_gpu.sh",
        "./scripts/deploy_comfyui_service.sh dev",
        "./scripts/health_check_comfyui.sh",
    ]


def build_nebius_service_url(config: Dict[str, str]) -> str:
    public_ip = config.get("public_ip", "").strip()
    return f"http://{public_ip}:8188" if public_ip else ""


def _collect_issue_hints(history: List[Dict[str, Any]], logs: List[str], instances: Dict[str, Dict[str, Any]]) -> List[str]:
    issues: List[str] = []

    current_state = history[-1]["to_state"] if history else "idle"
    if current_state == "error":
        issues.append("Deployment entered error state")

    if not LOG_PATH.exists():
        issues.append("Deployment log file missing")

    if not STATE_PATH.exists():
        issues.append("State machine file missing")

    lowered_logs = "\n".join(logs).lower()
    if "unauthorized" in lowered_logs or "denied" in lowered_logs:
        issues.append("Registry or API authorization failed")
    if "hf_token" in lowered_logs or "gatedrepoerror" in lowered_logs:
        issues.append("Hugging Face token missing or gated model access failed")
    if "ghcr" in lowered_logs and "unauthorized" in lowered_logs:
        issues.append("GHCR authentication failed")
    if "ssh failed" in lowered_logs or "connection timed out" in lowered_logs:
        issues.append("SSH connection failed")
    if "docker build failed" in lowered_logs:
        issues.append("Docker build failed")
    if "docker pull" in lowered_logs and "not found" in lowered_logs:
        issues.append("Docker image not found")
    if "terraform" in lowered_logs and "error" in lowered_logs:
        issues.append("Terraform apply failed")
    if "nebius_ip missing" in lowered_logs or "missing nebius provider config" in lowered_logs:
        issues.append("Nebius provider host config missing: set NEBIUS_IP in provider.nebius.env")
    if "missing env file" in lowered_logs and "lambda config panel" in lowered_logs:
        issues.append("Missing env file: use the Lambda Config panel for the current Lambda flow")

    restricted = [name for name, state in instances.items() if state.get("ingress_status") == "restricted"]
    if restricted:
        issues.append(f"Ingress is restricted for {', '.join(restricted[:3])}")

    unknown_container = [name for name, state in instances.items() if state.get("container_status") == "unknown"]
    if unknown_container:
        issues.append(f"Container status unknown for {', '.join(unknown_container[:3])}")

    return issues


def _derive_fix_suggestions(issues: List[str], logs: List[str]) -> List[Dict[str, str]]:
    suggestions: List[Dict[str, str]] = []

    if issues:
        for suggestion in suggest_fixes("deployment", issues):
            suggestions.append({"source": "heuristic", "text": suggestion})

    lowered_logs = "\n".join(logs).lower()
    targeted_fixes = [
        ("ghcr authentication failed", "Run Docker login for `ghcr.io` on the remote GPU node before pulling."),
        ("hugging face token missing or gated model access failed", "Export `HF_TOKEN` locally and inject it into the container runtime env."),
        ("ssh connection failed", "Wait for the instance to finish booting, then retry SSH with the configured private key."),
        ("docker image not found", "Verify the preset `docker_image` tag exists in the registry before deployment."),
        ("terraform apply failed", "Inspect Terraform stderr first; most failures here are quota, API key, or variable issues."),
    ]
    for needle, text in targeted_fixes:
        if any(needle in issue.lower() for issue in issues):
            suggestions.append({"source": "targeted", "text": text})

    if "restricted" in lowered_logs:
        suggestions.append(
            {
                "source": "targeted",
                "text": "Expose the service through a tunnel or add ingress configuration before relying on health checks.",
            }
        )

    deduped: List[Dict[str, str]] = []
    seen: set[str] = set()
    for item in suggestions:
        if item["text"] in seen:
            continue
        seen.add(item["text"])
        deduped.append(item)
    return deduped


@dataclass
class DashboardSnapshot:
    current_state: str
    history: List[Dict[str, Any]]
    deployments: Dict[str, Dict[str, Any]]
    tracked_deployment_count: int
    suggested_fix_count: int
    presets: List[Dict[str, Any]]
    issues: List[str]
    suggestions: List[Dict[str, str]]
    log_path: Optional[str]
    state_path: Optional[str]
    nebius_config_present: bool
    runtime_state_path: Optional[str]


def build_snapshot(log_limit: int = 200) -> DashboardSnapshot:
    state_blob = _safe_json(STATE_PATH, {})
    history = state_blob.get("history", []) if isinstance(state_blob, dict) else []
    deployments = _safe_json(INSTANCE_PATH, {})
    runtime_blob = _safe_json(RUNTIME_STATE_PATH, {})
    runtime_fleet = runtime_blob.get("fleet", {}) if isinstance(runtime_blob, dict) else {}
    merged_deployments = {}
    valid_presets = _preset_names()
    if isinstance(deployments, dict):
      merged_deployments.update(
          {
              name: state
              for name, state in deployments.items()
              if name in valid_presets or state.get("preset") in valid_presets
          }
      )
    if isinstance(runtime_fleet, dict):
      merged_deployments.update(runtime_fleet)
    tracked_deployment_count = len(merged_deployments) if isinstance(merged_deployments, dict) else 0
    if isinstance(runtime_blob, dict):
        try:
            tracked_deployment_count = int(runtime_blob.get("trackedDeploymentCount", tracked_deployment_count))
        except (TypeError, ValueError):
            pass
    logs = _tail_lines(LOG_PATH, log_limit)
    issues = _collect_issue_hints(history, logs, merged_deployments if isinstance(merged_deployments, dict) else {})
    suggestions = _derive_fix_suggestions(issues, logs)
    suggested_fix_count = len(suggestions)
    if isinstance(runtime_blob, dict):
        try:
            suggested_fix_count = int(runtime_blob.get("suggestedFixCount", suggested_fix_count))
        except (TypeError, ValueError):
            pass
    nebius_config = load_nebius_config()

    return DashboardSnapshot(
        current_state=state_blob.get("current_state", "idle") if isinstance(state_blob, dict) else "idle",
        history=history if isinstance(history, list) else [],
        deployments=merged_deployments if isinstance(merged_deployments, dict) else {},
        tracked_deployment_count=tracked_deployment_count,
        suggested_fix_count=suggested_fix_count,
        presets=_load_presets(),
        issues=issues,
        suggestions=suggestions,
        log_path=str(LOG_PATH.relative_to(ROOT)) if LOG_PATH.exists() else None,
        state_path=str(STATE_PATH.relative_to(ROOT)) if STATE_PATH.exists() else None,
        nebius_config_present=bool(nebius_config.get("project_id") and nebius_config.get("public_ip")),
        runtime_state_path=str(RUNTIME_STATE_PATH.relative_to(ROOT)) if RUNTIME_STATE_PATH.exists() else None,
    )


def _update_runtime_instance_status(instance_id: str, status: str) -> Dict[str, Any]:
    runtime_blob = _safe_json(RUNTIME_STATE_PATH, {"version": 1, "fleet": {}, "executionHistory": []})
    if not isinstance(runtime_blob, dict):
        runtime_blob = {"version": 1, "fleet": {}, "executionHistory": []}

    fleet = runtime_blob.get("fleet", {})
    if not isinstance(fleet, dict):
        fleet = {}
        runtime_blob["fleet"] = fleet

    if instance_id not in fleet:
        snapshot = build_snapshot()
        source = snapshot.deployments.get(instance_id)
        if not source:
            raise KeyError(instance_id)
        fleet[instance_id] = source

    fleet[instance_id]["status"] = status
    fleet[instance_id]["updatedAt"] = __import__("datetime").datetime.utcnow().isoformat() + "Z"
    _write_json(RUNTIME_STATE_PATH, runtime_blob)
    return fleet[instance_id]


class DashboardHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(UI_DIR), **kwargs)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/overview":
            snapshot = build_snapshot()
            self._send_json(asdict(snapshot))
            return

        if parsed.path == "/api/nebius-config":
            config = load_nebius_config()
            payload = {
                "config": _mask_secret_config(config),
                "commands": build_nebius_commands(config),
                "config_path": str(NEBIUS_CONFIG_PATH.relative_to(ROOT)),
                "secret_path": str(NEBIUS_SECRET_PATH.relative_to(ROOT)),
                "has_api_token": bool(config.get("api_token")),
                "has_ssh_private_key_path": bool(config.get("ssh_private_key_path")),
                "service_url": build_nebius_service_url(config),
            }
            self._send_json(payload)
            return

        if parsed.path == "/api/lambda-config":
            config = load_lambda_config()
            payload = {
                "config": _mask_lambda_config(config),
                "commands": build_lambda_commands(config),
                "config_path": str(LAMBDA_CONFIG_PATH.relative_to(ROOT)),
                "secret_path": str(LAMBDA_SECRET_PATH.relative_to(ROOT)),
                "has_api_key": bool(config.get("api_key")),
                "has_ghcr_token": bool(config.get("ghcr_token")),
                "has_hf_token": bool(config.get("hf_token")),
            }
            self._send_json(payload)
            return

        if parsed.path == "/api/lambda-availability":
            self._send_json(_lambda_availability_response())
            return

        if parsed.path == "/api/repairs":
            self._send_json(repair_state_response())
            return

        if parsed.path == "/api/lambda-health":
            self._send_json(lambda_health_response())
            return

        if parsed.path == "/api/lambda-instance/status":
            self._send_json(lambda_instance_status_response())
            return

        if parsed.path == "/api/inference-preview/config":
            self._send_json(inference_preview_config())
            return

        if parsed.path == "/api/service-profiles":
            self._send_json(service_profiles_response())
            return

        if parsed.path == "/api/inference-preview/history":
            self._send_json(preview_history_response())
            return

        if parsed.path == "/api/logs":
            query = parse_qs(parsed.query)
            limit_raw = query.get("limit", ["200"])[0]
            try:
                limit = max(10, min(1000, int(limit_raw)))
            except ValueError:
                limit = 200
            payload = {"lines": _tail_lines(LOG_PATH, limit), "path": str(LOG_PATH.relative_to(ROOT)) if LOG_PATH.exists() else None}
            self._send_json(payload)
            return

        if parsed.path in {"/", "/admin", "/admin/"}:
            self.path = "/admin_interface.html"
        return super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/nebius-config":
            body = self._read_json_body()
            config = save_nebius_config(body if isinstance(body, dict) else {})
            payload = {
                "ok": True,
                "config": _mask_secret_config(config),
                "commands": build_nebius_commands(config),
                "config_path": str(NEBIUS_CONFIG_PATH.relative_to(ROOT)),
                "secret_path": str(NEBIUS_SECRET_PATH.relative_to(ROOT)),
                "has_api_token": bool(config.get("api_token")),
                "has_ssh_private_key_path": bool(config.get("ssh_private_key_path")),
                "service_url": build_nebius_service_url(config),
            }
            self._send_json(payload)
            return

        if parsed.path in {"/api/fleet/start", "/api/fleet/stop"}:
            body = self._read_json_body()
            instance_id = body.get("instance_id") if isinstance(body, dict) else None
            if not isinstance(instance_id, str) or not instance_id.strip():
                self.send_error(HTTPStatus.BAD_REQUEST, "Missing instance_id")
                return
            target_status = "running" if parsed.path.endswith("/start") else "stopped"
            try:
                instance = _update_runtime_instance_status(instance_id, target_status)
            except KeyError:
                self.send_error(HTTPStatus.NOT_FOUND, "Unknown instance_id")
                return
            self._send_json({"ok": True, "instance": instance})
            return

        if parsed.path == "/api/preset-deploy":
            body = self._read_json_body()
            preset = body.get("preset") if isinstance(body, dict) else None
            if not isinstance(preset, str) or not preset.strip():
                self.send_error(HTTPStatus.BAD_REQUEST, "Missing preset")
                return
            try:
                payload = _start_preset_deploy(preset.strip())
            except FileNotFoundError:
                self.send_error(HTTPStatus.NOT_FOUND, "Unknown preset")
                return
            self._send_json(payload)
            return

        if parsed.path == "/api/lambda-config":
            body = self._read_json_body()
            config = save_lambda_config(body if isinstance(body, dict) else {})
            payload = {
                "ok": True,
                "config": _mask_lambda_config(config),
                "commands": build_lambda_commands(config),
                "config_path": str(LAMBDA_CONFIG_PATH.relative_to(ROOT)),
                "secret_path": str(LAMBDA_SECRET_PATH.relative_to(ROOT)),
                "has_api_key": bool(config.get("api_key")),
                "has_ghcr_token": bool(config.get("ghcr_token")),
                "has_hf_token": bool(config.get("hf_token")),
            }
            self._send_json(payload)
            return

        if parsed.path == "/api/lambda-availability/refresh":
            self._send_json(refresh_lambda_availability())
            return

        if parsed.path == "/api/lambda-availability/select":
            body = self._read_json_body()
            try:
                self._send_json(select_lambda_gpu_option(body if isinstance(body, dict) else {}))
            except ValueError as exc:
                self.send_error(HTTPStatus.BAD_REQUEST, str(exc))
            return

        if parsed.path == "/api/repairs/clear":
            _write_json(REPAIR_STATE_PATH, {"version": 1, "repairs": []})
            self._send_json(repair_state_response())
            return

        if parsed.path == "/api/repairs/analyze":
            self._send_json(analyze_latest_logs_for_repair())
            return

        if parsed.path == "/api/repairs/retry":
            body = self._read_json_body()
            preset = body.get("preset", "image-server-v13") if isinstance(body, dict) else "image-server-v13"
            try:
                payload = _start_preset_deploy(str(preset).strip() or "image-server-v13")
            except FileNotFoundError:
                self.send_error(HTTPStatus.NOT_FOUND, "Unknown preset")
                return
            self._send_json(payload)
            return

        if parsed.path == "/api/lambda-health/check":
            body = self._read_json_body()
            preset = body.get("preset", "image-server-v13") if isinstance(body, dict) else "image-server-v13"
            self._send_json(check_lambda_health(str(preset).strip() or "image-server-v13"))
            return

        if parsed.path == "/api/lambda-health/heal":
            body = self._read_json_body()
            preset = body.get("preset", "image-server-v13") if isinstance(body, dict) else "image-server-v13"
            self._send_json(heal_lambda_health(str(preset).strip() or "image-server-v13"))
            return

        if parsed.path == "/api/lambda-instance/cancel":
            body = self._read_json_body()
            preset = body.get("preset", "image-server-v13") if isinstance(body, dict) else "image-server-v13"
            self._send_json(cancel_lambda_instance(str(preset).strip() or "image-server-v13"))
            return

        if parsed.path == "/api/lambda-instance/poll":
            body = self._read_json_body()
            preset = body.get("preset", "image-server-v13") if isinstance(body, dict) else "image-server-v13"
            self._send_json(poll_lambda_instance_status(str(preset).strip() or "image-server-v13"))
            return

        if parsed.path == "/api/lambda-instance/cleanup-stale":
            body = self._read_json_body()
            preset = body.get("preset", "image-server-v13") if isinstance(body, dict) else "image-server-v13"
            self._send_json(cleanup_stale_lambda_instance(str(preset).strip() or "image-server-v13"))
            return

        if parsed.path == "/api/inference-preview/generate":
            body = self._read_json_body()
            try:
                self._send_json(run_inference_preview(body if isinstance(body, dict) else {}))
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)})
            return

        if parsed.path == "/api/logs/clear":
            LOG_PATH.write_text("", encoding="utf-8")
            self._send_json({"ok": True, "path": str(LOG_PATH.relative_to(ROOT))})
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Unknown endpoint")

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _send_json(self, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> Any:
        length_raw = self.headers.get("Content-Length", "0")
        try:
            length = int(length_raw)
        except ValueError:
            length = 0
        raw = self.rfile.read(length) if length > 0 else b"{}"
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return {}


def main() -> None:
    host = os.getenv("INTELLIGENSI_DASHBOARD_HOST", "127.0.0.1")
    port = int(os.getenv("INTELLIGENSI_DASHBOARD_PORT", "4173"))
    server = ThreadingHTTPServer((host, port), DashboardHandler)
    print(f"Dashboard available at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
