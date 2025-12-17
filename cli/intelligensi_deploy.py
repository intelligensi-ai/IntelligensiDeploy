"""Command-line interface for IntelligensiDeploy."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import List, Optional

# ----------------------------
# Auto-load .env.local if present
# ----------------------------
env_file = Path(".env.local")
if env_file.exists():
    with env_file.open() as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key, value)

# ----------------------------
# Add repo root to Python path
# ----------------------------
repo_root = Path(__file__).parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from deploy.workflow import DeploymentError, deploy_preset, shutdown_preset, status_preset
from presets.loader import PresetValidationError, load_presets
from intelligensi_deploy.agent.auto_fix_suggester import suggest_fixes

# ----------------------------
# Helpers
# ----------------------------

def require_env(var_name: str) -> None:
    if not os.environ.get(var_name):
        raise SystemExit(f"❌ Missing required environment variable: {var_name}")

def resolve_env_vars(env: dict) -> dict:
    """
    Resolve ${VAR} references using the current process environment.
    This is CRITICAL for Docker env injection.
    """
    return {
        k: os.path.expandvars(v) if isinstance(v, str) else v
        for k, v in env.items()
    }

# ----------------------------
# Commands
# ----------------------------

def deploy(preset: str) -> None:
    """Execute a deployment flow for a preset."""

    print(f"🚧 Starting deploy for preset: {preset}")

    # 🔐 Preflight secrets
    require_env("LAMBDALABS_API_KEY")
    require_env("GHCR_TOKEN")
    require_env("HF_TOKEN")

    # 🔧 Ensure env vars are resolved before deploy engine uses them
    os.environ["INTELLIGENSI_RESOLVE_ENV"] = "1"

    try:
        state = deploy_preset(preset)

        ip = state.ip
        instance_id = state.instance_id

        port = getattr(state, "port", 8080)
        ssh_user = getattr(state, "ssh_username", "ubuntu")
        ssh_key = getattr(state, "ssh_private_key_path", "~/.ssh/intelligensi_lambda")

        print("\n🚀 Deployment successful")
        print(f"Service: {preset}")
        print(f"Instance ID: {instance_id}")
        print(f"IP: {ip}")

        print("\n🔐 SSH access:")
        print(f"ssh -i {ssh_key} {ssh_user}@{ip}")

        print("\n❤️ Health check:")
        print(f"curl http://{ip}:{port}/health\n")

    except DeploymentError as exc:
        raise SystemExit(f"Deployment failed: {exc}")

def status(preset: str) -> str:
    """Return the current deployment status."""
    try:
        return status_preset(preset)
    except DeploymentError as exc:
        return f"Status check failed: {exc}"

def shutdown(preset: str) -> None:
    """Tear down infrastructure and reset state."""
    try:
        shutdown_preset(preset)
        print(f"✅ Shutdown requested for preset '{preset}'")
    except DeploymentError as exc:
        raise SystemExit(f"Shutdown failed: {exc}")

def list_presets(presets_dir: Path) -> List[str]:
    """Return available preset identifiers."""
    return [preset.stem for preset in presets_dir.glob("*.yaml")]

def validate(service: str) -> None:
    """Validate a service before deployment."""

    from intelligensi_deploy.validators.docker_validator import validate_dockerfile
    from intelligensi_deploy.validators.service_validator import validate_service

    service_path = Path("services") / service
    print(f"Validating service: {service_path}")

    errors: List[str] = []
    errors.extend(validate_service(str(service_path)))
    errors.extend(validate_dockerfile(str(service_path / "Dockerfile")))

    if errors:
        print("\n❌ VALIDATION FAILED:")
        for error in errors:
            print(" -", error)
        raise SystemExit(1)

    print("\n✅ VALIDATION PASSED")

def validate_agent(service: str) -> None:
    """Run AI-driven validation using the auto-fix suggester."""

    print(f"Running agentic validator on service: {service}\n")

    from intelligensi_deploy.validators.docker_validator import validate_dockerfile
    from intelligensi_deploy.validators.service_validator import validate_service

    issues: List[str] = []

    service_path = os.path.join("services", service)
    issues.extend(validate_service(service_path))
    issues.extend(validate_dockerfile(os.path.join(service_path, "Dockerfile")))

    if not issues:
        print("✅ No issues found.")
        return

    print("\n❗ Issues found:")
    for issue in issues:
        print(f" - {issue}")

    print("\n🤖 Agent suggestions:")
    for fix in suggest_fixes(service, issues):
        print(f" - {fix}")

# ----------------------------
# CLI wiring
# ----------------------------

def parse_arguments(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="IntelligensiDeploy CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    d = sub.add_parser("deploy", help="Deploy a preset")
    d.add_argument("preset")

    s = sub.add_parser("status", help="Show deployment status")
    s.add_argument("preset")

    x = sub.add_parser("shutdown", help="Destroy resources")
    x.add_argument("preset")

    sub.add_parser("list-presets", help="List available presets")

    v = sub.add_parser("validate", help="Validate a service")
    v.add_argument("service")

    va = sub.add_parser("validate-agent", help="AI validation")
    va.add_argument("service")

    return parser.parse_args(argv)

def main(argv: Optional[List[str]] = None) -> None:
    args = parse_arguments(argv)

    if args.command == "deploy":
        deploy(args.preset)
    elif args.command == "status":
        print(status(args.preset))
    elif args.command == "shutdown":
        shutdown(args.preset)
    elif args.command == "list-presets":
        for preset in list_presets(Path("presets")):
            print(preset)
    elif args.command == "validate":
        validate(args.service)
    elif args.command == "validate-agent":
        validate_agent(args.service)

# ----------------------------
# Entrypoint
# ----------------------------

if __name__ == "__main__":
    main()
