"""CEE lifecycle manager — create, reset, and vend CEEState instances."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, Optional

from .state import CEEState


@dataclass
class CEESnapshot:
    """Named snapshot configuration for an attack case's preconditions."""

    snapshot_id: str
    description: str
    state_json: str  # Serialized CEEState (from CEEState.snapshot())


class CEEManager:
    """Manages CEE lifecycle for experiments."""

    def __init__(self) -> None:
        self._snapshots: Dict[str, CEESnapshot] = {}
        self._active_state: Optional[CEEState] = None

    def register_snapshot(self, snapshot: CEESnapshot) -> None:
        """Register a named snapshot for use in experiments."""
        self._snapshots[snapshot.snapshot_id] = snapshot

    def create_from_snapshot(self, snapshot_id: str) -> CEEState:
        """Create a new CEE state from a registered snapshot."""
        snap = self._snapshots.get(snapshot_id)
        if snap is None:
            raise ValueError(f"Unknown snapshot: '{snapshot_id}'. "
                             f"Registered: {list(self._snapshots.keys())}")
        self._active_state = CEEState.from_snapshot(snap.state_json)
        return self._active_state

    def create_from_config(self, config: Dict[str, Any]) -> CEEState:
        """Create a new CEE state from an inline configuration dict."""
        state = CEEState(
            filesystem=config.get("filesystem", {}),
            web_results=config.get("web_results", {}),
            database=config.get("database", {}),
        )
        self._active_state = state
        return state

    def reset(self, snapshot_id: str) -> CEEState:
        """Reset active state to a named snapshot. Returns the reset state."""
        snap = self._snapshots.get(snapshot_id)
        if snap is None:
            raise ValueError(f"Unknown snapshot: '{snapshot_id}'")
        if self._active_state is None:
            self._active_state = CEEState()
        self._active_state.reset_from(snap.state_json)
        return self._active_state

    def get_active_state(self) -> Optional[CEEState]:
        """Return the currently active CEEState, or None if not initialized."""
        return self._active_state
