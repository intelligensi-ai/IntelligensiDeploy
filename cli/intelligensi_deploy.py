"""Command-line interface for IntelligensiDeploy."""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path
from typing import List, Optional

from agent.agent_adapter import AgentAdapter
from core.state_machine import StateMachine, StateTransitionError
from intelligensi_deploy.validators.docker_validator import validate_dockerfile
from intelligensi_deploy.validators.service_validator import validate_service


def _build_state_machine() -> StateMachine:
    """Create a state machine with a simple event logger."""

    logger = logging.getLogger("intelligensi.cli")
    logger.addHandler(logging.StreamHandler())
    logger.setLevel(logging.INFO)
    return StateMachine(logger=logger)


def deploy(preset: str, terraform_dir: Path, context_path: Optional[Path]) -> None:
    """Execute a deployment flow for a preset."""

    state = _build_state_machine()
    try:
        state.transition("planning", {"preset": preset})
        state.transition("provisioning")
        state.run_terraform("init", terraform_dir)
        state.run_terraform("apply", terraform_dir, extra_args=["-auto-approve"])
        state.transition("building")
        state.build_container_image(preset=preset, context_path=context_path)
        state.transition("deploying")
        state.transition("verifying")
        state.transition("running")
    except Exception as exc:
        try:
            state.transition("error", {"reason": str(exc)})
        except StateTransitionError:
            pass
        raise


def status() -> str:
    """Return the current deployment status."""

    adapter = AgentAdapter(agent_id="cli-status")
    return adapter.get_state() or "unknown"


def logs(limit: int = 100) -> List[str]:
    """Retrieve recent deployment logs."""

    adapter = AgentAdapter(agent_id="cli-logs")
    return adapter.get_logs(limit=limit)


def shutdown(terraform_dir: Path) -> None:
    """Tear down infrastructure and reset state."""

    state = _build_state_machine()
    state.transition("shutdown")
    state.run_terraform("destroy", terraform_dir, extra_args=["-auto-approve"])
    state.reset()


def list_presets(presets_dir: Path) -> List[str]:
    """Return available preset identifiers."""

    return [preset.stem for preset in presets_dir.glob("*.yaml")]


def validate(service: str) -> None:
    """Validate a service before deployment."""

    service_path = os.path.join("services", service)

    print(f"Validating service: {service_path}")

    errors: List[str] = []
    errors.extend(validate_service(service_path))
    errors.extend(validate_dockerfile(os.path.join(service_path, "Dockerfile")))

    if errors:
        print("\n❌ VALIDATION FAILED:")
        for error in errors:
            print(" -", error)
        raise SystemExit(1)

    print("\n✅ VALIDATION PASSED")
    print("Service is ready for deployment.")


def parse_arguments(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Build the CLI argument parser."""

    parser = argparse.ArgumentParser(description="IntelligensiDeploy CLI")
    subcommands = parser.add_subparsers(dest="command", required=True)

    deploy_parser = subcommands.add_parser("deploy", help="Deploy a preset")
    deploy_parser.add_argument("preset", help="Name of the preset to deploy")
    deploy_parser.add_argument(
        "--terraform-dir",
        type=Path,
        default=Path("infra/terraform"),
        help="Terraform working directory",
    )
    deploy_parser.add_argument(
        "--context-path",
        type=Path,
        default=None,
        help="Docker build context override",
    )

    status_parser = subcommands.add_parser("status", help="Show deployment status")
    status_parser.set_defaults()

    logs_parser = subcommands.add_parser("logs", help="Show recent logs")
    logs_parser.add_argument("--limit", type=int, default=100, help="Number of log lines to display")

    shutdown_parser = subcommands.add_parser("shutdown", help="Destroy resources")
    shutdown_parser.add_argument(
        "--terraform-dir",
        type=Path,
        default=Path("infra/terraform"),
        help="Terraform working directory",
    )

    subcommands.add_parser("list-presets", help="List available presets")

    validate_parser = subcommands.add_parser("validate", help="Validate a service before deployment")
    validate_parser.add_argument("service", help="Service name to validate")

    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> None:
    """Entry point for the IntelligensiDeploy CLI."""

    args = parse_arguments(argv)

    if args.command == "deploy":
        deploy(args.preset, args.terraform_dir, args.context_path)
    elif args.command == "status":
        print(status())
    elif args.command == "logs":
        for line in logs(limit=args.limit):
            print(line)
    elif args.command == "shutdown":
        shutdown(args.terraform_dir)
    elif args.command == "list-presets":
        for preset in list_presets(Path("presets")):
            print(preset)
    elif args.command == "validate":
        validate(args.service)


if __name__ == "__main__":
    main()

