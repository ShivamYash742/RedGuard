"""
Tests for security and propagation metrics, and TDS.

All synthetic — no LLM, no CEE, no network.
"""
from __future__ import annotations

import sys
import os
from typing import Any, Dict, List
from uuid import uuid4

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from metrics.security import compute_asr, compute_icr, compute_soc
from metrics.propagation import (
    compute_propagation_rate,
    compute_propagation_depth,
    compute_downstream_coverage,
    compute_blast_radius,
    compute_containment_rate,
)
from metrics.trajectory import (
    extract_behavioral_subsequence,
    levenshtein_distance,
    compute_tds,
    compute_per_agent_tds,
)


# ── Verdict dict builder ───────────────────────────────────────────────────────

def _make_verdict(
    compromised_agents: List[str],
    entry_agent: str = "agent_a",
    downstream_total: List[str] = None,
    contained: bool = None,
    containment_layer: str = "none",
    depth: int = None,
    coverage: float = None,
) -> Dict[str, Any]:
    """Build a synthetic verdict dict matching EvidenceBundle.to_dict() format."""
    if downstream_total is None:
        downstream_total = ["agent_b", "agent_c"]

    downstream_compromised = [a for a in compromised_agents if a in downstream_total]
    entry_compromised = entry_agent in compromised_agents

    _depth = depth if depth is not None else max(0, len(downstream_compromised))
    _coverage = coverage if coverage is not None else (
        len(downstream_compromised) / len(downstream_total) if downstream_total else 0.0
    )
    _contained = contained if contained is not None else (
        len(downstream_compromised) < len(downstream_total)
    )

    return {
        "agent_impacts": [
            {
                "agent_id": agent_id,
                "compromised": agent_id in compromised_agents,
                "compromise_evidence": ["evt1"] if agent_id in compromised_agents else [],
                "influenced": agent_id in compromised_agents,
            }
            for agent_id in ["agent_a", "agent_b", "agent_c"]
        ],
        "propagation": {
            "entry_agent": entry_agent,
            "entry_compromised": entry_compromised,
            "downstream_compromised": downstream_compromised,
            "downstream_total": downstream_total,
            "depth": _depth,
            "coverage": _coverage,
            "path": [entry_agent] + downstream_compromised if entry_compromised else [],
        },
        "containment": {
            "contained": _contained,
            "layer": containment_layer,
            "point": None,
        },
    }


def _make_event(event_type: str, agent_id: str = None, tool: str = None,
                arguments: dict = None) -> Dict[str, Any]:
    return {
        "event_id": str(uuid4()),
        "run_id": "test",
        "step": 1,
        "event_type": event_type,
        "agent_id": agent_id,
        "tool": tool,
        "arguments": arguments or {},
        "content_tag": "external_content",
        "authorized": True,
        "source_event_id": None,
        "result": None,
    }


# ── ASR ────────────────────────────────────────────────────────────────────────

class TestASR:
    def test_asr_all_safe(self):
        verdicts = [
            _make_verdict([]),
            _make_verdict([]),
            _make_verdict([]),
        ]
        assert compute_asr(verdicts) == 0.0

    def test_asr_all_compromised(self):
        verdicts = [
            _make_verdict(["agent_a", "agent_b", "agent_c"]),
            _make_verdict(["agent_a"]),
            _make_verdict(["agent_b"]),
        ]
        assert compute_asr(verdicts) == 1.0

    def test_asr_partial(self):
        verdicts = [
            _make_verdict(["agent_a"]),
            _make_verdict([]),
        ]
        assert compute_asr(verdicts) == 0.5

    def test_asr_per_agent(self):
        verdicts = [
            _make_verdict(["agent_a"]),
            _make_verdict(["agent_a"]),
            _make_verdict([]),
        ]
        assert compute_asr(verdicts, agent_id="agent_a") == pytest.approx(2 / 3, abs=0.001)
        assert compute_asr(verdicts, agent_id="agent_b") == 0.0

    def test_asr_empty_returns_zero(self):
        assert compute_asr([]) == 0.0


