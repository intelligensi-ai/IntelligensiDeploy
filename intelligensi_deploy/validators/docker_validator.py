from pathlib import Path
from typing import List

def validate_dockerfile(path: str) -> List[str]:
    errors = []
    dockerfile = Path(path)

    if not dockerfile.exists():
        return ["Dockerfile missing"]

    content = dockerfile.read_text()

    # Required checks
    if "FROM" not in content:
        errors.append("Dockerfile missing FROM instruction")

    if "CMD" not in content and "ENTRYPOINT" not in content:
        errors.append("Dockerfile missing CMD or ENTRYPOINT")

    # Optional: warn against ADD instead of COPY
    if "ADD " in content:
        errors.append("Warning: ADD detected, COPY is recommended")

    return errors
