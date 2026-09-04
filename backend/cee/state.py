"""CEE in-memory state store."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Dict, List
import json


@dataclass
class CEEState:
    """
    Controlled Execution Environment state.

    NOT a security sandbox. This is a deterministic research fixture
    providing mock resources for agent tools. No OS-level isolation.
    Agents still call real LLM APIs; only tool inputs/outputs are
    intercepted and served from this state.
    """

    # Mock filesystem: path → content string
    filesystem: Dict[str, str] = field(default_factory=dict)

    # Mock web search results: query_keyword → list of result strings
    web_results: Dict[str, List[str]] = field(default_factory=dict)

    # Mock key-value database: key → value (any JSON-serializable)
    database: Dict[str, Any] = field(default_factory=dict)

    # Event log of all state accesses (populated by tools)
    access_log: List[Dict[str, Any]] = field(default_factory=list)

    def snapshot(self) -> str:
        """Serialize current state to JSON string for reproducibility."""
        return json.dumps(
            {
                "filesystem": self.filesystem,
                "web_results": self.web_results,
                "database": self.database,
            },
            sort_keys=True,
            indent=2,
        )

    @classmethod
    def from_snapshot(cls, snapshot_json: str) -> "CEEState":
        """Restore state from a JSON snapshot."""
        data = json.loads(snapshot_json)
        return cls(
            filesystem=data.get("filesystem", {}),
            web_results=data.get("web_results", {}),
            database=data.get("database", {}),
        )

    def reset_from(self, snapshot_json: str) -> None:
        """Reset to a saved snapshot state. Clears access_log."""
        data = json.loads(snapshot_json)
        self.filesystem = data.get("filesystem", {})
        self.web_results = data.get("web_results", {})
        self.database = data.get("database", {})
        self.access_log = []

    def deep_copy(self) -> "CEEState":
        """Return an independent deep copy of this state."""
        return deepcopy(self)
