"""
RedGuard Lab Persistence (Mode B)
===================================

Thin Prisma layer over the three additive tables — `Experiment`, `LabRun`,
`TraceEvent` (`backend/prisma/schema.prisma`). Never reads or writes a
Mode A table (Session, ProbeEvent, Report, PolicySnapshot, CustomProbe).

Events are addressed within a run by their `core.lab.trace.TraceEvent.step`
(a small int, monotonic per run) — `sourceEventId` / `derivedFromJson` store
that step, not the DB row's own cuid `id`. This matches how the trace module,
the tool gateway, and the eventual evidence bundle all reference events (see
MULTI_AGENT_LAB_PLAN.md §6 note 1, §8).
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Make core.lab importable from backend/ (same pattern as scanner.py / app.py).
_PARENT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PARENT_DIR not in sys.path:
    sys.path.insert(0, _PARENT_DIR)
from core.lab.trace import ContentTag, EventCategory, EventCollector, EventType, TraceEvent


async def create_experiment(
    db: Any,
    *,
    name: str,
    arm_key: str,
    config: Dict[str, Any],
    versions: Dict[str, Any],
):
    return await db.experiment.create(
        data={
            "name": name,
            "armKey": arm_key,
            "configJson": json.dumps(config),
            "versionsJson": json.dumps(versions),
        }
    )


async def create_run(
    db: Any,
    *,
    experiment_id: str,
    case_id: str,
    mode: str,
    pair_id: str,
    repetition_index: int,
    baseline_run_id: Optional[str] = None,
    seed: Optional[int] = None,
):
    return await db.labrun.create(
        data={
            "experimentId": experiment_id,
            "caseId": case_id,
            "mode": mode,
            "pairId": pair_id,
            "baselineRunId": baseline_run_id,
            "repetitionIndex": repetition_index,
            "seed": seed,
            "status": "RUNNING",
        }
    )


async def finish_run(
    db: Any,
    *,
    run_id: str,
    status: str,
    verdict: Optional[Dict[str, Any]] = None,
    metrics: Optional[Dict[str, Any]] = None,
    invalid_reason: Optional[str] = None,
    cee_before: Optional[Dict[str, Any]] = None,
    cee_after: Optional[Dict[str, Any]] = None,
):
    return await db.labrun.update(
        where={"id": run_id},
        data={
            "status": status,
            "finishedAt": datetime.now(timezone.utc),
            "verdictJson": json.dumps(verdict) if verdict is not None else None,
            "metricsJson": json.dumps(metrics) if metrics is not None else None,
            "invalidReason": invalid_reason,
            "ceeBeforeJson": json.dumps(cee_before) if cee_before is not None else None,
            "ceeAfterJson": json.dumps(cee_after) if cee_after is not None else None,
        },
    )


async def update_verdict(db: Any, *, run_id: str, verdict: Dict[str, Any]):
    """Replace a finished run's verdict and nothing else — the rescoring pass
    that runs once all of its case's clean repetitions are in."""
    return await db.labrun.update(where={"id": run_id}, data={"verdictJson": json.dumps(verdict)})


def _event_to_row(run_id: str, event: TraceEvent) -> Dict[str, Any]:
    return {
        "runId": run_id,
        "step": event.step,
        "timestamp": event.timestamp,
        "agentId": event.agent_id,
        "category": event.category.value,
        "eventType": event.event_type.value,
        "tool": event.tool,
        "argumentsJson": json.dumps(event.arguments) if event.arguments is not None else None,
        "resultJson": json.dumps(event.result) if event.result is not None else None,
        "authorized": event.authorized,
        "sourceEventId": str(event.source_event_id) if event.source_event_id is not None else None,
        "derivedFromJson": json.dumps(list(event.derived_from)),
        "contentTag": event.content_tag.value if event.content_tag else None,
        "risk": event.risk,
        "metadataJson": json.dumps(event.metadata) if event.metadata is not None else None,
    }


async def persist_events(db: Any, *, run_id: str, collector: EventCollector) -> int:
    """Insert every event currently in `collector` under `run_id`.

    Returns the number of rows inserted. Safe to call once per run after the
    run finishes — this module does not do incremental/streaming inserts.
    """
    events = collector.events
    if not events:
        return 0
    await db.traceevent.create_many(data=[_event_to_row(run_id, e) for e in events])
    return len(events)


def _row_to_event(row: Any) -> TraceEvent:
    return TraceEvent(
        step=row.step,
        category=EventCategory(row.category),
        event_type=EventType(row.eventType),
        timestamp=row.timestamp,
        agent_id=row.agentId,
        tool=row.tool,
        arguments=json.loads(row.argumentsJson) if row.argumentsJson else None,
        result=json.loads(row.resultJson) if row.resultJson else None,
        authorized=row.authorized,
        source_event_id=int(row.sourceEventId) if row.sourceEventId is not None else None,
        derived_from=tuple(json.loads(row.derivedFromJson)) if row.derivedFromJson else (),
        content_tag=ContentTag(row.contentTag) if row.contentTag else None,
        risk=row.risk,
        metadata=json.loads(row.metadataJson) if row.metadataJson else None,
    )


