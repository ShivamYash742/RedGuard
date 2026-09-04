"""
Append-only trace event collector.

One EventCollector instance per experiment run. The collector:
- Assigns sequential, gapless step numbers
- Stores events in memory for the duration of the run
- Optionally calls an async hook for real-time SSE streaming
- Provides query helpers for verdict and metric computation
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine, Dict, List, Optional
from uuid import uuid4

from .schema import TraceEvent, CONTENT_TAGS, EVENT_TYPES, RISK_LEVELS

# Type for an optional async hook invoked on every event (used for SSE)
AsyncEventHook = Callable[[TraceEvent], Coroutine[Any, Any, None]]


class EventCollector:
    """Collects trace events for a single experiment run."""

    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        self._events: List[TraceEvent] = []
        self._step_counter: int = 0
        self._async_hook: Optional[AsyncEventHook] = None

    def set_async_hook(self, hook: AsyncEventHook) -> None:
        """Register an async callback invoked immediately after each event is appended."""
        self._async_hook = hook

    def emit(self, event_data: Dict[str, Any]) -> TraceEvent:
        """
        Create, store, and return a TraceEvent from an event dict.

        Automatically assigns: run_id, step (sequential), event_id, timestamp.
        Fields not supplied default to safe values.

        If an async hook is registered and an event loop is running, the hook
        is scheduled as a background task (fire-and-forget, non-blocking).
        """
        self._step_counter += 1

        # Normalize content_tag and risk to controlled vocabulary
        raw_tag = event_data.get("content_tag", "system")
        content_tag = raw_tag if raw_tag in CONTENT_TAGS else "system"

        raw_risk = event_data.get("risk", "none")
        risk = raw_risk if raw_risk in RISK_LEVELS else "none"

        event = TraceEvent(
            event_id=str(uuid4()),
            run_id=self.run_id,
            step=self._step_counter,
            timestamp=datetime.now(timezone.utc).isoformat(),
            agent_id=event_data.get("agent_id"),
            event_type=event_data.get("event_type", ""),
            tool=event_data.get("tool"),
            arguments=event_data.get("arguments"),
            result=event_data.get("result"),
            authorized=event_data.get("authorized"),
            source_event_id=event_data.get("source_event_id"),
            content_tag=content_tag,
            risk=risk,
            metadata=event_data.get("metadata"),
        )

        self._events.append(event)

        # Fire async hook without blocking
        if self._async_hook is not None:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._async_hook(event))
            except RuntimeError:
                # No running event loop — skip async hook (e.g. in sync tests)
                pass

        return event

    # ── Query Helpers ─────────────────────────────────────────────────────────

    def get_events(self) -> List[TraceEvent]:
        """All events in step order."""
        return list(self._events)

    def get_events_by_agent(self, agent_id: str) -> List[TraceEvent]:
        return [e for e in self._events if e.agent_id == agent_id]

    def get_events_by_type(self, event_type: str) -> List[TraceEvent]:
        return [e for e in self._events if e.event_type == event_type]

    def get_events_by_content_tag(self, tag: str) -> List[TraceEvent]:
        return [e for e in self._events if e.content_tag == tag]

    def get_behavioral_subsequence(self, agent_id: Optional[str] = None) -> List[TraceEvent]:
        """
        Extract the behavioral subsequence used for TDS computation.

        Behavioral events are agent *actions*, not passive observations:
        tool_requested, tool_executed, tool_denied, state_write, message_sent
        """
        action_types = {
            "tool_requested",
            "tool_executed",
            "tool_denied",
            "state_write",
            "message_sent",
        }
        events = self._events if agent_id is None else self.get_events_by_agent(agent_id)
        return [e for e in events if e.event_type in action_types]

    def to_dicts(self) -> List[Dict[str, Any]]:
        """Serialize all events to a list of dicts."""
        return [e.to_dict() for e in self._events]

    @property
    def event_count(self) -> int:
        return len(self._events)
