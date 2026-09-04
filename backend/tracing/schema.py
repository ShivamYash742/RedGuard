"""
Trace event schema for RedGuard multi-agent experiments.

Defines the controlled vocabulary of event types, content tags, and
the TraceEvent dataclass that represents every observable action in a run.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4


# ── Controlled Vocabulary ─────────────────────────────────────────────────────

# All valid event types. Any event outside this set is logged but flagged.
EVENT_TYPES: frozenset = frozenset(
    {
        # System / lifecycle
        "experiment_started",
        "experiment_completed",
        "cee_created",
        "cee_reset",
        # Agent lifecycle
        "agent_created",
        "task_assigned",
        "agent_step_started",
        "agent_step_completed",
        # Inter-agent communication
        "message_sent",
        "message_received",
        "message_filtered",
        # Tool execution lifecycle
        "tool_requested",
        "tool_authorized",
        "tool_denied",
        "tool_executed",
        "tool_result_returned",
        # Shared state
        "state_read",
        "state_write",
        "state_modified",
        # Attack injection marker
        "attack_injected",
        # Evaluation
        "verdict_computed",
    }
)

# Content tags — observational labels that track content origin.
# NOT security enforcement mechanisms.
CONTENT_TAGS: frozenset = frozenset(
    {
        "original_task",     # Content from the experiment controller task assignment
        "external_content",  # Content returned by a CEE tool (mock external source)
        "derived",           # Agent-produced content incorporating external content
        "attacker_artifact", # Adversarial payload injected by the CEE
        "system",            # Infrastructure / orchestration events
    }
)

RISK_LEVELS: frozenset = frozenset({"none", "low", "medium", "high"})


# ── TraceEvent ────────────────────────────────────────────────────────────────

@dataclass
class TraceEvent:
    """A single observable event in an experiment run.

    Instances are created exclusively by EventCollector.emit() which
    automatically assigns run_id, step, event_id, and timestamp.
    """

    event_id: str = field(default_factory=lambda: str(uuid4()))
    run_id: str = ""
    step: int = 0
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    agent_id: Optional[str] = None       # None for system / orchestrator events
    event_type: str = ""                  # Must be in EVENT_TYPES
    tool: Optional[str] = None
    arguments: Optional[Dict[str, Any]] = None
    result: Optional[str] = None
    authorized: Optional[bool] = None
    source_event_id: Optional[str] = None  # Provenance: ID of prior event this derives from
    content_tag: str = "system"            # Must be in CONTENT_TAGS
    risk: str = "none"                     # Must be in RISK_LEVELS
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dict (JSON-safe)."""
        return {
            "event_id": self.event_id,
            "run_id": self.run_id,
            "step": self.step,
            "timestamp": self.timestamp,
            "agent_id": self.agent_id,
            "event_type": self.event_type,
            "tool": self.tool,
            "arguments": self.arguments,
            "result": self.result,
            "authorized": self.authorized,
            "source_event_id": self.source_event_id,
            "content_tag": self.content_tag,
            "risk": self.risk,
            "metadata": self.metadata,
        }
