"""
Tests for orchestrator components: Topology, MessageBus, ToolGateway, EventCollector.

All synchronous. No LLM calls. No external I/O.
"""
from __future__ import annotations

import sys
import os
from typing import Any, Dict, List

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from cee.state import CEEState
from orchestrator.topology import TopologyConfig, AgentConfig
from orchestrator.message_bus import MessageBus, AgentMessage
from orchestrator.tool_gateway import ToolGateway
from tracing.collector import EventCollector
from tracing.schema import TraceEvent, EVENT_TYPES, CONTENT_TAGS


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_linear_topology() -> TopologyConfig:
    """Build a standard linear A→B→C topology for tests."""
    agents = [
        AgentConfig(
            agent_id="agent_a", role="researcher", system_prompt="Research.",
            allowed_tools=["web_search"], allowed_file_paths=["data/"],
            denied_file_paths=["restricted/"], allowed_db_keys=[], denied_db_keys=[],
        ),
        AgentConfig(
            agent_id="agent_b", role="validator", system_prompt="Validate.",
            allowed_tools=["file_read"], allowed_file_paths=["data/"],
            denied_file_paths=["restricted/"], allowed_db_keys=[], denied_db_keys=["restricted:"],
        ),
        AgentConfig(
            agent_id="agent_c", role="executor", system_prompt="Execute.",
            allowed_tools=["db_query"], allowed_file_paths=[],
            denied_file_paths=["restricted/"], allowed_db_keys=[], denied_db_keys=["restricted:"],
        ),
    ]
    return TopologyConfig(
        topology_id="linear_test",
        description="Test linear topology",
        agents=agents,
        edges=[("agent_a", "agent_b"), ("agent_b", "agent_c")],
        defense_variant="permissive",
    )


def _collect_events() -> tuple[List[Dict[str, Any]], Any]:
    events: List[Dict[str, Any]] = []

    def emit(evt: Dict[str, Any]) -> None:
        events.append(evt)

    return events, emit


def _make_cee_state() -> CEEState:
    return CEEState(
        filesystem={"data/report.txt": "content"},
        web_results={"research": ["Finding A"]},
        database={"config:pipeline": "30", "restricted:secret": "NO"},
    )


# ── TopologyConfig ─────────────────────────────────────────────────────────────

class TestTopologyConfig:
    def test_valid_topology_passes_validation(self):
        topo = _make_linear_topology()
        errors = topo.validate()
        assert errors == [], f"Unexpected errors: {errors}"

    def test_too_few_agents_fails(self):
        topo = TopologyConfig(
            topology_id="t", description="", agents=[], edges=[], defense_variant="permissive"
        )
        errors = topo.validate()
        assert any("2 agents" in e for e in errors)

    def test_edge_unknown_source_fails(self):
        topo = _make_linear_topology()
        topo.edges.append(("ghost_agent", "agent_b"))
        errors = topo.validate()
        assert any("ghost_agent" in e for e in errors)

    def test_self_loop_fails(self):
        topo = _make_linear_topology()
        topo.edges.append(("agent_a", "agent_a"))
        errors = topo.validate()
        assert any("Self-loop" in e or "self-loop" in e.lower() for e in errors)

    def test_invalid_defense_variant_fails(self):
        topo = _make_linear_topology()
        topo.defense_variant = "offensive"
        errors = topo.validate()
        assert any("defense_variant" in e for e in errors)

    def test_get_downstream(self):
        topo = _make_linear_topology()
        assert topo.get_downstream("agent_a") == ["agent_b"]
        assert topo.get_downstream("agent_c") == []

    def test_get_upstream(self):
        topo = _make_linear_topology()
        assert topo.get_upstream("agent_c") == ["agent_b"]
        assert topo.get_upstream("agent_a") == []

    def test_get_downstream_agents_bfs(self):
        topo = _make_linear_topology()
        # From agent_a, downstream = [agent_b, agent_c]
        downstream = topo.get_downstream_agents("agent_a")
        assert "agent_b" in downstream
        assert "agent_c" in downstream
        assert "agent_a" not in downstream

    def test_from_dict_builds_topology(self):
        config = {
            "agents": [
                {"id": "agent_a", "role": "researcher", "tools": ["web_search"]},
                {"id": "agent_b", "role": "validator", "tools": ["file_read"]},
                {"id": "agent_c", "role": "executor", "tools": ["db_query"]},
            ],
            "edges": [
                {"source": "agent_a", "target": "agent_b"},
                {"source": "agent_b", "target": "agent_c"},
            ],
            "defense_variant": "permissive",
        }
        topo = TopologyConfig.from_dict(config)
        errors = topo.validate()
        assert errors == []
        assert len(topo.agents) == 3
        assert topo.defense_variant == "permissive"