# ── SOC ────────────────────────────────────────────────────────────────────────

class TestSOC:
    def test_soc_consistent_all_same(self):
        verdicts = [
            _make_verdict(["agent_a"]),
            _make_verdict(["agent_a"]),
            _make_verdict(["agent_a"]),
        ]
        assert compute_soc(verdicts) == 1.0

    def test_soc_consistent_all_safe(self):
        verdicts = [_make_verdict([]), _make_verdict([]), _make_verdict([])]
        assert compute_soc(verdicts) == 1.0

    def test_soc_maximally_inconsistent(self):
        """3 distinct outcomes across 3 runs → SOC = 0.0"""
        verdicts = [
            _make_verdict([]),
            _make_verdict(["agent_a"]),
            _make_verdict(["agent_b"]),
        ]
        assert compute_soc(verdicts) == 0.0

    def test_soc_trivially_consistent_single_run(self):
        assert compute_soc([_make_verdict(["agent_a"])]) == 1.0

    def test_soc_empty_returns_one(self):
        assert compute_soc([]) == 1.0

    def test_soc_two_of_three_same(self):
        """2 distinct outcomes across 3 runs → SOC = 0.5"""
        verdicts = [
            _make_verdict([]),
            _make_verdict([]),
            _make_verdict(["agent_a"]),
        ]
        soc = compute_soc(verdicts)
        assert soc == pytest.approx(0.5, abs=0.001)


# ── Propagation Rate ───────────────────────────────────────────────────────────

class TestPropagationRate:
    def test_excludes_runs_where_entry_not_compromised(self):
        """Only runs where entry agent was compromised go into denominator."""
        verdicts = [
            _make_verdict([]),                    # entry safe → excluded
            _make_verdict(["agent_a", "agent_b"]),  # entry compromised, propagated
        ]
        rate = compute_propagation_rate(verdicts)
        # Only 1 qualifying run, and it propagated → rate = 1.0
        assert rate == 1.0

    def test_zero_when_entry_never_compromised(self):
        verdicts = [_make_verdict([]), _make_verdict([])]
        assert compute_propagation_rate(verdicts) == 0.0

    def test_propagation_rate_partial(self):
        verdicts = [
            _make_verdict(["agent_a", "agent_b"]),  # propagated
            _make_verdict(["agent_a"]),              # NOT propagated
        ]
        rate = compute_propagation_rate(verdicts)
        assert rate == 0.5


# ── Blast Radius (entry agent excluded) ───────────────────────────────────────

class TestBlastRadius:
    def test_blast_radius_excludes_entry_agent(self):
        """Entry agent_a is compromised but blast radius counts only downstream."""
        verdicts = [
            _make_verdict(["agent_a", "agent_b", "agent_c"]),  # entry+2 downstream
        ]
        blast = compute_blast_radius(verdicts)
        # downstream_total = [agent_b, agent_c], both compromised → coverage = 1.0
        assert blast == 1.0

    def test_blast_radius_zero_when_entry_only(self):
        verdicts = [_make_verdict(["agent_a"])]
        blast = compute_blast_radius(verdicts)
        assert blast == 0.0

    def test_blast_radius_half_when_one_of_two_downstream(self):
        verdicts = [
            _make_verdict(["agent_a", "agent_b"]),  # only agent_b downstream compromised
        ]
        blast = compute_blast_radius(verdicts)
        assert blast == pytest.approx(0.5, abs=0.001)


# ── Containment Rate ───────────────────────────────────────────────────────────

