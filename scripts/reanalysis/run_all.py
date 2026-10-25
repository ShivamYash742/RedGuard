"""Re-analyse the stored research database and write results/reanalysis/.

    backend/.venv/bin/python scripts/reanalysis/run_all.py --db papr/research_results_combined.db

Read-only on the database (it is copied and the copy opened read-only), no model call. Every output is
stamped: "re-analysis of stored outputs; no new model runs", the code versions, and the SHA-256 of the
source database.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.reanalysis import labels  # noqa: E402
from scripts.reanalysis.common import NOTE, REPO, open_copy, stamp  # noqa: E402
from scripts.reanalysis.lab import analyse_lab  # noqa: E402
from scripts.reanalysis.scanner import analyse_scanner  # noqa: E402


def _write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _pct(block: Any) -> str:
    return "n/a" if not block else f"{block['value']:.1%} ({round(block['value'] * block['n'])}/{block['n']})"


def _num(x: Any) -> str:
    return "n/a" if x in (None, "n/a") else f"{x:.2f}"


def summary_markdown(stamp_: Dict[str, Any], lab: Dict[str, Any], scanner: Dict[str, Any]) -> str:
    out = ["# Re-analysis of the stored research results", "", f"**{NOTE}**", "",
           f"- Source: `{stamp_['source_db']}` (SHA-256 `{stamp_['source_sha256']}`)",
           f"- Generated {stamp_['generated_at']} by `scripts/reanalysis/run_all.py` at commit `{(stamp_['analysis_code_git_commit'] or 'unknown')[:10]}`",
           f"- Current code: Scanner benchmark {stamp_['scanner_versions']['benchmark_version']}, Lab evaluator {stamp_['lab_versions']['evaluator_version']}, metrics {stamp_['lab_versions']['metric_version']}",
           "", "## Lab mode: stored 1.2.0 verdicts against re-evaluated traces (evaluator and metrics 2.0.0)", "",
           "Every stored trace was evaluated again against its case's current definition, with the other clean runs of the case "
           "as baseline, as the sweep's rescore pass did. The **1.2.0 view** pools all cases from the verdicts stored at the time; "
           "the **2.0.0 view** counts only attack cases whose objective is reachable in the arm (RGM-008 and RGM-009 are controls, "
           "RGM-005 is unreachable in this arm), and adds exposure and CPR by message.", "",
           "| Model | Valid runs (1.2.0) | ASR 1.2.0 | Runs in scope (2.0.0) | ASR 2.0.0 | Exposed / in scope | ASR given exposure | CPR 1.2.0 (D) | CPR any 2.0.0 | CPR by message | Verdicts changed |",
           "|---|---|---|---|---|---|---|---|---|---|---|"]
    for e in lab["experiments"]:
        o, n = e["metric_1_2_0_stored_verdicts_all_cases_pooled"], e["metric_2_0_0_reevaluated_traces"]
        out.append(f"| {e['model']} | {o['asr']['n'] if o['asr'] else 0} | {_pct(o['asr'])} | {n['runs_in_scope']} | {_pct(n['asr'])} | "
                   f"{n['exposure']['exposed']} / {n['exposure']['valid']} | {_pct(n['exposure']['asr_given_exposure'])} | "
                   f"{_num(o['cpr'])} ({o['cpr_denominator']}) | {_num(n['cpr_any'])} ({n['cpr_denominator']}) | {_num(n['cpr_message'])} ({n['cpr_message_denominator']}) | "
                   f"{e['runs_whose_verdict_changed']} |")
    total_verdicts = sum(e["counts"]["attack_runs_with_a_stored_verdict"] for e in lab["experiments"])
    total_completed = sum(e["counts"]["attack_runs_completed"] for e in lab["experiments"])
    duplicates = [(e["model"], e["counts"]["pairs_with_two_completed_attack_rows"]) for e in lab["experiments"]
                  if e["counts"]["pairs_with_two_completed_attack_rows"]]
    out += ["", f"- Stored attack-run verdicts: **{total_verdicts}**; distinct completed attack pairs the metrics use: **{total_completed}**. "
                "The difference is a pair that a resume ran again, which left two COMPLETED attack rows (two verdicts) under one pair id: "
                + (", ".join(f"{m}: {n} pair(s)" for m, n in duplicates) if duplicates else "none")
                + ". The metrics keep the latest row per pair."]
    changed = [r for r in lab["rows"] if r["old_objective"] != r["new_objective"]]
    out.append(f"- Runs whose objective level changed: **{len(changed)}** of {len(lab['rows'])}. "
               "Per run: `lab_runs.csv`; per case, old and new objective counts: `lab_summary.json`.")
    out += ["", "## Scanner mode: what can and cannot be re-scored", "",
            "Only replies scored by words can be re-scored: the 11 attack probes that still use compliance phrases and the 10 benign "
            "controls. The other 35 attack probes are now scored from recorded tool calls or canaries; these runs never produced either, "
            "so their stored outcome is kept and **there is no 5.0.0 attack-success figure for these sessions**. Prompts were also "
            "rewritten since, so the replies answer the old prompts. Sessions with no events (a failed run) are omitted.", "",
            "### Stored (4.0.0) scoring: how much did the tie-break matter?", "",
            "Rows where a refusal phrase and a success indicator both matched were scored REFUSED. Model alone, all attack probes, pooled by agent and prompt mode:", "",
            "| Agent | Prompt | Sessions | Attacks | Compromised (refusal precedence, as stored) | Mixed rows | Compromised (success precedence) |", "|---|---|---|---|---|---|---|"]
    pooled: Dict[Any, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for s in scanner["sessions"]:
        if not s["events"]:
            continue
        t = s["stored_scoring_tiebreak_range"]
        key = (s["agent_id"], s["prompt_mode"])
        pooled[key]["sessions"] += 1
        for k in ("attacks", "compromised_refusal_precedence", "mixed_rows", "compromised_success_precedence"):
            pooled[key][k] += t[k]
    for (agent, mode), t in sorted(pooled.items()):
        out.append(f"| {agent} | {mode} | {t['sessions']} | {t['attacks']} | {t['compromised_refusal_precedence']} | {t['mixed_rows']} | {t['compromised_success_precedence']} |")
    out += ["", "### Re-scored subset (text-scored attacks and controls), per session", "",
            "| Session | Agent | Prompt | Text attacks: compromised stored | now (refusal precedence) | mixed | now (success precedence) | Controls over-refused stored | Controls now | Not re-scorable: compromised as stored |",
            "|---|---|---|---|---|---|---|---|---|---|"]
    for s in scanner["sessions"]:
        if not s["events"]:
            continue
        t, c, f = s["text_scored_attacks"], s["controls"], s["not_rescorable_attacks"]
        out.append(f"| `{s['session_id'][-15:]}` | {s['agent_id']} | {s['prompt_mode']} | {t['model_alone_compromised_old']}/{t['n']} | "
                   f"{t['model_alone_compromised_new_refusal_precedence']} | {t['mixed_rows']} | {t['model_alone_compromised_new_success_precedence']} | "
                   f"{c['over_refused_old']}/{c['n']} | {', '.join(f'{k} {v}' for k, v in sorted(c['new'].items()))} | {f['model_alone_compromised_as_stored']}/{f['n']} |")
    out += ["", "## Files", "",
            "- `lab_runs.csv`, `lab_summary.json`: the Lab comparison, one row per completed attack run / one object per experiment",
            "- `scanner_rows.csv`, `scanner_summary.json`: the Scanner re-scoring, one row per stored probe event",
            "- `labelling_sample.csv`: 56 Scanner replies and 20 Lab runs for two people to label (`scripts/reanalysis/labels.py agree`)",
            "- `STAMP.json`: versions and the source checksum", ""]
    return "\n".join(out)


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", required=True, help="the research database (a copy is analysed)")
    parser.add_argument("--out", default=str(REPO / "results" / "reanalysis"))
    args = parser.parse_args(argv)
    source, out = Path(args.db), Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    stamp_ = stamp(source)

    with open_copy(source) as conn:
        lab = analyse_lab(conn)
        scanner = analyse_scanner(conn)

    (out / "STAMP.json").write_text(json.dumps(stamp_, indent=2) + "\n")
    (out / "lab_summary.json").write_text(json.dumps({"stamp": stamp_, "experiments": lab["experiments"]}, indent=2) + "\n")
    (out / "scanner_summary.json").write_text(json.dumps({"stamp": stamp_, "sessions": scanner["sessions"]}, indent=2) + "\n")
    _write_csv(out / "lab_runs.csv", lab["rows"])
    _write_csv(out / "scanner_rows.csv", scanner["rows"])
    n = labels.export_sample(source, out / "labelling_sample.csv")
    (out / "SUMMARY.md").write_text(summary_markdown(stamp_, lab, scanner))
    print(f"wrote {out} ({len(lab['rows'])} lab runs, {len(scanner['rows'])} scanner rows, {n} labelling rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
