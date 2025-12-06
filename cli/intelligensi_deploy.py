"""Command-line interface for IntelligensiDeploy."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import List, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from deploy.workflow import DeploymentError, deploy_preset, shutdown_preset, status_preset
from presets.loader import PresetValidationError, load_presets


def deploy(preset: str) -> None:
    """Execute a deployment flow for a preset."""

    try:
        state = deploy_preset(preset)
        print(f"🚀 Deployed {preset} to {state.ip} (instance_id={state.instance_id})")
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
    print("Service is ready for deployment.")


def validate_agent(service: str):
    """Validate a service with agentic auto-fix suggestions."""

    from intelligensi_deploy.agent.auto_fix_suggester import suggest_fixes
    from intelligensi_deploy.validators.docker_validator import validate_dockerfile
    from intelligensi_deploy.validators.service_validator import validate_service

    service_path = os.path.join("services", service)
    print(f"\n🔍 Agentic Validation: {service}")

    errors = []
    errors.extend(validate_service(service_path))
    errors.extend(validate_dockerfile(os.path.join(service_path, "Dockerfile")))

    if not errors:
        print("\n✅ VALIDATION PASSED — No fixes required.")
        return

    print("\n❌ VALIDATION FAILED — Issues detected:")
    for e in errors:
        print(" -", e)

    print("\n🤖 Suggested Fixes:")
    fixes = suggest_fixes(errors)
    for f in fixes:
        print("   ", f)

    # Ask user if they want auto-patch generation
    choice = input("\nWould you like Codex to generate the required patches? (y/n): ").strip().lower()

    if choice == "y":
        print("\n🛠  Generating patch instructions…")
        print("Paste this into Codex:\n")
        print("-------- BEGIN PATCH INSTRUCTIONS --------")

        for e in errors:
            print(f"# Fix for: {e}")
            print("# TODO: Insert fix here. Codex will fill it based on context.")
            print()

        print("-------- END PATCH INSTRUCTIONS --------\n")
        print("⚡ Paste that into Codex and apply. Then re-run:")
        print(f"    python3 cli/intelligensi_deploy.py validate-agent {service}")
    else:
        print("\n🚫 No patches generated. Fix manually or re-run validate-agent.")


def parse_arguments(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Build the CLI argument parser."""

    parser = argparse.ArgumentParser(description="IntelligensiDeploy CLI")
    subcommands = parser.add_subparsers(dest="command", required=True)

    deploy_parser = subcommands.add_parser("deploy", help="Deploy a preset")
    deploy_parser.add_argument("preset", help="Name of the preset to deploy")

    status_parser = subcommands.add_parser("status", help="Show deployment status")
    status_parser.add_argument("preset", help="Name of the preset to query")

    shutdown_parser = subcommands.add_parser("shutdown", help="Destroy resources")
    shutdown_parser.add_argument("preset", help="Name of the preset to destroy")

    subcommands.add_parser("list-presets", help="List available presets")

    validate_parser = subcommands.add_parser("validate", help="Validate a service before deployment")
    validate_parser.add_argument("service", help="Service name to validate")

    validate_agent_parser = subcommands.add_parser(
        "validate-agent", help="Validate a service with agentic suggestions"
    )
    validate_agent_parser.add_argument("service", help="Service name to validate")

    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> None:
    """Entry point for the IntelligensiDeploy CLI."""

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


if __name__ == "__main__":
    main()

