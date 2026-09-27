"""
RedGuard Mode B Sweep Driver (P7)
===================================

Executes the §11 arms unattended, persists every run, exports evidence
bundles, and prints the cross-arm comparisons that are the research output.

    python sweep.py --arms attack,attack_permissive_tools --reps 5 \
        --provider nvidia --model nvidia/nemotron-3-super-120b-a12b

    python sweep.py --scripted --reps 2            # no model, no cost
    python sweep.py --resume <experiment_id>       # continue a dead sweep
    python sweep.py --report <experiment_id>[,...] # analysis only, no runs

**Resume is the point.** A full sweep is thousands of model calls over hours.
Without resume, an upstream outage two hours in throws away everything and
the next attempt starts from zero — which in practice means the sweep never
completes and the numbers never get produced. Completed pairs are recorded in
the database, so a resumed sweep skips them and picks up where it stopped.

The database is the source of truth throughout: this script computes nothing
it does not first persist, so `--report` over the same experiments always
reproduces what the run printed.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

_PARENT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PARENT_DIR not in sys.path:
    sys.path.insert(0, _PARENT_DIR)

from prisma import Prisma

import lab_store
from lab_api import ARMS, _build_config, _outcomes
from core.lab.analysis import arm_summary, comparability_problems, compare_standard, compromise_by_agent
from core.lab.cases import case_ids, fixture_factory, load_case
from core.lab.evaluator import evaluate
from core.lab.evidence import build_bundle
from core.lab.metrics import RunOutcome
from core.lab.model_client import ModelClient, ModelConfig
from core.lab.repro import reproducibility_stamp
from core.lab.runner import ATTACK, CLEAN, DEFAULT_MAX_STEPS, ScriptedClient, run_case


# ─────────────────────────────────────────────────────────────────────────────
# Execution
# ─────────────────────────────────────────────────────────────────────────────

async def run_arm(
    db: Any,
    *,
    arm: str,
    cases: Sequence[str],
    reps: int,
    model_config: ModelConfig,
    scripted: bool,
    max_steps: int,
    experiment_id: Optional[str] = None,
    quiet: bool = False,
) -> str:
    """Execute one arm, resuming into `experiment_id` when given."""
    run_config = _build_config(arm, model_config, "linear_abc", max_steps)

    if experiment_id:
        experiment = await lab_store.get_experiment(db, experiment_id)
        if experiment is None:
            raise SystemExit(f"No experiment {experiment_id!r} to resume")
        config_data = json.loads(experiment.configJson)
        cases, reps, arm = config_data["cases"], config_data["repetitions"], config_data["arm"]
        # Everything that defines the experiment comes from its stored
        # config, never from this invocation's flags. The documented
        # `--resume <id>` carries no --provider/--model, so reading the CLI
        # silently continued a nemotron sweep on the ollama default, inside
        # the same experiment.
        stored_model = config_data.get("model") or {}
        model_config = ModelConfig.from_env(
            provider=stored_model.get("provider", "ollama"), model=stored_model.get("model"),
        )
        max_steps = config_data.get("max_steps", DEFAULT_MAX_STEPS)
        scripted = bool(config_data.get("scripted", False))
        run_config = _build_config(arm, model_config, config_data.get("topology_id", "linear_abc"), max_steps)
        print(f"  resuming with the stored config: "
              f"{'(scripted)' if scripted else f'{model_config.provider} / {model_config.model}'}, "
              f"max_steps={max_steps}")
        stale = await lab_store.abandon_stale_runs(db, experiment_id)
        if stale:
            print(f"  marked {stale} interrupted run(s) FAILED")
        done = await lab_store.completed_pairs(db, experiment_id)
        if done:
            print(f"  resuming: {len(done)} pairs already complete")
    else:
        experiment = await lab_store.create_experiment(
            db,
            name=f"sweep {arm} {datetime.now(timezone.utc):%Y-%m-%d %H:%M}",
            arm_key=arm,
            config={
                **run_config.to_dict(), "arm": arm, "cases": list(cases),
                "repetitions": reps, "scripted": scripted,
            },
            versions=reproducibility_stamp(),
        )
        experiment_id = experiment.id
        done = set()

    total = len(cases) * reps
    index = 0

    for case_id in cases:
        case = load_case(case_id)
        cee_factory = fixture_factory(case)
        client: Any = ScriptedClient(case["clean_script"]) if scripted else ModelClient(model_config)

        for rep in range(1, reps + 1):
            index += 1
            pair_id = f"{experiment_id}-{case_id}-r{rep}"
            if pair_id in done:
                continue

            prefix = f"  [{index}/{total}] {case_id} rep {rep}"
            try:
                verdict_label = await _run_pair(
                    db, experiment_id=experiment_id, case=case, cee_factory=cee_factory,
                    run_config=run_config, client=client, pair_id=pair_id, rep=rep,
                )
                if not quiet:
                    print(f"{prefix}: {verdict_label}")
            except Exception as exc:
                # One failed pair must not end a multi-hour sweep. It is
                # reported, left out of the aggregates as RUN_INVALID, and
                # the sweep continues.
                print(f"{prefix}: FAILED — {type(exc).__name__}: {exc}")

    return experiment_id


async def _run_pair(
    db: Any, *, experiment_id: str, case: Dict[str, Any], cee_factory, run_config,
    client: Any, pair_id: str, rep: int,
) -> str:
    rows, results = {}, {}
    for mode in (CLEAN, ATTACK):
        row = await lab_store.create_run(
            db, experiment_id=experiment_id, case_id=case["id"], mode=mode,
            pair_id=pair_id, repetition_index=rep,
        )
        result = await run_case(case, cee_factory(), run_config, client, mode=mode, run_id=row.id)
        await lab_store.persist_events(db, run_id=row.id, collector=result.collector)
        rows[mode], results[mode] = row, result

    await lab_store.set_baseline(db, run_id=rows[ATTACK].id, baseline_run_id=rows[CLEAN].id)

    clean, attack = results[CLEAN], results[ATTACK]
    verdict = evaluate(case, attack.collector, clean.collector)
    harness_error = attack.harness_error or clean.harness_error
    status = "FAILED" if harness_error else "COMPLETED"

    for mode, result in ((CLEAN, clean), (ATTACK, attack)):
        await lab_store.finish_run(
            db, run_id=rows[mode].id, status=status,
            verdict=verdict.to_dict() if mode == ATTACK else None,
            metrics=result.diagnostics(), invalid_reason=harness_error,
            cee_before=result.cee_before, cee_after=result.cee_after,
        )

    if harness_error:
        # Stored, but excluded from every aggregate and re-run on resume.
        return f"FAILED — {harness_error} (excluded; re-run on --resume)"
    return (
        f"{verdict.objective.level.value} · {verdict.containment.label} · "
        f"{verdict.system_outcome.value}"
        + (f" · parse_failures={attack.parse_failure_count}" if attack.parse_failure_count else "")
    )


# ─────────────────────────────────────────────────────────────────────────────
# Reporting
# ─────────────────────────────────────────────────────────────────────────────

async def _outcomes_for(db: Any, experiment_id: str) -> Tuple[str, List[RunOutcome]]:
    """The same outcomes the API aggregates (`lab_api._outcomes`): completed
    pairs only, one per pair. Harness-failed pairs are reported, not scored."""
    experiment = await lab_store.get_experiment(db, experiment_id)
    if experiment is None:
        raise SystemExit(f"No experiment {experiment_id!r}")
    outcomes, runs = await _outcomes(db, experiment_id)
    failed = lab_store.failed_pair_ids(runs)
    if failed:
        print(f"  ! {experiment_id}: {len(failed)} pair(s) excluded — harness error or interrupted")
    return experiment.armKey, outcomes


async def _check_comparable(db: Any, experiment_ids: Sequence[str]) -> None:
    configs = {}
    for experiment_id in experiment_ids:
        experiment = await lab_store.get_experiment(db, experiment_id)
        if experiment is not None:
            configs[experiment_id] = json.loads(experiment.configJson)
    errors, warnings = comparability_problems(configs)
    for warning in warnings:
        print(f"  ! {warning}")
    if errors:
        raise SystemExit(
            "These experiments differ in more than their arm and cannot be pooled or compared:\n  "
            + "\n  ".join(errors)
        )


async def export_bundles(db: Any, experiment_id: str, out_dir: Path) -> int:
    """Write one §12 evidence bundle per attacked run.

    The bundle, not the database row, is the unit of peer review — a reviewer
    with the directory can recompute every verdict without this codebase.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    experiment = await lab_store.get_experiment(db, experiment_id)
    written = 0

    # Completed pairs only — the same set the report aggregates, so every
    # bundle on disk corresponds to a row in the published numbers.
    for run in lab_store.completed_attack_runs(await lab_store.list_runs(db, experiment_id)):
        if not run.baselineRunId:
            continue
        bundle = build_bundle(
            case=load_case(run.caseId),
            attack_collector=await lab_store.load_run_collector(db, run.id),
            clean_collector=await lab_store.load_run_collector(db, run.baselineRunId),
            config=json.loads(experiment.configJson) if experiment else {},
            run_id=run.id, pair_id=run.pairId, experiment_id=experiment_id,
            arm=experiment.armKey if experiment else "unknown",
            cee_before=json.loads(run.ceeBeforeJson) if run.ceeBeforeJson else None,
            cee_after=json.loads(run.ceeAfterJson) if run.ceeAfterJson else None,
            diagnostics=json.loads(run.metricsJson) if run.metricsJson else None,
        )
        path = out_dir / f"{run.caseId}-r{run.repetitionIndex}-{run.id[:8]}.json"
        path.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
        written += 1

    return written


