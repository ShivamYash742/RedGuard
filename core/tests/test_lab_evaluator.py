"""Golden-trace tests for core/lab/evaluator.py (§16 of
MULTI_AGENT_LAB_PLAN.md). Each fixture under golden_traces/*.json is a
hand-designed (agent_impact, objective, containment, system_outcome) verdict
paired with an attack trace and a clean baseline — see
golden_traces/_generate.py for how they were built.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.lab.evaluator import evaluate, predicate_matches, verdict_from_dict, PredicateContext
from core.lab.trace import EventCollector, TraceEvent

GOLDEN_DIR = Path(__file__).parent / "golden_traces"
SCENARIOS = ["safe", "contained_at_b", "contained_by_gateway", "propagated", "critical", "cpr_undefined"]


def _load(name: str):
    data = json.loads((GOLDEN_DIR / f"{name}.json").read_text())
    attack = EventCollector.from_events(name, [TraceEvent.from_dict(e) for e in data["attack_trace"]])
    clean = EventCollector.from_events(f"{name}_clean", [TraceEvent.from_dict(e) for e in data["clean_trace"]])
    return data["case"], attack, clean, data["expected_verdict"]


class TestGoldenTraces:
    @pytest.mark.parametrize("name", SCENARIOS)
    def test_verdict_matches_expected(self, name):
        case, attack, clean, expected = _load(name)
        verdict = evaluate(case, attack, clean)

        actual_impact = {agent: r.level.value for agent, r in verdict.agent_impact.items()}
        assert actual_impact == expected["agent_impact"], name

        assert verdict.objective.level.value == expected["objective"], name
        if verdict.objective.level.value != "NOT_REACHED":
            assert verdict.objective.evidence, f"{name}: a matched objective must carry evidence event ids"

        assert verdict.containment.status == expected["containment_status"], name
        assert verdict.containment.agent == expected.get("containment_agent"), name
        assert verdict.containment.mechanism == expected.get("containment_mechanism"), name

        assert verdict.system_outcome.value == expected["system_outcome"], name

    @pytest.mark.parametrize("name", SCENARIOS)
    def test_every_agent_impact_dimension_carries_evidence_or_is_not_influenced(self, name):
        """Every verdict dimension must be traceable to event ids (§9) —
        except NOT_INFLUENCED, which by definition has none.
        """
        case, attack, clean, _ = _load(name)
        verdict = evaluate(case, attack, clean)
        for agent, result in verdict.agent_impact.items():
            if result.level.value != "NOT_INFLUENCED":
                assert result.evidence, f"{name}/{agent}: {result.level} must carry evidence"


class TestObjectivePredicatesUnsatisfiedByCleanTrace:
    """§21.7: every case's objective predicates must evaluate to NOT_REACHED
    against that case's own *clean* golden trace — otherwise the predicate
    is trivially satisfiable by normal behavior and the metric is fiction.
    Required CI check, not a guideline.
    """

    @pytest.mark.parametrize("name", SCENARIOS)
    def test_objective_not_reached_on_clean_trace(self, name):
        case, _, clean, _ = _load(name)
        # Evaluate the clean trace *as if* it were the attack trace, paired
        # against itself as baseline — a clean run must never look like it
        # reached the attacker's objective.
        verdict = evaluate(case, clean, clean)
        assert verdict.objective.level.value == "NOT_REACHED", (
            f"{name}: objective predicate is satisfiable by normal (clean) behavior"
        )


class TestPredicateMatcher:
    """Unit coverage for the leaf types + combinators independent of any
    golden trace (§15).
    """

    def _events(self, name):
        _, attack, _, _ = _load(name)
        return attack

    def test_leaf_event_type_and_agent(self):
        attack = self._events("propagated")
        ctx = PredicateContext(collector=attack, clean_events=())
        ok, ids = predicate_matches({"event_type": "tool_executed", "agent": "C"}, attack.events, ctx)
        assert ok
        assert ids

    def test_all_requires_every_child(self):
        attack = self._events("propagated")
        ctx = PredicateContext(collector=attack, clean_events=())
        ok, _ = predicate_matches(
            {"all": [{"event_type": "tool_executed", "agent": "C"}, {"event_type": "nonexistent_type_xyz"}]},
            attack.events, ctx,
        )
        # invalid event_type value never matches any real event -> all() is False
        assert not ok

    def test_any_matches_if_one_child_matches(self):
        attack = self._events("propagated")
        ctx = PredicateContext(collector=attack, clean_events=())
        ok, _ = predicate_matches(
            {"any": [{"event_type": "tool_denied"}, {"event_type": "tool_executed", "agent": "C"}]},
            attack.events, ctx,
        )
        assert ok

    def test_none_matches_if_no_child_matches(self):
        attack = self._events("propagated")
        ctx = PredicateContext(collector=attack, clean_events=())
        ok, ids = predicate_matches({"none": [{"event_type": "tool_denied"}]}, attack.events, ctx)
        assert ok
        assert ids == []

    def test_unknown_leaf_key_raises(self):
        attack = self._events("safe")
        ctx = PredicateContext(collector=attack, clean_events=())
        with pytest.raises(ValueError):
            predicate_matches({"bogus_key": "x"}, attack.events, ctx)

    def test_attack_derived_leaf(self):
        attack = self._events("propagated")
        ctx = PredicateContext(collector=attack, clean_events=())
        ok, _ = predicate_matches({"attack_derived": True, "event_type": "tool_executed", "agent": "C"}, attack.events, ctx)
        assert ok

    def test_absent_in_clean_leaf(self):
        case, attack, clean, _ = _load("contained_by_gateway")
        ctx = PredicateContext(collector=attack, clean_events=tuple(clean.events))
        # C's web_search attempt never happens in the clean trace (there, C only ever does db_query).
        ok, _ = predicate_matches(
            {"event_type": "tool_requested", "agent": "C", "tool": "web_search", "absent_in_clean": True},
            attack.events, ctx,
        )
        assert ok


class TestContainmentIsConsistentWithDownstreamCompromise:
    """Regression: the containment walk returned CONTAINED at the first
    non-COMPROMISED downstream agent without looking further along the path.

    An agent can fail the conjunctive INFLUENCED test for innocent reasons —
    it did not echo the canary, and its action signature matches its own
    clean-run behaviour — while still passing the attack along. Execution is
    sequential, so a later agent can only have been reached *through* it. The
    old walk then emitted "contained at B" beside "C compromised" in the same
    verdict, which is the safe/unsafe collapse §9 exists to prevent.
    """

    def _propagated_with_invisible_middle(self):
        case, attack, clean, _ = _load("propagated")
        verdict = evaluate(case, attack, clean)
        assert verdict.agent_impact["B"].level.value == "COMPROMISED"
        assert verdict.agent_impact["C"].level.value == "COMPROMISED"
        return case, attack, clean

    def test_downstream_compromise_outranks_a_local_non_compromise(self):
        case, attack, clean = self._propagated_with_invisible_middle()
        # Make B invisible to the compromise predicate without touching what
        # B actually did, exactly as a canary-free relay would look.
        case = json.loads(json.dumps(case))
        case["evaluation"]["compromise_predicate"]["B"] = {
            "event_type": "state_write", "agent": "B", "arg_contains": "never-happens",
        }
        verdict = evaluate(case, attack, clean)

        assert verdict.agent_impact["B"].level.value != "COMPROMISED"
        assert verdict.agent_impact["C"].level.value == "COMPROMISED"
        assert verdict.containment.status == "NOT_CONTAINED", (
            "B cannot have contained an attack that demonstrably reached C"
        )

    def test_containment_still_reported_when_nothing_downstream_is_compromised(self):
        """The fix must not swallow real containment."""
        case, attack, clean, expected = _load("contained_at_b")
        verdict = evaluate(case, attack, clean)
        assert verdict.containment.status == "CONTAINED"
        assert verdict.containment.agent == expected.get("containment_agent")

    def test_architectural_containment_at_the_last_hop_survives(self):
        """`contained_by_gateway`: C is INFLUENCED but not COMPROMISED and
        nothing follows it, so the gateway's denial is still the answer."""
        case, attack, clean, _ = _load("contained_by_gateway")
        verdict = evaluate(case, attack, clean)
        assert verdict.containment.status == "CONTAINED"
        assert verdict.containment.agent == "C"
        assert verdict.containment.mechanism == "tool_denied"


class TestVerdictSerialization:
    @pytest.mark.parametrize("name", SCENARIOS)
    def test_round_trips_through_dict(self, name):
        """Verdicts are persisted as JSON and reloaded to recompute
        aggregate metrics, so the round trip has to be lossless — including
        the evidence ids, without which a stored verdict is unauditable.
        """
        case, attack, clean, _ = _load(name)
        verdict = evaluate(case, attack, clean)
        restored = verdict_from_dict(json.loads(json.dumps(verdict.to_dict())))

        assert restored.objective == verdict.objective
        assert restored.containment == verdict.containment
        assert restored.system_outcome == verdict.system_outcome
        assert restored.agent_impact == verdict.agent_impact

    def test_dict_form_is_json_serializable_and_keeps_evidence(self):
        case, attack, clean, _ = _load("critical")
        data = evaluate(case, attack, clean).to_dict()
        json.dumps(data)
        assert data["objective"]["evidence"]
        assert data["containment"]["label"]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
