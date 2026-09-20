"""
RedGuard Topology + Message Bus
=================================

Topology-constrained inter-agent communication (§5.3 of
MULTI_AGENT_LAB_PLAN.md). `Topology` is the static authorization structure
(who may message whom, who may use which tool, who may read/write shared
state); `MessageBus` is the runtime mailbox that enforces it and emits the
trace events for every send/deny/deliver/receive.

Three events per message (`message_sent`/`message_denied`, then
`message_delivered`, then `message_received`) is deliberate: `sent` vs
`received` is exactly where containment can occur, and collapsing them loses
that distinction (§5.3).
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional, Sequence, Tuple

from .trace import ContentTag, EventCategory, EventCollector, EventType, TraceEvent


@dataclass(frozen=True)
class Topology:
    id: str
    version: str
    agents: Tuple[str, ...]
    edges: Tuple[Tuple[str, str], ...]
    tool_auth: Dict[str, FrozenSet[str]] = field(default_factory=dict)
    state_auth: Dict[str, FrozenSet[str]] = field(default_factory=dict)

    def can_send(self, src: str, dst: str) -> bool:
        return (src, dst) in self.edges

    def tool_authorized(self, agent: str, tool: str) -> bool:
        return tool in self.tool_auth.get(agent, frozenset())

    def state_authorized(self, agent: str, mode: str) -> bool:
        """`mode` is 'read' or 'write'."""
        return mode in self.state_auth.get(agent, frozenset())

    def downstream(self, agent: str) -> FrozenSet[str]:
        """Transitive closure of agents reachable from `agent` via edges.

        This is the structural eligibility set used as the CPR denominator
        (§10) — it is computed from the topology alone, independent of what
        any run actually did.
        """
        adjacency: Dict[str, List[str]] = defaultdict(list)
        for src, dst in self.edges:
            adjacency[src].append(dst)

        visited: set = set()
        queue = deque(adjacency.get(agent, []))
        while queue:
            node = queue.popleft()
            if node in visited:
                continue
            visited.add(node)
            queue.extend(adjacency.get(node, []))
        return frozenset(visited)

    def distance(self, src: str, dst: str) -> Optional[int]:
        """Shortest path length (in edges) from src to dst, or None if
        unreachable. 0 if src == dst.
        """
        if src == dst:
            return 0
        adjacency: Dict[str, List[str]] = defaultdict(list)
        for a, b in self.edges:
            adjacency[a].append(b)

        visited = {src}
        queue = deque([(src, 0)])
        while queue:
            node, dist = queue.popleft()
            for neighbor in adjacency.get(node, []):
                if neighbor == dst:
                    return dist + 1
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, dist + 1))
        return None


def linear_abc() -> Topology:
    """The MVP topology (§5.3): A -> B -> C."""
    return Topology(
        id="linear_abc",
        version="1.0.0",
        agents=("A", "B", "C"),
        edges=(("A", "B"), ("B", "C")),
        tool_auth={
            "A": frozenset({"file_read", "web_search"}),
            "B": frozenset({"db_query"}),
            "C": frozenset({"db_query"}),
        },
        state_auth={
            "A": frozenset(),
            "B": frozenset({"read"}),
            "C": frozenset({"read", "write"}),
        },
    )


class MessageBus:
    """Topology-checked mailbox. `send` enforces the edge check and emits
    `message_sent`/`message_denied` (+ `message_delivered` on success);
    `receive` drains an agent's inbox, emitting `message_received` per item.
    """

    def __init__(self, topology: Topology, collector: EventCollector):
        self.topology = topology
        self.collector = collector
        self._inboxes: Dict[str, List[Tuple[int, Any]]] = defaultdict(list)

    def send(
        self,
        src: str,
        dst: str,
        payload: Any,
        *,
        derived_from: Sequence[int] = (),
    ) -> TraceEvent:
        if not self.topology.can_send(src, dst):
            return self.collector.emit(
                EventCategory.COMMUNICATION,
                EventType.MESSAGE_DENIED,
                agent_id=src,
                arguments={"to": dst, "payload": payload},
                authorized=False,
                derived_from=tuple(derived_from),
                metadata={"reason": "no_edge"},
            )

        sent = self.collector.emit(
            EventCategory.COMMUNICATION,
            EventType.MESSAGE_SENT,
            agent_id=src,
            arguments={"to": dst, "payload": payload},
            authorized=True,
            derived_from=tuple(derived_from),
            content_tag=ContentTag.DERIVED,
        )
        delivered = self.collector.emit(
            EventCategory.COMMUNICATION,
            EventType.MESSAGE_DELIVERED,
            agent_id=dst,
            source_event_id=sent.step,
            derived_from=(sent.step,),
            metadata={"from": src},
        )
        self._inboxes[dst].append((delivered.step, payload))
        return sent

    def receive(self, agent_id: str) -> List[Tuple[int, Any]]:
        """Drain and return this agent's pending inbox as
        `(message_received_step, payload)` pairs, emitting one
        `message_received` event per item.
        """
        pending = self._inboxes.pop(agent_id, [])
        received: List[Tuple[int, Any]] = []
        for delivered_step, payload in pending:
            event = self.collector.emit(
                EventCategory.COMMUNICATION,
                EventType.MESSAGE_RECEIVED,
                agent_id=agent_id,
                source_event_id=delivered_step,
                derived_from=(delivered_step,),
                content_tag=ContentTag.DERIVED,
            )
            received.append((event.step, payload))
        return received

    def has_pending(self, agent_id: str) -> bool:
        return bool(self._inboxes.get(agent_id))
