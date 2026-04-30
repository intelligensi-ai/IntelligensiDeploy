"""Auto-fix suggester module for deployment issues."""

from typing import List


def suggest_fixes(service: str, issues: List[str]) -> List[str]:
    """Suggest fixes for deployment issues.

    Args:
        service: Service name being validated
        issues: List of issues found during validation

    Returns:
        List of suggested fixes
    """
    # TODO: Implement actual fix suggestions based on issue analysis
    fixes: List[str] = []

    for issue in issues:
        lowered = issue.lower()
        if "nebius_ip missing" in lowered or "provider host" in lowered or "provider.nebius.env" in lowered:
            fixes.append(
                "Add Nebius host and SSH settings to services/ltx-worker/provider.nebius.env, or run the Lambda preset for Lambda-hosted workers."
            )
        elif "missing env file" in lowered or "service.env" in lowered:
            fixes.append(
                "Use the dashboard Lambda Config panel for connection settings, SSH path, registry token, and HF_TOKEN."
            )
        elif "folder not found" in lowered:
            fixes.append(f"Create the service directory: mkdir -p services/{service}")
        elif "dockerfile missing" in lowered:
            fixes.append(f"Create a Dockerfile in services/{service}/Dockerfile")
        elif "port" in lowered:
            fixes.append("Check port configuration in service manifest")
        elif "environment" in lowered:
            fixes.append("Verify environment variables are properly set")
        else:
            fixes.append(f"Review and fix: {issue}")

    if not fixes:
        fixes = [
            "Check service configuration",
            "Verify Docker image build",
            "Review deployment logs",
            "Validate network connectivity",
        ]

    return fixes
