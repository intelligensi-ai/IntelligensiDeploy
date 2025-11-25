"""
Converts validator errors into human-readable fixes and optional patch instructions.
"""


def suggest_fixes(errors: list[str]) -> list[str]:
    suggestions = []

    for e in errors:

        # Missing required files
        if "Missing required file:" in e:
            missing = e.split(":")[1].strip()
            suggestions.append(
                f"• Create `{missing}` in the service folder. "
                f"Example placeholder will be generated if you choose auto-fix."
            )

        # deploy_config errors
        if "deploy_config.yaml" in e:
            suggestions.append(
                "• Check deploy_config.yaml format. Ensure keys: service_name, docker, resources."
            )

        # Dockerfile errors
        if "Dockerfile missing FROM" in e:
            suggestions.append("• Add a FROM line, e.g. FROM nvidia/cuda:12.8.0-base-ubuntu22.04")

        if "CMD" in e:
            suggestions.append("• Add a CMD or ENTRYPOINT to the Dockerfile.")

    if not suggestions:
        suggestions.append("• No auto-fix suggestions available.")

    return suggestions
