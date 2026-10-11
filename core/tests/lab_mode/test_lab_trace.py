"""Tests for core/lab_mode/trace.py: monotonic steps, taint closure, canary scan,
and the content-tag-is-not-a-trust-level invariant (§8 of
MULTI_AGENT_LAB_PLAN.md).
"""

from __future__ import annotations

import inspect

from core.lab_mode import tools as lab_tools
from core.lab_mode import topology as lab_topology
from core.lab_mode.trace import (
    ContentTag,
    EventCategory,
    EventCollector,
    EventType,
    canary_in,
    is_attack_derived,
)


class TestEventCollector:
    def test_step_is_monotonic(self):
        collector = EventCollector(run_id="r1")
        e0 = collector.emit(EventCategory.SYSTEM, EventType.RUN_STARTED)
        e1 = collector.emit(EventCategory.SYSTEM, EventType.CEE_LOADED)
        e2 = collector.emit(EventCategory.SYSTEM, EventType.RUN_FINISHED)
        assert [e0.step, e1.step, e2.step] == [0, 1, 2]

    def test_by_step_lookup(self):
        collector = EventCollector(run_id="r1")
        e0 = collector.emit(EventCategory.SYSTEM, EventType.RUN_STARTED)
        assert collector.by_step(e0.step) is e0
        assert collector.by_step(999) is None

    def test_to_json_round_trips_shape(self):
        collector = EventCollector(run_id="r1")
        collector.emit(EventCategory.TOOL, EventType.TOOL_REQUESTED, agent_id="A", tool="file_read")
        data = collector.to_json()
        assert data[0]["agent_id"] == "A"
        assert data[0]["event_type"] == "tool_requested"


class TestTaintClosure:
    def test_direct_artifact_event_is_attack_derived(self):
        collector = EventCollector(run_id="r1")
        planted = collector.emit(EventCategory.INJECTION, EventType.ARTIFACT_PLANTED)
        assert is_attack_derived(collector, planted.step)

    def test_transitive_chain_is_attack_derived(self):
        collector = EventCollector(run_id="r1")
        planted = collector.emit(EventCategory.INJECTION, EventType.ARTIFACT_PLANTED)
        read = collector.emit(
            EventCategory.TOOL, EventType.TOOL_EXECUTED, derived_from=(planted.step,)
        )
        output = collector.emit(
            EventCategory.AGENT, EventType.AGENT_OUTPUT, derived_from=(read.step,)
        )
        assert is_attack_derived(collector, output.step)

    def test_unrelated_event_is_not_attack_derived(self):
        collector = EventCollector(run_id="r1")
        collector.emit(EventCategory.INJECTION, EventType.ARTIFACT_PLANTED)
        clean = collector.emit(EventCategory.AGENT, EventType.AGENT_OUTPUT)
        assert not is_attack_derived(collector, clean.step)

    def test_missing_step_is_not_attack_derived(self):
        collector = EventCollector(run_id="r1")
        assert not is_attack_derived(collector, 42)


class TestCanaryScan:
    def test_present(self):
        assert canary_in("here is RG-CANARY-7f3a91 embedded", "RG-CANARY-7f3a91")

    def test_absent(self):
        assert not canary_in("nothing to see here", "RG-CANARY-7f3a91")

    def test_none_value(self):
        assert not canary_in(None, "RG-CANARY-7f3a91")


class TestLiveListener:
    def test_listener_sees_each_event_as_it_is_emitted(self):
        """How the API streams a run while it executes."""
        seen = []
        collector = EventCollector(run_id="r1", listener=seen.append)
        first = collector.emit(EventCategory.SYSTEM, EventType.RUN_STARTED)
        assert seen == [first]
        second = collector.emit(EventCategory.SYSTEM, EventType.RUN_FINISHED)
        assert seen == [first, second]


class TestContentTagsAreNotTrustLevels:
    """§8: content tags are observational labels, not trust levels — no code
    path in the gateway or the bus may branch on them. Enforced statically:
    both modules only ever *set* content_tag (as a keyword to `emit`), never
    read it back to make a decision.
    """

    def test_gateway_never_reads_content_tag(self):
        source = inspect.getsource(lab_tools)
        assert ".content_tag" not in source

    def test_bus_never_reads_content_tag(self):
        source = inspect.getsource(lab_topology)
        assert ".content_tag" not in source

    def test_content_tag_enum_is_used_for_setting_only(self):
        # Sanity check the enum itself is intact and these tags are the four from §8.
        assert {t.value for t in ContentTag} == {
            "original_task",
            "external_content",
            "derived",
            "attacker_artifact",
        }


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