async def load_run_events(db: Any, run_id: str) -> List[TraceEvent]:
    """Ordered replay of one run's trace, reconstructed as `TraceEvent`s."""
    rows = await db.traceevent.find_many(where={"runId": run_id}, order={"step": "asc"})
    return [_row_to_event(row) for row in rows]


async def load_run_collector(db: Any, run_id: str) -> EventCollector:
    """One run's trace as an `EventCollector`, ready for `evaluate()`.

    This is what makes offline replay possible (§17): a stored run can be
    re-evaluated without re-running it, so a metric or verdict change can be
    checked against past results instead of silently rewriting them.
    """
    return EventCollector.from_events(run_id, await load_run_events(db, run_id))


# ─────────────────────────────────────────────────────────────────────────────
# Reads for the API surface (§13)
# ─────────────────────────────────────────────────────────────────────────────

async def list_experiments(db: Any, limit: int = 50) -> List[Any]:
    return await db.experiment.find_many(order={"createdAt": "desc"}, take=limit)


async def get_experiment(db: Any, experiment_id: str) -> Optional[Any]:
    return await db.experiment.find_unique(where={"id": experiment_id})


async def list_runs(db: Any, experiment_id: str) -> List[Any]:
    return await db.labrun.find_many(
        where={"experimentId": experiment_id},
        order=[{"repetitionIndex": "asc"}, {"startedAt": "asc"}],
    )


async def get_run(db: Any, run_id: str) -> Optional[Any]:
    return await db.labrun.find_unique(where={"id": run_id})


async def get_pair_runs(db: Any, pair_id: str) -> List[Any]:
    """Both halves of one repetition. The ATTACK row's verdict is only
    meaningful beside its CLEAN baseline, so they are fetched together.
    """
    return await db.labrun.find_many(where={"pairId": pair_id}, order={"mode": "asc"})


async def set_baseline(db: Any, *, run_id: str, baseline_run_id: str) -> Any:
    """Point an ATTACK run at the CLEAN run it is paired with.

    Recorded on the row rather than inferred from `pairId` at read time
    because every baseline-relative definition in §9 depends on it, and an
    inferred pairing would silently pick a wrong baseline if a pair ever
    ended up with more than two rows.
    """
    return await db.labrun.update(
        where={"id": run_id}, data={"baselineRunId": baseline_run_id}
    )


# ─────────────────────────────────────────────────────────────────────────────
# Which runs count (shared by the API and the sweep CLI)
# ─────────────────────────────────────────────────────────────────────────────

def completed_attack_runs(runs: List[Any]) -> List[Any]:
    """ATTACK runs whose pair completed without a harness error, one per pair.

    Two defects met here. A pair whose run hit a harness error (a timeout,
    an exhausted retry budget) was stored as FAILED *with a verdict* — and
    the aggregation read every ATTACK row with a verdict, so a truncated run
    scored as an attack that failed. Then resume re-ran the FAILED pair and
    added a second ATTACK row under the same `pair_id`, counting it twice.
    Only COMPLETED rows count, and a pair contributes its latest one.
    """
    latest: Dict[str, Any] = {}
    for run in runs:
        if run.mode != "ATTACK" or run.status != "COMPLETED" or not run.verdictJson:
            continue
        current = latest.get(run.pairId)
        if current is None or (run.finishedAt or run.startedAt) >= (current.finishedAt or current.startedAt):
            latest[run.pairId] = run
    return sorted(latest.values(), key=lambda r: (r.caseId, r.repetitionIndex))


def failed_pair_ids(runs: List[Any]) -> List[str]:
    """Pairs with no COMPLETED attack run — excluded, and reported as such."""
    completed = {r.pairId for r in completed_attack_runs(runs)}
    return sorted({r.pairId for r in runs if r.pairId not in completed})


async def completed_pairs(db: Any, experiment_id: str) -> set:
    """`pair_id`s already done — what a resumed experiment skips."""
    return {r.pairId for r in completed_attack_runs(await list_runs(db, experiment_id))}


async def abandon_stale_runs(db: Any, experiment_id: str) -> int:
    """Mark RUNNING rows of an experiment FAILED before it is resumed.

    A run is RUNNING only while its process is executing it. Anything still
    RUNNING when an experiment is (re)started belongs to a stream that
    disconnected or a sweep that died, and would otherwise read as
    in-progress forever.
    """
    stale = await db.labrun.find_many(where={"experimentId": experiment_id, "status": "RUNNING"})
    for run in stale:
        await db.labrun.update(
            where={"id": run.id},
            data={
                "status": "FAILED",
                "finishedAt": datetime.now(timezone.utc),
                "invalidReason": "abandoned: the run was interrupted before it finished",
            },
        )
    return len(stale)
