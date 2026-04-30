"""Rule-based deployment failure classification and safe repair decisions."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List


SAFE_AUTO_CATEGORIES = {
    "lambda_capacity",
    "lambda_shape_drift",
    "missing_env_file",
    "ssh_readiness",
    "health_timeout",
    "docker_build",
}


@dataclass
class FailureClassification:
    category: str
    confidence: float
    evidence: List[str]
    safe_to_auto_apply: bool
    recommended_action: str
    retry_allowed: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RepairAction:
    id: str
    description: str
    command_or_patch: str
    risk_level: str
    requires_operator_secret: bool
    rollback_note: str
    retry_allowed: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _lines(logs: Iterable[str] | str) -> List[str]:
    if isinstance(logs, str):
        return logs.splitlines()
    return [str(item) for item in logs]


def _evidence(lines: List[str], needles: Iterable[str], limit: int = 4) -> List[str]:
    lowered_needles = [needle.lower() for needle in needles]
    matches = [
        line.strip()
        for line in lines
        if any(needle in line.lower() for needle in lowered_needles)
    ]
    return matches[:limit]


def classify_failure(logs: Iterable[str] | str, error_text: str = "") -> FailureClassification:
    lines = _lines(logs)
    combined = "\n".join([*lines, error_text]).lower()

    rules = [
        (
            "provider_host_config_missing",
            ("nebius_ip missing", "missing nebius provider config", "provider host configuration", "provider.nebius.env"),
            "Add the Nebius host/SSH settings to services/ltx-worker/provider.nebius.env, or use a Lambda preset for Lambda-hosted workers.",
            False,
            0.94,
        ),
        (
            "missing_env_file",
            ("missing env file", "lambda config panel", "service.env"),
            "Use the dashboard Lambda Config panel for the current Lambda-first flow.",
            True,
            0.94,
        ),
        (
            "lambda_capacity",
            ("insufficient-capacity", "not enough capacity", "capacity to fulfill launch request"),
            "Retry the next ranked Lambda GPU option.",
            True,
            0.96,
        ),
        (
            "lambda_shape_drift",
            ("instance type", "not found", "unsupported instance"),
            "Refresh Lambda instance types and retry a currently listed GPU option.",
            True,
            0.86,
        ),
        (
            "credentials",
            ("invalid-api-key", "unauthorized", "401", "api key was invalid", "expired"),
            "Save valid credentials, then retry manually.",
            False,
            0.92,
        ),
        (
            "ssh_key",
            ("permission denied (publickey)", "no such identity", "bad permissions"),
            "Check the configured SSH key name and private key path.",
            False,
            0.9,
        ),
        (
            "ssh_readiness",
            ("connection timed out", "connection refused", "ssh failed after", "operation timed out"),
            "Wait for instance boot and retry SSH within the configured limit.",
            True,
            0.78,
        ),
        (
            "ghcr_auth",
            ("ghcr", "denied", "unauthorized", "docker login"),
            "Run Docker login for ghcr.io or save a valid GHCR token.",
            False,
            0.82,
        ),
        (
            "huggingface_auth",
            ("gatedrepoerror", "hf_token", "hugging face", "model is gated"),
            "Save a valid HF_TOKEN with access to the requested model.",
            False,
            0.84,
        ),
        (
            "docker_build",
            ("docker build failed", "failed to solve", "buildkit", "dockerfile"),
            "Retry the Docker build once, then stop for operator review.",
            True,
            0.74,
        ),
        (
            "docker_image_missing",
            ("docker pull", "not found", "manifest unknown", "pull access denied"),
            "Verify the configured image tag exists and credentials can pull it.",
            False,
            0.78,
        ),
        (
            "port_conflict",
            ("port is already allocated", "address already in use", "bind: address"),
            "Stop the conflicting container or choose another service port.",
            False,
            0.8,
        ),
        (
            "health_timeout",
            ("health check", "timed out", "unable to reach", "service boot"),
            "Extend the health-check wait once and tail service logs.",
            True,
            0.72,
        ),
    ]

    for category, needles, action, safe, confidence in rules:
        if any(needle in combined for needle in needles):
            return FailureClassification(
                category=category,
                confidence=confidence,
                evidence=_evidence(lines + [error_text], needles) or [error_text.strip()][:1],
                safe_to_auto_apply=safe,
                recommended_action=action,
                retry_allowed=safe,
            )

    return FailureClassification(
        category="unknown",
        confidence=0.2,
        evidence=[line for line in lines[-4:] if line.strip()] or ([error_text.strip()] if error_text.strip() else []),
        safe_to_auto_apply=False,
        recommended_action="Stop for operator review. The failure did not match a known safe repair rule.",
        retry_allowed=False,
    )


def resolve_repair_action(
    classification: FailureClassification,
    retry_number: int = 0,
    retry_limit: int = 1,
) -> RepairAction:
    retry_allowed = classification.retry_allowed and retry_number < retry_limit
    if not classification.safe_to_auto_apply:
        return RepairAction(
            id=f"manual_{classification.category}",
            description=classification.recommended_action,
            command_or_patch="manual",
            risk_level="manual",
            requires_operator_secret=classification.category in {"credentials", "ghcr_auth", "huggingface_auth"},
            rollback_note="No automatic change was applied.",
            retry_allowed=False,
            metadata={"category": classification.category},
        )

    actions = {
        "missing_env_file": ("use_lambda_config_panel", "Use the dashboard Lambda Config panel for current connection and secret settings."),
        "lambda_capacity": ("retry_next_lambda_gpu", "Retry with the next ranked Lambda GPU option."),
        "lambda_shape_drift": ("refresh_lambda_shapes", "Refresh Lambda GPU availability and retry."),
        "ssh_readiness": ("retry_ssh_after_wait", "Wait and retry SSH readiness."),
        "health_timeout": ("extend_health_wait", "Extend health-check wait once."),
        "docker_build": ("retry_docker_build_once", "Retry Docker build once."),
    }
    action_id, description = actions.get(
        classification.category,
        ("manual_unknown", classification.recommended_action),
    )
    if classification.category == "missing_env_file":
        retry_allowed = False
    return RepairAction(
        id=action_id,
        description=description,
        command_or_patch=action_id if retry_allowed else "retry-limit-reached",
        risk_level="low" if retry_allowed else "manual",
        requires_operator_secret=False,
        rollback_note="The retry is bounded and no destructive cleanup is performed.",
        retry_allowed=retry_allowed,
        metadata={"category": classification.category, "retry_number": retry_number, "retry_limit": retry_limit},
    )


def build_repair_record(
    logs: Iterable[str] | str,
    error_text: str = "",
    retry_number: int = 0,
    retry_limit: int = 1,
) -> Dict[str, Any]:
    classification = classify_failure(logs, error_text)
    action = resolve_repair_action(classification, retry_number=retry_number, retry_limit=retry_limit)
    return {
        "classification": classification.to_dict(),
        "action": action.to_dict(),
        "retry_number": retry_number,
        "retry_limit": retry_limit,
        "result": "pending" if action.retry_allowed else "manual_required",
    }


__all__ = [
    "FailureClassification",
    "RepairAction",
    "build_repair_record",
    "classify_failure",
    "resolve_repair_action",
]
