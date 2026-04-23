"""Local dashboard server for IntelligensiDeploy.

Serves the admin UI plus JSON endpoints backed by the existing deployment
state, instance state, preset files, and optional logs.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
UI_DIR = ROOT / "ui"
STATE_PATH = ROOT / ".intelligensi_state.json"
INSTANCE_PATH = ROOT / ".intelligensi_instances.json"
LOG_PATH = ROOT / "deploy.log"
PRESET_DIR = ROOT / "presets"
NEBIUS_CONFIG_PATH = ROOT / ".intelligensi_nebius_config.json"
NEBIUS_SECRET_PATH = ROOT / ".intelligensi_nebius_secrets.json"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from intelligensi_deploy.agent.auto_fix_suggester import suggest_fixes


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
    presets: List[Dict[str, Any]]
    issues: List[str]
    suggestions: List[Dict[str, str]]
    log_path: Optional[str]
    state_path: Optional[str]
    nebius_config_present: bool


def build_snapshot(log_limit: int = 200) -> DashboardSnapshot:
    state_blob = _safe_json(STATE_PATH, {})
    history = state_blob.get("history", []) if isinstance(state_blob, dict) else []
    deployments = _safe_json(INSTANCE_PATH, {})
    logs = _tail_lines(LOG_PATH, log_limit)
    issues = _collect_issue_hints(history, logs, deployments if isinstance(deployments, dict) else {})
    suggestions = _derive_fix_suggestions(issues, logs)
    nebius_config = load_nebius_config()

    return DashboardSnapshot(
        current_state=state_blob.get("current_state", "idle") if isinstance(state_blob, dict) else "idle",
        history=history if isinstance(history, list) else [],
        deployments=deployments if isinstance(deployments, dict) else {},
        presets=_load_presets(),
        issues=issues,
        suggestions=suggestions,
        log_path=str(LOG_PATH.relative_to(ROOT)) if LOG_PATH.exists() else None,
        state_path=str(STATE_PATH.relative_to(ROOT)) if STATE_PATH.exists() else None,
        nebius_config_present=bool(nebius_config.get("project_id") and nebius_config.get("public_ip")),
    )


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
