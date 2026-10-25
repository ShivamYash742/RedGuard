"""Re-evaluate stored Lab traces with the current evaluator and metrics (2.0.0) and put the result beside
the verdicts and metrics stored at the time (evaluator and metrics 1.2.0). Read-only; no model is called.

The "1.2.0 view" is what the old code pooled: every case together, from the verdicts stored in the
database (`analysis.scope_report(...)["pooled_legacy"]`). The "2.0.0 view" re-runs `evaluate()` over each
stored trace against its case's current definition and reports the new headline (controls and unreachable
cases left out, CPR_any beside CPR_message, exposure, ASR given exposure).
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any, Dict, List, Optional, Sequence, Tuple

from core.lab_mode.analysis import headline, scope_report
from core.lab_mode.cases import load_case
from core.lab_mode.evaluator import Verdict, evaluate, verdict_from_dict
from core.lab_mode.metrics import RunOutcome, case_role, in_scope
from core.lab_mode.trace import ContentTag, EventCategory, EventCollector, EventType, TraceEvent

EVENT_COLUMNS = "step, timestamp, agent_id, category, event_type, tool, arguments_json, result_json, authorized, source_event_id, derived_from_json, content_tag, risk, metadata_json"


def load_collector(conn: sqlite3.Connection, run_id: str) -> EventCollector:
    """A stored run's trace as an EventCollector (mirrors backend/lab_mode/store._row_to_event)."""
    events: List[TraceEvent] = []
    for r in conn.execute(f"select {EVENT_COLUMNS} from lab_trace_events where run_id = ? order by step", (run_id,)):
        events.append(TraceEvent.from_dict({
            "step": r["step"], "category": r["category"], "event_type": r["event_type"],
            "agent_id": r["agent_id"], "tool": r["tool"],
            "arguments": json.loads(r["arguments_json"]) if r["arguments_json"] else None,
            "result": json.loads(r["result_json"]) if r["result_json"] else None,
            "authorized": None if r["authorized"] is None else bool(r["authorized"]),
            "source_event_id": r["source_event_id"],
            "derived_from": json.loads(r["derived_from_json"]) if r["derived_from_json"] else [],
            "content_tag": r["content_tag"], "risk": r["risk"],
            "metadata": json.loads(r["metadata_json"]) if r["metadata_json"] else None,
        }))
    return EventCollector.from_events(run_id, events)


def completed_attack_runs(runs: Sequence[sqlite3.Row]) -> List[sqlite3.Row]:
    """The store's rule (lab_mode/store.completed_attack_runs): COMPLETED attack rows with a verdict, the
    latest one per pair."""
    latest: Dict[str, sqlite3.Row] = {}
    for run in runs:
        if run["mode"] != "ATTACK" or run["status"] != "COMPLETED" or not run["verdict_json"]:
            continue
        current = latest.get(run["pair_id"])
        if current is None or (run["finished_at"] or run["started_at"]) >= (current["finished_at"] or current["started_at"]):
            latest[run["pair_id"]] = run
    return list(latest.values())


def _levels(verdict: Verdict) -> str:
    return "/".join(f"{a}:{r.level.value[:4]}" for a, r in sorted(verdict.agent_impact.items()))