# ── MessageBus ─────────────────────────────────────────────────────────────────

class TestMessageBus:
    def test_message_on_allowed_edge_delivered(self):
        events, emit = _collect_events()
        bus = MessageBus(allowed_edges=[("agent_a", "agent_b")], emit_event=emit)

        msg = AgentMessage(
            message_id="m1", sender_id="agent_a", receiver_id="agent_b",
            content="Hello from A", content_tag="derived",
        )
        result = bus.send(msg)

        assert result is True
        event_types = [e["event_type"] for e in events]
        assert "message_sent" in event_types
        assert "message_received" in event_types
        assert "message_filtered" not in event_types

    def test_message_on_invalid_edge_filtered(self):
        events, emit = _collect_events()
        bus = MessageBus(allowed_edges=[("agent_a", "agent_b")], emit_event=emit)

        msg = AgentMessage(
            message_id="m2", sender_id="agent_a", receiver_id="agent_c",
            content="Trying to skip B", content_tag="derived",
        )
        result = bus.send(msg)

        assert result is False
        event_types = [e["event_type"] for e in events]
        assert "message_filtered" in event_types
        assert "message_received" not in event_types

    def test_delivered_messages_in_log(self):
        events, emit = _collect_events()
        bus = MessageBus(allowed_edges=[("agent_a", "agent_b")], emit_event=emit)

        msg = AgentMessage(
            message_id="m3", sender_id="agent_a", receiver_id="agent_b",
            content="Message", content_tag="original_task",
        )
        bus.send(msg)

        assert len(bus.get_log()) == 1
        assert bus.get_log()[0].content == "Message"

    def test_filtered_messages_not_in_log(self):
        events, emit = _collect_events()
        bus = MessageBus(allowed_edges=[("agent_a", "agent_b")], emit_event=emit)

        msg = AgentMessage(
            message_id="m4", sender_id="agent_c", receiver_id="agent_a",
            content="Reverse", content_tag="derived",
        )
        bus.send(msg)

        assert len(bus.get_log()) == 0


# ── ToolGateway ────────────────────────────────────────────────────────────────