class TestContainmentRate:
    def test_containment_rate_all_contained(self):
        verdicts = [
            _make_verdict(["agent_a"], contained=True),
            _make_verdict(["agent_a"], contained=True),
        ]
        assert compute_containment_rate(verdicts) == 1.0

    def test_containment_rate_none_contained(self):
        verdicts = [
            _make_verdict(["agent_a", "agent_b", "agent_c"], contained=False),
        ]
        assert compute_containment_rate(verdicts) == 0.0

    def test_containment_rate_excludes_entry_not_compromised(self):
        verdicts = [
            _make_verdict([]),                          # entry not compromised → excluded
            _make_verdict(["agent_a"], contained=True), # entry compromised, contained
        ]
        rate = compute_containment_rate(verdicts)
        assert rate == 1.0


# ── TDS ────────────────────────────────────────────────────────────────────────

class TestTDS:
    def _web_search_event(self, agent_id: str, query: str) -> Dict[str, Any]:
        return _make_event("tool_requested", agent_id=agent_id, tool="web_search",
                           arguments={"query": query})

    def _file_read_event(self, agent_id: str, path: str) -> Dict[str, Any]:
        return _make_event("tool_executed", agent_id=agent_id, tool="file_read",
                           arguments={"path": path})

    def test_tds_identical_traces(self):
        clean = [
            self._web_search_event("agent_a", "research query"),
            self._file_read_event("agent_b", "data/report.txt"),
        ]
        # Same trace
        assert compute_tds(clean, clean) == 0.0

    def test_tds_completely_different(self):
        clean = [self._web_search_event("agent_a", "research")]
        attacked = [self._file_read_event("agent_b", "restricted/credentials.json")]
        tds = compute_tds(clean, attacked)
        assert tds > 0.0

    def test_tds_zero_when_both_empty(self):
        assert compute_tds([], []) == 0.0

    def test_tds_one_when_one_vs_one_different(self):
        """1 action vs 1 completely different action → distance=1, max_len=1 → TDS=1.0"""
        clean = [self._web_search_event("agent_a", "legitimate")]
        attacked = [self._file_read_event("agent_a", "restricted/secret.env")]
        tds = compute_tds(clean, attacked)
        assert tds == 1.0

    def test_tds_bounded_zero_to_one(self):
        import random
        clean = [self._web_search_event("agent_a", f"query_{i}") for i in range(5)]
        attacked = [self._file_read_event("agent_b", f"path_{i}") for i in range(7)]
        tds = compute_tds(clean, attacked)
        assert 0.0 <= tds <= 1.0

    def test_per_agent_tds(self):
        clean = [
            self._web_search_event("agent_a", "research"),
            self._file_read_event("agent_b", "data/report.txt"),
        ]
        attacked = [
            self._file_read_event("agent_a", "restricted/credentials.json"),  # agent_a drifted
            self._file_read_event("agent_b", "data/report.txt"),              # agent_b same
        ]
        per_agent = compute_per_agent_tds(clean, attacked, ["agent_a", "agent_b"])
        assert per_agent["agent_a"] > 0.0
        assert per_agent["agent_b"] == 0.0

    def test_behavioral_subsequence_filters_lifecycle_events(self):
        events = [
            _make_event("experiment_started"),    # NOT behavioral
            _make_event("agent_created"),          # NOT behavioral
            _make_event("tool_requested", "agent_a", "web_search", {"query": "q"}),  # behavioral
            _make_event("message_sent", "agent_a", arguments={"receiver": "agent_b"}),  # behavioral
        ]
        subseq = extract_behavioral_subsequence(events)
        assert len(subseq) == 2

    def test_levenshtein_equal_sequences(self):
        seq = ["a", "b", "c"]
        assert levenshtein_distance(seq, seq) == 0

    def test_levenshtein_empty_sequences(self):
        assert levenshtein_distance([], []) == 0
        assert levenshtein_distance(["a"], []) == 1
        assert levenshtein_distance([], ["a"]) == 1

    def test_levenshtein_one_insertion(self):
        assert levenshtein_distance(["a", "b"], ["a", "x", "b"]) == 1
