"""
RedGuard Lab Trace
===================

The primary evidence layer for Mode B (§8, §5.5 of MULTI_AGENT_LAB_PLAN.md).

An `EventCollector` owns a monotonic `step` counter per run and appends
immutable `TraceEvent`s. Provenance (`derived_from`) is recorded at emission
time by the caller (tool gateway, message bus, runner) — never reconstructed
afterwards.

A `TraceEvent.step` is the identifier other events reference via
`source_event_id` / `derived_from`, matching the worked example in §8 of the
plan. Persistence to the `lab_trace_events` table (mapping run_id+step to a
DB row id) is a later phase's concern, not this module's.

Content tags are observational labels describing where content came from.
They are **not** trust levels — see `test_content_tags_not_branched_on` in
core/tests/test_lab_trace.py, which enforces this by construction: nothing
in this package inspects `content_tag` to make an authorization decision.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


# ─────────────────────────────────────────────────────────────────────────────
# Enums (§8)
# ─────────────────────────────────────────────────────────────────────────────

class EventCategory(str, Enum):
    SYSTEM = "system"
    INJECTION = "injection"
    AGENT = "agent"
    COMMUNICATION = "communication"
    TOOL = "tool"
    STATE = "state"
    EVALUATION = "evaluation"


class EventType(str, Enum):
    # system
    RUN_STARTED = "run_started"
    CEE_LOADED = "cee_loaded"
    CONFIG_SNAPSHOT = "config_snapshot"
    RUN_FINISHED = "run_finished"
    # injection
    ARTIFACT_PLANTED = "artifact_planted"
    ARTIFACT_OBSERVED = "artifact_observed"
    # agent
    AGENT_STEP_STARTED = "agent_step_started"
    AGENT_OUTPUT = "agent_output"
    ACTION_PARSE_FAILED = "action_parse_failed"
    AGENT_FINISHED = "agent_finished"
    # communication
    MESSAGE_SENT = "message_sent"
    MESSAGE_DELIVERED = "message_delivered"
    MESSAGE_DENIED = "message_denied"
    MESSAGE_RECEIVED = "message_received"
    # tool
    TOOL_REQUESTED = "tool_requested"
    TOOL_EXECUTED = "tool_executed"
    TOOL_DENIED = "tool_denied"
    TOOL_ERROR = "tool_error"
    # state
    STATE_READ = "state_read"
    STATE_WRITE = "state_write"
    # evaluation
    PREDICATE_MATCHED = "predicate_matched"
    VERDICT_EMITTED = "verdict_emitted"


class ContentTag(str, Enum):
    ORIGINAL_TASK = "original_task"
    EXTERNAL_CONTENT = "external_content"
    DERIVED = "derived"
    ATTACKER_ARTIFACT = "attacker_artifact"


#: Terminal events for taint-closure purposes (§5.5): an event is
#: attack-derived if its derived_from closure reaches one of these.
_ARTIFACT_EVENT_TYPES = frozenset({EventType.ARTIFACT_PLANTED, EventType.ARTIFACT_OBSERVED})


# ─────────────────────────────────────────────────────────────────────────────
# TraceEvent
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class TraceEvent:
    """One immutable, append-only trace record.

    `step` is this event's identifier within its run; `source_event_id` and
    `derived_from` reference other events' `step` values.
    """

    step: int
    category: EventCategory
    event_type: EventType
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    agent_id: Optional[str] = None
    tool: Optional[str] = None
    arguments: Optional[Dict[str, Any]] = None
    result: Optional[Any] = None
    authorized: Optional[bool] = None
    source_event_id: Optional[int] = None
    derived_from: Tuple[int, ...] = ()
    content_tag: Optional[ContentTag] = None
    risk: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TraceEvent":
        """Inverse of `to_dict`, minus timestamp fidelity (irrelevant to
        evaluation — order is carried by `step`). Used to load hand-authored
        golden-trace fixtures (core/tests/golden_traces/*.json) and any other
        externally-serialized trace.
        """
        return cls(
            step=data["step"],
            category=EventCategory(data["category"]),
            event_type=EventType(data["event_type"]),
            agent_id=data.get("agent_id"),
            tool=data.get("tool"),
            arguments=data.get("arguments"),
            result=data.get("result"),
            authorized=data.get("authorized"),
            source_event_id=data.get("source_event_id"),
            derived_from=tuple(data.get("derived_from") or ()),
            content_tag=ContentTag(data["content_tag"]) if data.get("content_tag") else None,
            risk=data.get("risk"),
            metadata=data.get("metadata"),
        )

    def to_dict(self) -> Dict[str, Any]:
        """JSON-serializable representation, for evidence bundles and persistence."""
        return {
            "step": self.step,
            "category": self.category.value,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "agent_id": self.agent_id,
            "tool": self.tool,
            "arguments": self.arguments,
            "result": self.result,
            "authorized": self.authorized,
            "source_event_id": self.source_event_id,
            "derived_from": list(self.derived_from),
            "content_tag": self.content_tag.value if self.content_tag else None,
            "risk": self.risk,
            "metadata": self.metadata,
        }


# ─────────────────────────────────────────────────────────────────────────────
# EventCollector
# ─────────────────────────────────────────────────────────────────────────────

class EventCollector:
    """Appends `TraceEvent`s for one run, assigning a monotonic `step` to each."""

    def __init__(self, run_id: str):
        self.run_id = run_id
        self._events: List[TraceEvent] = []
        self._next_step = 0

    @property
    def events(self) -> List[TraceEvent]:
        """Read-only view of events emitted so far, in emission order."""
        return list(self._events)

    def emit(
        self,
        category: EventCategory,
        event_type: EventType,
        *,
        agent_id: Optional[str] = None,
        tool: Optional[str] = None,
        arguments: Optional[Dict[str, Any]] = None,
        result: Optional[Any] = None,
        authorized: Optional[bool] = None,
        source_event_id: Optional[int] = None,
        derived_from: Tuple[int, ...] = (),
        content_tag: Optional[ContentTag] = None,
        risk: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TraceEvent:
        event = TraceEvent(
            step=self._next_step,
            category=category,
            event_type=event_type,
            agent_id=agent_id,
            tool=tool,
            arguments=arguments,
            result=result,
            authorized=authorized,
            source_event_id=source_event_id,
            derived_from=tuple(derived_from),
            content_tag=content_tag,
            risk=risk,
            metadata=metadata,
        )
        self._next_step += 1
        self._events.append(event)
        return event

    def by_step(self, step: int) -> Optional[TraceEvent]:
        """O(n) lookup by step. Fine at MVP trace volumes (~40-80 events/run)."""
        for event in self._events:
            if event.step == step:
                return event
        return None

    def to_json(self) -> List[Dict[str, Any]]:
        return [event.to_dict() for event in self._events]

    @classmethod
    def from_events(cls, run_id: str, events: List[TraceEvent]) -> "EventCollector":
        """Rehydrate a collector from previously-persisted events (e.g. loaded
        back from the DB), in step order. Used for offline replay — the
        evaluator (later phases) takes a collector, not a DB row set.
        """
        collector = cls(run_id)
        collector._events = list(events)
        collector._next_step = (events[-1].step + 1) if events else 0
        return collector


# ─────────────────────────────────────────────────────────────────────────────
# Taint closure + canary scan (§5.5)
# ─────────────────────────────────────────────────────────────────────────────

def is_attack_derived(collector: EventCollector, step: int) -> bool:
    """True if `step`, or any event transitively reachable via `derived_from`,
    is an artifact_planted / artifact_observed event.
    """
    visited: set[int] = set()
    stack = [step]
    while stack:
        current = stack.pop()
        if current in visited:
            continue
        visited.add(current)
        event = collector.by_step(current)
        if event is None:
            continue
        if event.event_type in _ARTIFACT_EVENT_TYPES:
            return True
        stack.extend(event.derived_from)
    return False


def canary_in(value: Any, canary: str) -> bool:
    """Substring scan for a case's canary token — the second, independent
    propagation signal alongside `derived_from` taint closure (§5.5).
    """
    if not canary or value is None:
        return False
    return canary in str(value)
