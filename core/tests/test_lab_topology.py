"""Tests for Topology + MessageBus (core/lab/topology.py)."""

from __future__ import annotations

from core.lab.topology import MessageBus, linear_abc
from core.lab.trace import EventCollector, EventType


class TestTopology:
    def test_can_send_along_edge(self):
        topo = linear_abc()
        assert topo.can_send("A", "B")
        assert topo.can_send("B", "C")

    def test_cannot_send_non_edge(self):
        topo = linear_abc()
        assert not topo.can_send("A", "C")
        assert not topo.can_send("C", "A")
        assert not topo.can_send("B", "A")

    def test_tool_authorized(self):
        topo = linear_abc()
        assert topo.tool_authorized("A", "file_read")
        assert not topo.tool_authorized("A", "db_query")
        assert topo.tool_authorized("C", "db_query")

    def test_downstream_closure(self):
        topo = linear_abc()
        assert topo.downstream("A") == frozenset({"B", "C"})
        assert topo.downstream("B") == frozenset({"C"})
        assert topo.downstream("C") == frozenset()

    def test_distance(self):
        topo = linear_abc()
        assert topo.distance("A", "A") == 0
        assert topo.distance("A", "B") == 1
        assert topo.distance("A", "C") == 2
        assert topo.distance("C", "A") is None


class TestMessageBus:
    def test_send_along_edge_delivers(self):
        topo = linear_abc()
        collector = EventCollector(run_id="r1")
        bus = MessageBus(topo, collector)

        bus.send("A", "B", {"text": "hello"})
        types = [e.event_type for e in collector.events]
        assert EventType.MESSAGE_SENT in types
        assert EventType.MESSAGE_DELIVERED in types
        assert bus.has_pending("B")

    def test_send_off_edge_denied_no_delivery(self):
        topo = linear_abc()
        collector = EventCollector(run_id="r1")
        bus = MessageBus(topo, collector)

        bus.send("A", "C", {"text": "skip B"})
        types = [e.event_type for e in collector.events]
        assert types == [EventType.MESSAGE_DENIED]
        assert not bus.has_pending("C")

    def test_receive_drains_inbox_and_emits_received(self):
        topo = linear_abc()
        collector = EventCollector(run_id="r1")
        bus = MessageBus(topo, collector)

        bus.send("A", "B", {"text": "one"})
        bus.send("A", "B", {"text": "two"})
        received = bus.receive("B")

        assert [payload for _, payload in received] == [{"text": "one"}, {"text": "two"}]
        assert not bus.has_pending("B")
        received_events = [e for e in collector.events if e.event_type == EventType.MESSAGE_RECEIVED]
        assert len(received_events) == 2

    def test_derived_from_propagates_onto_sent_event(self):
        topo = linear_abc()
        collector = EventCollector(run_id="r1")
        bus = MessageBus(topo, collector)

        sent = bus.send("A", "B", {"text": "hello"}, derived_from=(3,))
        assert sent.derived_from == (3,)

    def test_taint_chain_survives_send_and_receive(self):
        """derived_from must chain all the way through sent -> delivered ->
        received, not just onto the sent event, or taint closure silently
        breaks at every message-bus hop (§5.5).
        """
        from core.lab.trace import EventCategory as Cat, is_attack_derived
        from core.lab.trace import EventType as Type

        topo = linear_abc()
        collector = EventCollector(run_id="r1")
        bus = MessageBus(topo, collector)

        artifact = collector.emit(Cat.INJECTION, Type.ARTIFACT_PLANTED)
        sent = bus.send("A", "B", {"text": "poisoned"}, derived_from=(artifact.step,))
        received = bus.receive("B")
        received_step = received[0][0]

        delivered = [e for e in collector.events if e.event_type == Type.MESSAGE_DELIVERED][0]
        assert delivered.derived_from == (sent.step,)  # direct parent only, per hop
        assert is_attack_derived(collector, delivered.step)  # transitive closure reaches the artifact
        assert is_attack_derived(collector, received_step)


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
