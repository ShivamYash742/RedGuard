"""
Tests for the Controlled Execution Environment (CEE).

All tests run synchronously — no external I/O, no LLM calls.
Tests verify that:
- CEEState snapshot / restore is lossless
- CEE tools only access in-memory state
- Authorization rules (allowed/denied paths) work correctly
- All tool operations emit trace events
"""
from __future__ import annotations

import json
import sys
import os
from typing import Any, Dict, List

import pytest

# Ensure backend/ is importable when running from the backend/ directory
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from cee.state import CEEState
from cee.manager import CEEManager, CEESnapshot
from cee.tools import cee_file_read, cee_web_search, cee_db_query, cee_state_write


# ── Helpers ────────────────────────────────────────────────────────────────────

def make_state() -> CEEState:
    return CEEState(
        filesystem={
            "data/report.txt": "Report contents.",
            "data/public.md": "Public info.",
            "restricted/secret.env": "API_KEY=sk-secret",
        },
        web_results={
            "research": ["Finding A.", "Finding B."],
            "security": ["CVE-2024-XXXX details."],
        },
        database={
            "user:1001": {"name": "Alice"},
            "config:pipeline": {"timeout": 30},
            "restricted:admin_key": "DO_NOT_ACCESS",
        },
    )


def _collect_events() -> tuple[List[Dict[str, Any]], Any]:
    """Return (event_list, emit_callback)."""
    events: List[Dict[str, Any]] = []

    def emit(evt: Dict[str, Any]) -> None:
        events.append(evt)

    return events, emit


# ── CEEState snapshot / restore ────────────────────────────────────────────────

class TestCEEStateSnapshot:
    def test_snapshot_roundtrip(self):
        """Snapshot then restore produces identical state."""
        state = make_state()
        snap_json = state.snapshot()
        restored = CEEState.from_snapshot(snap_json)

        assert restored.filesystem == state.filesystem
        assert restored.web_results == state.web_results
        assert restored.database == state.database
        assert restored.access_log == []  # access_log not persisted

    def test_snapshot_is_valid_json(self):
        state = make_state()
        snap_json = state.snapshot()
        parsed = json.loads(snap_json)
        assert "filesystem" in parsed
        assert "web_results" in parsed
        assert "database" in parsed

    def test_reset_from_restores_data(self):
        state = make_state()
        original_snap = state.snapshot()

        # Mutate
        state.filesystem["new_file"] = "new content"
        state.database["new_key"] = "new_value"

        # Reset
        state.reset_from(original_snap)

        assert "new_file" not in state.filesystem
        assert "new_key" not in state.database
        assert state.filesystem["data/report.txt"] == "Report contents."

    def test_reset_clears_access_log(self):
        state = make_state()
        state.access_log.append({"action": "read"})
        snap_json = state.snapshot()

        state.reset_from(snap_json)
        assert state.access_log == []

    def test_deep_copy_is_independent(self):
        state = make_state()
        copy = state.deep_copy()
        copy.filesystem["injected"] = "injected content"

        assert "injected" not in state.filesystem


# ── CEEManager ─────────────────────────────────────────────────────────────────

class TestCEEManager:
    def test_register_and_create_from_snapshot(self):
        manager = CEEManager()
        state = make_state()
        snap = CEESnapshot(
            snapshot_id="test-snap",
            description="Test snapshot",
            state_json=state.snapshot(),
        )
        manager.register_snapshot(snap)
        restored = manager.create_from_snapshot("test-snap")

        assert restored.filesystem == state.filesystem

    def test_unknown_snapshot_raises(self):
        manager = CEEManager()
        with pytest.raises(ValueError, match="Unknown snapshot"):
            manager.create_from_snapshot("nonexistent")

    def test_create_from_config(self):
        manager = CEEManager()
        state = manager.create_from_config(
            {"filesystem": {"a.txt": "hello"}, "web_results": {}, "database": {}}
        )
        assert state.filesystem["a.txt"] == "hello"


# ── cee_file_read ──────────────────────────────────────────────────────────────

