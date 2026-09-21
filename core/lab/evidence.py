"""
RedGuard Mode B Evidence Bundle
=================================

One self-contained JSON per attacked run (§12 of MULTI_AGENT_LAB_PLAN.md):
enough to audit the verdict **without the database and without this code**.

Two choices in here are deliberate and worth defending:

*The case is embedded, not referenced.* Cases change. A bundle citing
`RGM-003` tells a reviewer nothing about what RGM-003 said on the day the run
happened, and a later edit to the case silently rewrites the history of every
result that cites it.

*Both traces are embedded in full.* Every verdict definition in §9 is
baseline-relative — INFLUENCED needs `absent_in_clean`, and Trajectory Drift
without its paired clean run measures LLM nondeterminism rather than attack
effect (§21.1). A bundle carrying only the attack trace cannot be
re-evaluated; it can only be believed.

The result is that the bundle, not the database row, is the unit of peer
review: a reviewer can recompute every dimension of the verdict offline.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from .evaluator import Verdict, evaluate
from .metrics import RunOutcome, coverage, depth, refusal_detected, tds_report, trajectory_tokens
from .repro import reproducibility_stamp
from .trace import EventCollector, TraceEvent, is_attack_derived


def _event_to_dict(event: TraceEvent) -> Dict[str, Any]:
    return {
        "step": event.step,
        "category": event.category.value,
        "event_type": event.event_type.value,
        "timestamp": event.timestamp.isoformat() if hasattr(event.timestamp, "isoformat") else event.timestamp,
        "agent_id": event.agent_id,
        "tool": event.tool,
        "arguments": event.arguments,
        "result": event.result,
        "authorized": event.authorized,
        "source_event_id": event.source_event_id,
        "derived_from": list(event.derived_from),
        "content_tag": event.content_tag.value if event.content_tag else None,
        "risk": event.risk,
        "metadata": event.metadata,
    }


def derivation_chain(collector: EventCollector, step: int) -> List[int]:
    """The recorded derivation path from `step` back to its roots.

    Walks `derived_from` only. It is an *observed* derivation — what the
    harness recorded as having contributed to an event at the moment it was
    emitted — never a causal claim about the model's reasoning (§5.5's
    terminology discipline). The bundle says "traceable influence"; it does
    not say "caused".
    """
    by_step = {e.step: e for e in collector.events}
    seen: List[int] = []
    frontier = [step]
    while frontier:
        current = frontier.pop(0)
        if current in seen:
            continue
        seen.append(current)
        event = by_step.get(current)
        if event is not None:
            frontier.extend(p for p in event.derived_from if p not in seen)
    return seen


def _objective_provenance(
    collector: EventCollector, verdict: Verdict,
) -> List[Dict[str, Any]]:
    """For each event the verdict cites as evidence, the chain back to the
    artifact — the §12 `provenance` block.
    """
    cited: List[int] = list(verdict.objective.evidence)
    for impact in verdict.agent_impact.values():
        cited.extend(impact.evidence)
    cited.extend(verdict.containment.evidence)

    chains = []
    for step in sorted(set(cited)):
        chains.append({
            "event_id": step,
            "chain": derivation_chain(collector, step),
            "attack_derived": is_attack_derived(collector, step),
        })
    return chains


def _cee_diff(before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
    """Which CEE keys the run added, removed or changed, per channel."""
    diff: Dict[str, Any] = {}
    for channel in ("files", "web", "db", "kv"):
        old, new = before.get(channel) or {}, after.get(channel) or {}
        changed = {
            "added": sorted(set(new) - set(old)),
            "removed": sorted(set(old) - set(new)),
            "modified": sorted(k for k in set(old) & set(new) if old[k] != new[k]),
        }
        if any(changed.values()):
            diff[channel] = changed
    return diff


def _refusal_text(events: Sequence[TraceEvent]) -> str:
    """Free text the agents emitted, for the *secondary* refusal indicator.

    §10.10 keeps this a diagnostic: no verdict dimension reads it. It is
    recorded so a reviewer can see that an agent said "I won't do that" —
    not so anything scores on having said it.
    """
    parts: List[str] = []
    for e in events:
        if isinstance(e.result, str):
            parts.append(e.result)
        if isinstance(e.arguments, dict):
            payload = e.arguments.get("payload") or e.arguments.get("content")
            if isinstance(payload, str):
                parts.append(payload)
        summary = (e.metadata or {}).get("summary")
        if isinstance(summary, str):
            parts.append(summary)
    return "\n".join(parts)


def build_bundle(
    *,
    case: Dict[str, Any],
    attack_collector: EventCollector,
    clean_collector: EventCollector,
    config: Dict[str, Any],
    run_id: str,
    pair_id: str,
    experiment_id: str,
    arm: str,
    cee_before: Optional[Dict[str, Any]] = None,
    cee_after: Optional[Dict[str, Any]] = None,
    diagnostics: Optional[Dict[str, Any]] = None,
    verdict: Optional[Verdict] = None,
) -> Dict[str, Any]:
    """Assemble the §12 bundle for one attacked run.

    `verdict` may be supplied when it was already computed (the runner path);
    otherwise it is recomputed here from the two traces — which is itself the
    property the bundle is meant to have.
    """
    verdict = verdict or evaluate(case, attack_collector, clean_collector)
    attack_events = attack_collector.events
    clean_events = clean_collector.events
    before, after = cee_before or {}, cee_after or {}

    outcome = RunOutcome(case=case, verdict=verdict)
    depths, coverages = depth([outcome]), coverage([outcome])

    # One pair yields no clean-vs-clean null, so `null` and `effect` are None
    # by construction. That is the honest result, not a gap: §10.8 says
    # TDS_attack alone is not publishable, and the null needs repetitions.
    # The experiment-level metrics endpoint computes it across a whole
    # repetition set; a single bundle records its own raw value and says so.
    drift = tds_report(
        [trajectory_tokens(attack_events)],
        [trajectory_tokens(clean_events)],
    )

    compromised = [a for a, r in verdict.agent_impact.items() if r.level.value == "COMPROMISED"]
    influenced = [a for a, r in verdict.agent_impact.items() if r.level.value != "NOT_INFLUENCED"]

    return {
        "run_id": run_id,
        "pair_id": pair_id,
        "experiment_id": experiment_id,
        "arm": arm,

        "case": case,
        "config": config,
        "versions": reproducibility_stamp(),

        "cee": {
            "fixture_id": case.get("cee_fixture"),
            "before": before,
            "after": after,
            "diff": _cee_diff(before, after),
        },

        "traces": {
            "attack_trace": [_event_to_dict(e) for e in attack_events],
            "clean_trace": [_event_to_dict(e) for e in clean_events],
        },

        "provenance": _objective_provenance(attack_collector, verdict),
        "verdict": verdict.to_dict(),

        "compromised_agents": compromised,
        "influenced_agents": influenced,
        "affected_tools": sorted({e.tool for e in attack_events if e.tool}),
        "affected_resources": sorted({
            str(v) for e in attack_events if isinstance(e.arguments, dict)
            for k, v in e.arguments.items() if k in ("path", "name", "key", "query")
        }),

        "containment": {
            "point": verdict.containment.agent,
            "mechanism": verdict.containment.mechanism,
            "status": verdict.containment.status,
        },

        "metrics": {
            "objective": verdict.objective.level.value,
            "depth": depths[0] if depths else None,
            "coverage": coverages[0] if coverages else None,
            "tds_vs_paired_clean": drift.attack,
            # Always None for a single pair — the noise floor needs repeated
            # clean runs. Carried explicitly so a reader cannot mistake
            # `tds_vs_paired_clean` for an attributable effect (§21.1).
            "tds_null": drift.null,
            "tds_effect": drift.effect,
        },

        "diagnostics": {
            **(diagnostics or {}),
            # Secondary indicator only (§10.10). Recorded beside the verdict,
            # never inside it.
            "refusal_detected": refusal_detected(_refusal_text(attack_events)),
        },
    }