def _fmt(value: Any) -> str:
    if value is None:
        return "—"
    if value == "n/a":
        return "n/a"
    if isinstance(value, float):
        return f"{value * 100:.1f}%"
    return str(value)


def print_report(by_arm: Dict[str, List[RunOutcome]]) -> None:
    print("\n" + "=" * 72)
    print("ARM SUMMARIES")
    print("=" * 72)
    for arm, outcomes in by_arm.items():
        summary = arm_summary(outcomes)
        print(f"\n{arm}  (n={summary['n_valid']} valid of {summary['n_runs']})")
        if summary["n_invalid"]:
            # §21.8 — visible, never absorbed into the denominator.
            print(f"  ! {summary['n_invalid']} run(s) excluded as RUN_INVALID")
        print(f"  ICR {_fmt(summary['icr']['value'])}   ASR {_fmt(summary['asr']['value'])}"
              f"   partial {_fmt(summary['partial_rate']['value'])}")
        print(f"  CPR {_fmt(summary['cpr'])} (D={summary['cpr_denominator_size']})"
              f"   containment {_fmt(summary['containment_rate'])}")
        print(f"  objectives: {summary['objective_histogram']}")
        for agent, row in sorted(compromise_by_agent(outcomes).items()):
            print(f"    {agent}: {row}")

    comparisons = compare_standard(by_arm)
    if not comparisons:
        print("\n(no cross-arm comparison — needs at least two arms)")
        return

    print("\n" + "=" * 72)
    print("CROSS-ARM COMPARISONS (§11)")
    print("=" * 72)
    for label, result in comparisons.items():
        print(f"\n{label}: {result['variant_arm']} vs {result['baseline_arm']}")
        for metric, block in result["metrics"].items():
            if metric in ("cpr", "containment_rate"):
                print(f"  {metric:14} {_fmt(block['baseline'])} -> {_fmt(block['variant'])}")
                continue
            overlap = block["overlapping"]
            marker = "" if overlap is None else ("  [intervals overlap]" if overlap else "  [separated]")
            print(f"  {metric:14} {_fmt(block['baseline']['value'])} -> "
                  f"{_fmt(block['variant']['value'])}"
                  f"  Δ {_fmt(block['difference'])}{marker}")
    print(f"\n{comparisons[list(comparisons)[0]]['caveat']}")


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--arms", default="attack", help=f"comma-separated; valid: {','.join(ARMS)}")
    parser.add_argument("--cases", default="", help="comma-separated case ids (default: all 9)")
    parser.add_argument("--reps", type=int, default=5)
    parser.add_argument("--provider", default="ollama", choices=["ollama", "nvidia", "groq"])
    parser.add_argument("--model", default=None)
    parser.add_argument("--max-steps", type=int, default=DEFAULT_MAX_STEPS)
    parser.add_argument("--scripted", action="store_true", help="replay clean scripts; no model calls")
    parser.add_argument("--resume", default=None, help="experiment id to continue")
    parser.add_argument("--report", default=None, help="comma-separated experiment ids; analysis only")
    parser.add_argument("--export", default=None, help="directory to write evidence bundles into")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    # Explicit rather than relying on the generated client's baked-in default:
    # a sweep writes thousands of rows, and "which database did that go into?"
    # is not a question to answer afterwards. `backend/prisma/dev.db` is
    # committed demo data (CLAUDE.md), so point DATABASE_URL at a copy.
    database_url = os.getenv("DATABASE_URL")
    db = Prisma(datasource={"url": database_url} if database_url else None)
    await db.connect()
    print(f"database: {database_url or '(client default — backend/prisma/dev.db)'}")
    try:
        if args.report:
            by_arm: Dict[str, List[RunOutcome]] = {}
            report_ids = [e.strip() for e in args.report.split(",") if e.strip()]
            await _check_comparable(db, report_ids)
            for experiment_id in report_ids:
                arm, outcomes = await _outcomes_for(db, experiment_id.strip())
                by_arm.setdefault(arm, []).extend(outcomes)
                if args.export:
                    written = await export_bundles(db, experiment_id.strip(), Path(args.export))
                    print(f"exported {written} bundles from {experiment_id.strip()}")
            print_report(by_arm)
            return 0

        model_config = ModelConfig.from_env(provider=args.provider, model=args.model)
        cases = [c.strip() for c in args.cases.split(",") if c.strip()] or case_ids()
        arms = [a.strip() for a in args.arms.split(",") if a.strip()]

        if args.resume and len(arms) > 1:
            # One experiment is one arm. Looping the arms over a single
            # resumed id executed it once per arm and pooled its outcomes
            # into the report once per arm.
            raise SystemExit("--resume continues one experiment (one arm); do not combine it with several --arms")

        if args.resume:
            print(f"resume: {args.resume} — model, cases, reps and max_steps come from the stored experiment")
        else:
            print(f"model:  {'(scripted)' if args.scripted else f'{args.provider} / {model_config.model}'}")
            print(f"cases:  {len(cases)} × {args.reps} reps × {len(arms)} arm(s)")

        experiment_ids: List[str] = []
        by_arm = {}
        for arm in arms:
            print(f"\n=== arm: {arm} ===")
            experiment_id = await run_arm(
                db, arm=arm, cases=cases, reps=args.reps, model_config=model_config,
                scripted=args.scripted, max_steps=args.max_steps,
                experiment_id=args.resume, quiet=args.quiet,
            )
            experiment_ids.append(experiment_id)
            arm_key, outcomes = await _outcomes_for(db, experiment_id)
            by_arm.setdefault(arm_key, []).extend(outcomes)

            if args.export:
                written = await export_bundles(db, experiment_id, Path(args.export))
                print(f"  exported {written} evidence bundles")

        print_report(by_arm)
        print("\nexperiment ids: " + ",".join(experiment_ids))
        print("re-run the analysis any time with:  python sweep.py --report " + ",".join(experiment_ids))
        return 0
    finally:
        await db.disconnect()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