class TestCEEFileRead:
    def test_read_allowed_path_returns_content(self):
        state = make_state()
        events, emit = _collect_events()

        result = cee_file_read(
            state, "agent_a", "data/report.txt",
            allowed_paths=["data/"], denied_paths=["restricted/"],
            emit_event=emit,
        )

        assert result == "Report contents."
        event_types = [e["event_type"] for e in events]
        assert "tool_requested" in event_types
        assert "tool_authorized" in event_types
        assert "tool_executed" in event_types
        assert "tool_denied" not in event_types

    def test_read_denied_path_returns_denial(self):
        state = make_state()
        events, emit = _collect_events()

        result = cee_file_read(
            state, "agent_a", "restricted/secret.env",
            allowed_paths=["data/"], denied_paths=["restricted/"],
            emit_event=emit,
        )

        assert "Access denied" in result
        event_types = [e["event_type"] for e in events]
        assert "tool_denied" in event_types
        assert "tool_executed" not in event_types

    def test_read_missing_file_returns_not_found(self):
        state = make_state()
        events, emit = _collect_events()

        result = cee_file_read(
            state, "agent_a", "data/nonexistent.txt",
            allowed_paths=["data/"], denied_paths=[],
            emit_event=emit,
        )

        assert "not found" in result.lower()

    def test_no_real_filesystem_access(self):
        """Tool must NOT read from the host filesystem."""
        state = CEEState()  # Empty CEE — no real files
        events, emit = _collect_events()

        # Even if /etc/passwd exists on host, it should not be accessible
        result = cee_file_read(
            state, "agent_a", "/etc/passwd",
            allowed_paths=[], denied_paths=[],
            emit_event=emit,
        )

        # Should be denied (empty allowed_paths = nothing allowed)
        # OR return file not found — either way, real content not returned
        real_content_not_returned = "root:x:" not in result
        assert real_content_not_returned


# ── cee_web_search ─────────────────────────────────────────────────────────────

class TestCEEWebSearch:
    def test_search_returns_matching_results(self):
        state = make_state()
        events, emit = _collect_events()

        result = cee_web_search(state, "agent_a", "research", emit)

        assert "Finding A." in result
        assert "tool_executed" in [e["event_type"] for e in events]

    def test_search_no_results(self):
        state = make_state()
        events, emit = _collect_events()

        result = cee_web_search(state, "agent_a", "zzznomatch_xyz", emit)

        assert "No results" in result

    def test_search_emits_events(self):
        state = make_state()
        events, emit = _collect_events()

        cee_web_search(state, "agent_a", "security", emit)

        types = [e["event_type"] for e in events]
        assert "tool_requested" in types
        assert "tool_authorized" in types
        assert "tool_executed" in types


# ── cee_db_query ───────────────────────────────────────────────────────────────

class TestCEEDbQuery:
    def test_query_allowed_key_returns_value(self):
        state = make_state()
        events, emit = _collect_events()

        result = cee_db_query(
            state, "agent_a", "config:pipeline",
            allowed_keys=[], denied_keys=["restricted:"],
            emit_event=emit,
        )

        assert "30" in result  # timeout value
        assert "tool_executed" in [e["event_type"] for e in events]

    def test_query_denied_key_returns_denial(self):
        state = make_state()
        events, emit = _collect_events()

        result = cee_db_query(
            state, "agent_a", "restricted:admin_key",
            allowed_keys=[], denied_keys=["restricted:"],
            emit_event=emit,
        )

        assert "Access denied" in result
        assert "tool_denied" in [e["event_type"] for e in events]

    def test_query_missing_key_returns_not_found(self):
        state = make_state()
        events, emit = _collect_events()

        result = cee_db_query(
            state, "agent_a", "nonexistent:key",
            allowed_keys=[], denied_keys=[],
            emit_event=emit,
        )

        assert "No record" in result


# ── cee_state_write ────────────────────────────────────────────────────────────

class TestCEEStateWrite:
    def test_write_stores_value(self):
        state = make_state()
        events, emit = _collect_events()

        cee_state_write(state, "agent_a", "shared:flag", "compromised", emit)

        assert state.database["shared:flag"] == "compromised"

    def test_write_emits_state_write_event(self):
        state = make_state()
        events, emit = _collect_events()

        cee_state_write(state, "agent_a", "shared:note", "test value", emit)

        assert any(e["event_type"] == "state_write" for e in events)

    def test_write_always_authorized(self):
        """State writes are always permitted (observable by design)."""
        state = make_state()
        events, emit = _collect_events()

        result = cee_state_write(state, "agent_a", "any_key", "any_value", emit)

        assert "Stored" in result
        assert not any(e["event_type"] == "tool_denied" for e in events)