class TestToolGateway:
    def test_allowed_tool_called_successfully(self):
        state = _make_cee_state()
        events, emit = _collect_events()
        gateway = ToolGateway(state=state, emit_event=emit)

        result = gateway.call_tool(
            agent_id="agent_a",
            tool_name="web_search",
            arguments={"query": "research"},
            agent_allowed_tools=["web_search"],
            agent_allowed_file_paths=["data/"],
            agent_denied_file_paths=["restricted/"],
            agent_allowed_db_keys=[],
            agent_denied_db_keys=[],
        )

        assert "Finding A" in result

    def test_unlisted_tool_denied(self):
        state = _make_cee_state()
        events, emit = _collect_events()
        gateway = ToolGateway(state=state, emit_event=emit)

        result = gateway.call_tool(
            agent_id="agent_c",
            tool_name="web_search",  # Not in allowed list below
            arguments={"query": "test"},
            agent_allowed_tools=["db_query"],  # Only db_query allowed
            agent_allowed_file_paths=[],
            agent_denied_file_paths=[],
            agent_allowed_db_keys=[],
            agent_denied_db_keys=[],
        )

        assert "not in the authorized" in result or "not available" in result
        event_types = [e["event_type"] for e in events]
        assert "tool_denied" in event_types

    def test_unknown_tool_denied(self):
        state = _make_cee_state()
        events, emit = _collect_events()
        gateway = ToolGateway(state=state, emit_event=emit)

        result = gateway.call_tool(
            agent_id="agent_a",
            tool_name="send_email",  # Not a known CEE tool
            arguments={"to": "attacker@evil.com"},
            agent_allowed_tools=["send_email"],
            agent_allowed_file_paths=[],
            agent_denied_file_paths=[],
            agent_allowed_db_keys=[],
            agent_denied_db_keys=[],
        )

        assert "Unknown tool" in result or "denied" in result.lower()

    def test_gateway_denied_path_emits_denied(self):
        state = _make_cee_state()
        events, emit = _collect_events()
        gateway = ToolGateway(state=state, emit_event=emit)

        result = gateway.call_tool(
            agent_id="agent_a",
            tool_name="file_read",
            arguments={"path": "restricted/secret.env"},
            agent_allowed_tools=["file_read"],
            agent_allowed_file_paths=["data/"],
            agent_denied_file_paths=["restricted/"],
            agent_allowed_db_keys=[],
            agent_denied_db_keys=[],
        )

        assert "Access denied" in result
        assert any(e["event_type"] == "tool_denied" for e in events)


# ── EventCollector ─────────────────────────────────────────────────────────────

class TestEventCollector:
    def test_steps_are_sequential_and_gapless(self):
        collector = EventCollector(run_id="run-test-1")

        for event_type in ["cee_created", "agent_created", "task_assigned"]:
            collector.emit({"event_type": event_type})

        events = collector.get_events()
        steps = [e.step for e in events]
        assert steps == list(range(1, len(steps) + 1))

    def test_run_id_assigned_to_all_events(self):
        collector = EventCollector(run_id="run-999")
        collector.emit({"event_type": "experiment_started"})
        collector.emit({"event_type": "agent_created"})

        for e in collector.get_events():
            assert e.run_id == "run-999"

    def test_unknown_content_tag_defaults_to_system(self):
        collector = EventCollector(run_id="r")
        collector.emit({"event_type": "agent_created", "content_tag": "not_a_valid_tag"})
        assert collector.get_events()[0].content_tag == "system"

    def test_behavioral_subsequence_filter(self):
        collector = EventCollector(run_id="r")
        # These should appear in behavioral subsequence
        collector.emit({"event_type": "tool_requested", "agent_id": "agent_a"})
        collector.emit({"event_type": "tool_executed", "agent_id": "agent_a"})
        collector.emit({"event_type": "message_sent", "agent_id": "agent_a"})
        # These should NOT appear
        collector.emit({"event_type": "agent_step_started", "agent_id": "agent_a"})
        collector.emit({"event_type": "experiment_completed"})

        behavioral = collector.get_behavioral_subsequence(agent_id="agent_a")
        types = [e.event_type for e in behavioral]

        assert "tool_requested" in types
        assert "tool_executed" in types
        assert "message_sent" in types
        assert "agent_step_started" not in types
        assert "experiment_completed" not in types

    def test_to_dicts_serializable(self):
        collector = EventCollector(run_id="r")
        collector.emit({"event_type": "agent_created", "agent_id": "agent_a"})
        dicts = collector.to_dicts()

        import json
        json_str = json.dumps(dicts)  # Must not throw
        assert isinstance(json_str, str)
        assert len(dicts) == 1

    def test_get_events_by_agent(self):
        collector = EventCollector(run_id="r")
        collector.emit({"event_type": "task_assigned", "agent_id": "agent_a"})
        collector.emit({"event_type": "task_assigned", "agent_id": "agent_b"})
        collector.emit({"event_type": "agent_step_completed", "agent_id": "agent_a"})

        a_events = collector.get_events_by_agent("agent_a")
        assert len(a_events) == 2
        assert all(e.agent_id == "agent_a" for e in a_events)
