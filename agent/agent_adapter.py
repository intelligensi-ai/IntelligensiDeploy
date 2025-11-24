"""Read-only adapter for exposing deployment state to agents."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.state_machine import DEFAULT_STATE_PATH, TransitionRecord


class AgentAdapter:
    """Provides a constrained view of deployment state for agents."""

    def __init__(self, agent_id: str, state_store: Path = DEFAULT_STATE_PATH, log_path: Optional[Path] = None) -> None:
        """Create a new read-only adapter instance."""

        self.agent_id = agent_id
        self.state_store = state_store
        self.log_path = log_path or Path("deploy.log")

    def _load_state_blob(self) -> Dict[str, Any]:
        """Load the persisted state file into memory."""

        if not self.state_store.exists():
            return {}
        try:
            return json.loads(self.state_store.read_text())
        except (json.JSONDecodeError, OSError):
            return {}

    def get_state(self) -> Optional[str]:
        """Return the last persisted state for the workflow."""

        return self._load_state_blob().get("current_state")

    def get_logs(self, limit: int = 100) -> List[str]:
        """Return the last ``limit`` lines from the deployment log file."""

        if not self.log_path.exists():
            return []

        lines = self.log_path.read_text(errors="ignore").splitlines()
        return lines[-limit:]

    def propose_plan(self) -> Dict[str, Any]:
        """Suggest the next phase based on the latest transition."""

        state_blob = self._load_state_blob()
        history = [TransitionRecord(**record) for record in state_blob.get("history", [])]
        latest = history[-1].to_state if history else "idle"

        proposals = {
            "idle": ["planning"],
            "planning": ["provisioning"],
            "provisioning": ["building"],
            "building": ["deploying"],
            "deploying": ["verifying"],
            "verifying": ["running"],
        }

        return {"current": latest, "next": proposals.get(latest, [])}

    def validate_plan(self, proposed_state: str) -> bool:
        """Validate that a proposed state is reachable from the current state."""

        state_blob = self._load_state_blob()
        current_state = state_blob.get("current_state", "idle")
        allowed_transitions = state_blob.get("allowed_transitions")

        if allowed_transitions and isinstance(allowed_transitions, dict):
            allowed = allowed_transitions.get(current_state, [])
            return proposed_state in allowed

        return proposed_state != current_state

