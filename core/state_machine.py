"""State machine scaffolding for deployment workflows."""

from typing import Any, Dict, Optional


class StateMachine:
    """Placeholder state machine for orchestrating deployment phases."""

    def __init__(self, initial_state: Optional[str] = None) -> None:
        """Initialize the state machine with an optional initial state."""
        self.initial_state = initial_state
        self.current_state = initial_state

    def transition(self, target_state: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Transition to a new state using the provided context."""
        self.current_state = target_state

    def reset(self) -> None:
        """Reset the state machine back to the initial state."""
        self.current_state = self.initial_state
