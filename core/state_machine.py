"""State machine for orchestrating IntelligensiDeploy workflows."""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

from infra.build import docker_builder

DEFAULT_STATE_PATH = Path(".intelligensi_state.json")


class StateTransitionError(RuntimeError):
    """Raised when an invalid state transition is requested."""

    def __init__(self, current_state: str, target_state: str) -> None:
        message = f"Invalid transition from '{current_state}' to '{target_state}'"
        super().__init__(message)
        self.current_state = current_state
        self.target_state = target_state


class CommandExecutionError(RuntimeError):
    """Base error for subprocess execution failures."""

    def __init__(self, command: Sequence[str], return_code: int, stdout: str, stderr: str) -> None:
        super().__init__("Command execution failed")
        self.command = list(command)
        self.return_code = return_code
        self.stdout = stdout
        self.stderr = stderr


class TerraformExecutionError(CommandExecutionError):
    """Raised when a Terraform command exits with a non-zero status."""


class DockerBuildError(CommandExecutionError):
    """Raised when Docker fails to build an image."""


@dataclass
class TransitionRecord:
    """Captures a single state transition."""

    timestamp: str
    from_state: Optional[str]
    to_state: str
    context: Dict[str, Any] = field(default_factory=dict)


class StateMachine:
    """State machine coordinating Terraform and Docker phases."""

    def __init__(
        self,
        initial_state: str = "idle",
        allowed_transitions: Optional[Dict[str, Iterable[str]]] = None,
        state_store: Path = DEFAULT_STATE_PATH,
        logger: Optional[logging.Logger] = None,
        event_hook: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    ) -> None:
        """Initialize the state machine.

        Args:
            initial_state: Starting state for the workflow.
            allowed_transitions: Optional mapping of valid transitions.
            state_store: Path to a JSON file that persists state.
            logger: Optional logger instance; defaults to module logger.
            event_hook: Callback invoked for transitions and command execution.
        """

        self.logger = logger or logging.getLogger("intelligensi.state_machine")
        self.logger.setLevel(logging.INFO)
        self.event_hook = event_hook
        self.state_store = state_store
        self.allowed_transitions = allowed_transitions or self._default_transitions()
        self.initial_state = initial_state
        self.current_state = initial_state
        self.history: List[TransitionRecord] = []

        self._load_state()

    @staticmethod
    def _default_transitions() -> Dict[str, Iterable[str]]:
        """Return a default transition map for deployment workflows."""

        return {
            "idle": ("planning", "provisioning"),
            "planning": ("provisioning", "error"),
            "provisioning": ("building", "error"),
            "building": ("deploying", "error"),
            "deploying": ("verifying", "running", "error"),
            "verifying": ("running", "error"),
            "running": ("updating", "shutdown", "error"),
            "updating": ("verifying", "running", "error"),
            "shutdown": ("idle",),
            "error": ("idle",),
        }

    def _emit_event(self, kind: str, payload: Dict[str, Any]) -> None:
        """Invoke the event hook when provided."""

        if self.event_hook:
            self.event_hook(kind, payload)

    def _load_state(self) -> None:
        """Load persisted state from disk if available."""

        if not self.state_store.exists():
            return

        try:
            data = json.loads(self.state_store.read_text())
            self.initial_state = data.get("initial_state", self.initial_state)
            self.current_state = data.get("current_state", self.current_state)
            self.allowed_transitions = data.get("allowed_transitions", self.allowed_transitions)
            history_records = data.get("history", [])
            self.history = [TransitionRecord(**record) for record in history_records]
        except (json.JSONDecodeError, OSError, TypeError) as exc:
            self.logger.warning("Unable to load state file %s: %s", self.state_store, exc)

    def _persist_state(self) -> None:
        """Persist current state and history to disk."""

        payload = {
            "initial_state": self.initial_state,
            "current_state": self.current_state,
            "allowed_transitions": self.allowed_transitions,
            "history": [record.__dict__ for record in self.history],
        }
        try:
            self.state_store.write_text(json.dumps(payload, indent=2))
        except OSError as exc:
            self.logger.error("Failed to persist state to %s: %s", self.state_store, exc)

    def transition(self, target_state: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Transition to a new state using the provided context.

        Raises:
            StateTransitionError: if the transition is not allowed.
        """

        context = context or {}
        allowed = self.allowed_transitions.get(self.current_state, ())
        if target_state not in allowed:
            self.logger.error("Invalid transition %s -> %s", self.current_state, target_state)
            raise StateTransitionError(self.current_state, target_state)

        record = TransitionRecord(
            timestamp=datetime.utcnow().isoformat() + "Z",
            from_state=self.current_state,
            to_state=target_state,
            context=context,
        )
        self.history.append(record)
        self.current_state = target_state
        self._persist_state()

        self.logger.info("Transitioned from %s to %s", record.from_state, record.to_state)
        self._emit_event("transition", record.__dict__)

    def reset(self) -> None:
        """Reset the state machine back to the initial state."""

        self.current_state = self.initial_state
        self.history.append(
            TransitionRecord(
                timestamp=datetime.utcnow().isoformat() + "Z",
                from_state=None,
                to_state=self.initial_state,
                context={"reset": True},
            )
        )
        self._persist_state()
        self.logger.info("State machine reset to %s", self.initial_state)
        self._emit_event("reset", {"state": self.initial_state})

    def get_history(self) -> List[TransitionRecord]:
        """Return a copy of the transition history."""

        return list(self.history)

    def run_terraform(self, action: str, workdir: Path, extra_args: Optional[Iterable[str]] = None) -> subprocess.CompletedProcess:
        """Execute a Terraform command in the provided working directory."""

        command = ["terraform", action]
        if extra_args:
            command.extend(extra_args)

        self.logger.info("Running Terraform command: %s", " ".join(command))
        self._emit_event("terraform", {"action": action, "workdir": str(workdir)})
        return self._run_command(command, workdir, TerraformExecutionError)

    def build_container_image(
        self,
        preset: str,
        context_path: Optional[Path] = None,
        tags: Optional[Dict[str, str]] = None,
    ) -> docker_builder.BuildResult:
        """Build a Docker image using the configured builder."""

        self.logger.info("Building Docker image for preset '%s'", preset)
        self._emit_event("docker_build", {"preset": preset, "context_path": str(context_path) if context_path else None})

        try:
            result = docker_builder.build_image(preset=preset, context_path=context_path, tags=tags)
        except docker_builder.DockerBuildError as exc:  # type: ignore[attr-defined]
            self.logger.error("Docker build failed: %s", exc)
            raise DockerBuildError(exc.command, exc.return_code, exc.stdout, exc.stderr)
        return result

    def _run_command(
        self,
        command: Sequence[str],
        workdir: Path,
        error_cls: type[CommandExecutionError],
    ) -> subprocess.CompletedProcess:
        """Execute a command and return the completed process, raising on failure."""

        process = subprocess.run(
            command,
            cwd=workdir,
            check=False,
            capture_output=True,
            text=True,
        )

        if process.returncode != 0:
            raise error_cls(command, process.returncode, process.stdout, process.stderr)

        return process