def _rate(block: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not block or block.get("value") is None:
        return None
    return {"value": round(block["value"], 4), "n": block["n"],
            "ci": [round(block["ci"][0], 4), round(block["ci"][1], 4)] if block.get("ci") else None}


def analyse_experiment(conn: sqlite3.Connection, experiment: sqlite3.Row) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    config = json.loads(experiment["config_json"])
    versions = (json.loads(experiment["versions_json"]) or {}).get("versions") or {}
    arm = experiment["arm_key"]
    runs = list(conn.execute("select * from lab_runs where experiment_id = ? order by repetition_index, started_at", (experiment["id"],)))
    attack_runs = [r for r in runs if r["mode"] == "ATTACK"]
    completed = completed_attack_runs(runs)

    cases: Dict[str, Dict[str, Any]] = {}
    for r in completed:
        cases.setdefault(r["case_id"], load_case(r["case_id"]))

    # every completed clean run of a case is a baseline for the case's attack runs (the sweep's rescore pass)
    collectors: Dict[str, EventCollector] = {}

    def collector(run_id: str) -> EventCollector:
        if run_id not in collectors:
            collectors[run_id] = load_collector(conn, run_id)
        return collectors[run_id]

    clean_ids = {cid: [r["id"] for r in runs if r["case_id"] == cid and r["mode"] == "CLEAN" and r["status"] == "COMPLETED"] for cid in cases}

    old_outcomes: List[RunOutcome] = []
    new_outcomes: List[RunOutcome] = []
    rows: List[Dict[str, Any]] = []
    for r in completed:
        case = cases[r["case_id"]]
        old = verdict_from_dict(json.loads(r["verdict_json"]))
        paired = r["baseline_run_id"]
        others = [c for c in clean_ids[r["case_id"]] if c != paired] if len(clean_ids[r["case_id"]]) >= 2 else []
        new = evaluate(case, collector(r["id"]), collector(paired), baseline=[collector(c) for c in others])
        old_outcomes.append(RunOutcome(case, old, arm=arm))
        new_outcomes.append(RunOutcome(case, new, arm=arm))
        rows.append({
            "experiment_id": experiment["id"], "model": (config.get("model") or {}).get("model"),
            "case_id": r["case_id"], "repetition": r["repetition_index"], "run_id": r["id"],
            "case_role": case_role(case), "in_scope_2_0_0": in_scope(RunOutcome(case, new, arm=arm)),
            "old_objective": old.objective.level.value, "new_objective": new.objective.level.value,
            "old_agent_impact": _levels(old), "new_agent_impact": _levels(new),
            "old_system_outcome": old.system_outcome.value, "new_system_outcome": new.system_outcome.value,
            "exposure_opportunity": new.exposure["opportunity"] if new.exposure else None,
            "exposed": new.exposure["exposed"] if new.exposure else None,
            "propagation": json.dumps(new.propagation, sort_keys=True) if new.propagation is not None else None,
            "changed": (old.objective.level != new.objective.level) or (_levels(old) != _levels(new)),
        })

    valid_old = [o for o in old_outcomes if o.verdict.system_outcome.value != "RUN_INVALID"]
    valid_new = [o for o in new_outcomes if o.verdict.system_outcome.value != "RUN_INVALID"]
    legacy = scope_report(valid_old)["pooled_legacy"]
    head = headline(valid_new)
    scope = scope_report(valid_new)

    def per_case(outcomes: Sequence[RunOutcome]) -> Dict[str, Dict[str, int]]:
        table: Dict[str, Dict[str, int]] = {}
        for o in outcomes:
            levels = table.setdefault(o.case["id"], {})
            levels[o.verdict.objective.level.value] = levels.get(o.verdict.objective.level.value, 0) + 1
        return dict(sorted(table.items()))

    summary = {
        "experiment_id": experiment["id"], "name": experiment["name"], "arm": arm,
        "model": (config.get("model") or {}).get("model"), "temperature": (config.get("model") or {}).get("temperature"),
        "seed": (config.get("model") or {}).get("seed"), "repetitions": config.get("repetitions"), "cases": len(config.get("cases") or []),
        "stored_versions": {k: versions.get(k) for k in ("evaluator_version", "metric_version", "case_schema_version", "cee_version")},
        "counts": {
            "runs_total": len(runs), "attack_runs_total": len(attack_runs),
            "attack_runs_with_a_stored_verdict": sum(1 for r in attack_runs if r["verdict_json"]),
            "attack_runs_completed": len(completed),
            # a pair a resume ran again has two COMPLETED attack rows under one pair id; the metrics keep the latest
            "pairs_with_two_completed_attack_rows": sum(
                1 for pair in {r["pair_id"] for r in attack_runs}
                if sum(1 for r in attack_runs if r["pair_id"] == pair and r["status"] == "COMPLETED" and r["verdict_json"]) > 1),
            "valid_attack_runs": len(valid_new),
            "failed_runs": sum(1 for r in runs if r["status"] == "FAILED"),
        },
        "metric_1_2_0_stored_verdicts_all_cases_pooled": {
            "icr": _rate(legacy["icr"]), "asr": _rate(legacy["asr"]), "partial_rate": _rate(legacy["partial_rate"]),
            "cpr": legacy["cpr"], "cpr_denominator": legacy["cpr_denominator_size"],
        },
        "metric_2_0_0_reevaluated_traces": {
            "runs_in_scope": scope["n_in_scope"],
            "icr": _rate(head["icr"]), "asr": _rate(head["asr"]), "partial_rate": _rate(head["partial_rate"]),
            "cpr_any": head["cpr_any"], "cpr_message": head["cpr_message"],
            "cpr_denominator": head["cpr_denominator_size"], "cpr_message_denominator": head["cpr_message_denominator_size"],
            "exposure": {
                "valid": head["exposure"]["n_valid"], "opportunity": head["exposure"]["n_opportunity"], "exposed": head["exposure"]["n_exposed"],
                "asr_given_exposure": _rate(head["exposure"]["asr_given_exposure"]),
            },
            "excluded": {"controls": scope["excluded"]["n_controls"], "unreachable": scope["excluded"]["n_unreachable"]},
        },
        "objective_by_case_old": per_case(valid_old),
        "objective_by_case_new": per_case(valid_new),
        "runs_whose_verdict_changed": sum(1 for row in rows if row["changed"]),
    }
    return summary, rows


def analyse_lab(conn: sqlite3.Connection) -> Dict[str, Any]:
    summaries, all_rows = [], []
    for experiment in conn.execute("select * from lab_experiments order by created_at"):
        summary, rows = analyse_experiment(conn, experiment)
        summaries.append(summary)
        all_rows.extend(rows)
    return {"experiments": summaries, "rows": all_rows}
