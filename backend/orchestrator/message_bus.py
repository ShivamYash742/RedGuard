"""
Inter-agent message bus.

Routes messages between agents according to the experiment topology.
Applies content tags, records provenance, and emits trace events.

Does NOT alter message content — observational and routing only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from uuid import uuid4

EventCallback = Callable[[Dict[str, Any]], None]


@dataclass
class AgentMessage:
    """A message routed from one agent to another."""

    message_id: str
    sender_id: str
    receiver_id: str
    content: str
    content_tag: str                    # Observational tag, NOT a security label
    source_event_id: Optional[str] = None  # Provenance: event ID that produced this content
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self) -> None:
        if not self.message_id:
            self.message_id = str(uuid4())[:8]


class MessageBus:
    """
    Routes messages between agents according to topology edges.

    Contract:
    - Only routes messages along declared topology edges.
    - Emits message_sent + message_received on allowed edges.
    - Emits message_sent + message_filtered on disallowed edges.
    - Does NOT modify message content.
    """

    def __init__(
        self,
        allowed_edges: List[Tuple[str, str]],
        emit_event: EventCallback,
    ) -> None:
        self._allowed_edges: Set[Tuple[str, str]] = set(
            (src, dst) for src, dst in allowed_edges
        )
        self._emit = emit_event
        self._message_log: List[AgentMessage] = []

    def send(self, message: AgentMessage) -> bool:
        """
        Attempt to route a message.

        Returns True if delivered (edge is in topology), False if filtered.
        """
        edge = (message.sender_id, message.receiver_id)

        # Always emit the send event (even if it will be filtered)
        self._emit(
            {
                "agent_id": message.sender_id,
                "event_type": "message_sent",
                "arguments": {
                    "receiver": message.receiver_id,
                    "content_length": len(message.content),
                    "content_tag": message.content_tag,
                    "content_preview": message.content[:200],
                },
                "source_event_id": message.source_event_id,
                "content_tag": message.content_tag,
                "risk": "none",
            }
        )

        if edge not in self._allowed_edges:
            # Route not permitted by topology
            self._emit(
                {
                    "agent_id": message.sender_id,
                    "event_type": "message_filtered",
                    "arguments": {
                        "receiver": message.receiver_id,
                        "reason": "edge_not_in_topology",
                    },
                    "risk": "medium",
                    "content_tag": "system",
                }
            )
            return False

        # Deliver — record in log and emit receipt
        self._message_log.append(message)

        self._emit(
            {
                "agent_id": message.receiver_id,
                "event_type": "message_received",
                "arguments": {
                    "sender": message.sender_id,
                    "content_length": len(message.content),
                    "content_tag": message.content_tag,
                    "content_preview": message.content[:200],
                },
                "source_event_id": message.source_event_id,
                "content_tag": message.content_tag,
                "risk": "none",
            }
        )

        return True

    def get_log(self) -> List[AgentMessage]:
        """Return a copy of all delivered messages in send order."""
        return list(self._message_log)
