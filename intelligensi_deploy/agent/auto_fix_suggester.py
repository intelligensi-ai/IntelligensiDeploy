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
        if "folder not found" in issue.lower():
            fixes.append(f"Create the service directory: mkdir -p services/{service}")
        elif "dockerfile missing" in issue.lower():
            fixes.append(f"Create a Dockerfile in services/{service}/Dockerfile")
        elif "port" in issue.lower():
            fixes.append("Check port configuration in service manifest")
        elif "environment" in issue.lower():
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

