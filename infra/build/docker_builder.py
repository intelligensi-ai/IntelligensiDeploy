"""Docker image builder for IntelligensiDeploy presets."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


class DockerBuildError(RuntimeError):
    """Raised when docker build fails."""

    def __init__(self, command: List[str], return_code: int, stdout: str, stderr: str) -> None:
        super().__init__(f"Docker build failed with exit code {return_code}")
        self.command = command
        self.return_code = return_code
        self.stdout = stdout
        self.stderr = stderr


@dataclass
class BuildResult:
    """Represents the outcome of a docker build."""

    command: List[str]
    return_code: int
    stdout: str
    stderr: str
    image_tags: List[str]


PRESET_CONTEXTS: Dict[str, Path] = {
    "flux_image_server": Path("services/image-server"),
    "image-server": Path("services/image-server"),
}


def build_image(preset: str, context_path: Optional[Path] = None, tags: Optional[Dict[str, str]] = None) -> BuildResult:
    """Build a docker image for the given preset.

    Args:
        preset: Name of the deployment preset.
        context_path: Optional override for the build context directory.
        tags: Mapping of repository names to tag strings.

    Raises:
        DockerBuildError: If the docker build command exits non-zero.

    Returns:
        BuildResult capturing the executed command and command output.
    """

    resolved_context = context_path or PRESET_CONTEXTS.get(preset) or Path.cwd()
    resolved_context = resolved_context.resolve()

    if not resolved_context.exists():
        raise DockerBuildError(["docker", "build"], 1, "", f"Context path does not exist: {resolved_context}")

    image_tags = _build_tags(preset, tags)
    command = ["docker", "build", str(resolved_context)]
    for tag in image_tags:
        command.extend(["-t", tag])

    process = subprocess.run(command, capture_output=True, text=True, check=False)
    if process.returncode != 0:
        raise DockerBuildError(command, process.returncode, process.stdout, process.stderr)

    return BuildResult(
        command=command,
        return_code=process.returncode,
        stdout=process.stdout,
        stderr=process.stderr,
        image_tags=image_tags,
    )


def _build_tags(preset: str, tags: Optional[Dict[str, str]]) -> List[str]:
    """Construct docker tags from a mapping or preset defaults."""

    if tags:
        return [f"{repository}:{tag}" for repository, tag in tags.items()]

    return [f"intelligensi/{preset}:latest"]

