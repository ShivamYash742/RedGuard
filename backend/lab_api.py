"""
RedGuard Mode B HTTP surface
==============================

The eleven endpoints of §13 (MULTI_AGENT_LAB_PLAN.md), mounted under
`/api/lab/*`. Mode A's router is untouched: this module adds endpoints, it
does not modify or wrap any existing one, and it never reads or writes a
Mode A table.

Shape, mirroring `app.py` rather than inventing a second style:

  POST /api/lab/experiments             create the row  (cf. POST /api/scan/start)
  POST /api/lab/experiments/{id}/start  execute it as a server-owned task
  POST /api/lab/experiments/{id}/stop   cancel that task
  GET  /api/lab/experiments/{id}/stream watch it, SSE — any number of viewers
  GET  /api/lab/experiments/{id}/run    start + stream in one request

Creation and execution are separate on purpose. An experiment is a durable
record of *what was configured* — arm, cases, repetitions, model, versions,
git commit — and it has to exist before any run does, so a crashed sweep is
still attributable. Execution then runs in the background: closing or
reloading the page that started it no longer stops it.

**The model is called here and only here.** Everything downstream of the
trace — evaluation, metrics, verdicts — is deterministic, so every endpoint
except execution is reproducible from the database alone.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from typing import Any, AsyncIterator, Dict, List, Optional, Set, Tuple

from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

# Same parent-path insert as app.py / scanner.py — core/ is a sibling of backend/.
_PARENT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PARENT_DIR not in sys.path:
    sys.path.insert(0, _PARENT_DIR)

from core.lab.analysis import ARMS, arm_summary, comparability_problems, compare_standard
from core.lab.cases import (
    CASES_DIR,
    FIXTURES_DIR,
    TOPOLOGIES,
    case_ids,
    fixture_factory,
    load_all_cases,
    load_case,
    load_fixture,
)
from core.lab.evaluator import _RESOURCE_ARG_KEYS, evaluate, verdict_from_dict
from core.lab.evidence import build_bundle
from core.lab.metrics import (
    asr,
    containment_histogram,
    containment_rate,
    coverage,
    cpr,
    cpr_denominator,
    depth,
    icr,
    macro_average,
    mean_coverage,
    partial_rate,
    rate_summary,
    soc,
    tds_report,
    trajectory_tokens,
    RunOutcome,
)
from core.lab.model_client import ModelClient, ModelConfig
from core.lab.repro import reproducibility_stamp
from core.lab.runner import ATTACK, CLEAN, DEFAULT_MAX_STEPS, RunConfig, ScriptedClient, run_case
from core.lab.tools import TOOLS
from core.lab.trace import EventCategory, EventType, TraceEvent

import lab_store
from database import get_db

router = APIRouter(prefix="/api/lab", tags=["lab"])

DEFAULT_REPS = 5
MAX_REPS = 25
#: Upper bound on the scripted demo's pause per step.
MAX_STEP_DELAY_MS = 5000


def _build_config(arm: str, model_config: ModelConfig, topology_id: str, max_steps: int) -> RunConfig:
    if arm not in ARMS:
        raise HTTPException(status_code=400, detail=f"Unknown arm '{arm}'. Valid: {sorted(ARMS)}")
    if topology_id not in TOPOLOGIES:
        raise HTTPException(status_code=400, detail=f"Unknown topology '{topology_id}'. Valid: {sorted(TOPOLOGIES)}")

    spec = ARMS[arm]
    topology = TOPOLOGIES[topology_id]()
    if spec["permissive_tools"]:
        topology = topology.permissive(sorted(TOOLS))

    return RunConfig(
        topology=topology,
        model=model_config,
        max_steps=max_steps,
        validation_mode=spec["validation_mode"],
    )


# ─────────────────────────────────────────────────────────────────────────────
# Catalog endpoints — all pure reads off disk, no database
# ─────────────────────────────────────────────────────────────────────────────

def _case_summary(case: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": case["id"],
        "title": case["title"],
        "family": case["attack"]["family"],
        "injection_point": case["attack"]["injection_point"],
        "channel": case["attack"]["delivery"]["channel"],
        "severity": case["severity"],
        "topology_id": case["topology_id"],
        "cee_fixture": case["cee_fixture"],
        "objective": case["objective"]["description"],
        "eligible_downstream_agents": case["eligibility"]["eligible_downstream_agents"],
        "expected_path": case["eligibility"]["expected_path"],
        "case_version": case["case_version"],
    }


@router.get("/cases")
async def list_cases():
    return {"cases": [_case_summary(c) for c in load_all_cases()], "total": len(case_ids())}


@router.get("/cases/{case_id}")
async def get_case(case_id: str):
    try:
        return load_case(case_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"No case '{case_id}'")
    except ValueError as exc:  # fails validation — a 500 would hide why
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/topologies")
async def list_topologies():
    result = []
    for topology_id, factory in TOPOLOGIES.items():
        topology = factory()
        result.append({
            "id": topology.id,
            "version": topology.version,
            "agents": list(topology.agents),
            "edges": [list(e) for e in topology.edges],
            "tool_auth": {a: sorted(t) for a, t in topology.tool_auth.items()},
            "state_auth": {a: sorted(m) for a, m in topology.state_auth.items()},
        })
    return {"topologies": result, "tools": sorted(TOOLS)}


@router.get("/fixtures")
async def list_fixtures():
    fixtures = []
    for path in sorted(FIXTURES_DIR.glob("*.json")):
        cee = load_fixture(path.stem)
        fixtures.append({
            "fixture_id": path.stem,
            "files": sorted(cee.files),
            "web": sorted(cee.web),
            "db": sorted(cee.db),
            "kv": sorted(cee.kv),
        })
    return {"fixtures": fixtures}


@router.get("/arms")
async def list_arms():
    """Not in §13's table, but the UI cannot offer an arm it has to hardcode."""
    return {"arms": [{"key": k, **{kk: vv for kk, vv in v.items()}} for k, v in ARMS.items()]}


# ─────────────────────────────────────────────────────────────────────────────
# Experiments
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/experiments")
async def create_experiment(request: Request):
    body = await request.json()

    arm = body.get("arm", "attack")
    selected = body.get("cases") or case_ids()
    reps = int(body.get("repetitions", DEFAULT_REPS))
    topology_id = body.get("topology_id", "linear_abc")
    max_steps = int(body.get("max_steps", DEFAULT_MAX_STEPS))

    if not 1 <= reps <= MAX_REPS:
        raise HTTPException(status_code=400, detail=f"repetitions must be between 1 and {MAX_REPS}")

    scripted = bool(body.get("scripted", False))
    step_delay_ms = int(body.get("step_delay_ms") or 0)
    if not 0 <= step_delay_ms <= MAX_STEP_DELAY_MS:
        raise HTTPException(status_code=400, detail=f"step_delay_ms must be between 0 and {MAX_STEP_DELAY_MS}")

    unknown = [c for c in selected if c not in case_ids()]
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown case ids: {unknown}")

    try:
        model_config = ModelConfig.from_env(
            provider=body.get("provider", "ollama"), model=body.get("model"),
        )
    except ValueError as exc:  # unknown provider — the caller's mistake, not ours
        raise HTTPException(status_code=400, detail=str(exc))

    # Validates arm and topology, and fails before anything is persisted.
    config = _build_config(arm, model_config, topology_id, max_steps)

    db = await get_db()
    experiment = await lab_store.create_experiment(
        db,
        name=body.get("name") or f"{arm} × {len(selected)} cases × {reps}",
        arm_key=arm,
        config={
            **config.to_dict(),
            "arm": arm,
            "cases": selected,
            "repetitions": reps,
            "scripted": scripted,
            # Slows the scripted replay so a demo can be watched; a model
            # run is slow enough on its own.
            **({"step_delay_ms": step_delay_ms} if scripted and step_delay_ms else {}),
        },
        versions=reproducibility_stamp(),
    )
    return {
        "experiment_id": experiment.id,
        "arm": arm,
        "cases": selected,
        "repetitions": reps,
        "total_runs": len(selected) * reps * 2,
        "config": config.to_dict(),
    }


def _experiment_row(experiment: Any, runs: Optional[List[Any]] = None) -> Dict[str, Any]:
    config = json.loads(experiment.configJson)
    payload = {
        "experiment_id": experiment.id,
        "name": experiment.name,
        "arm": experiment.armKey,
        "config": config,
        "versions": json.loads(experiment.versionsJson),
        "created_at": experiment.createdAt.isoformat(),
        # Runs per run, so `/lab` can badge a live experiment from any tab.
        "live": _JOBS[experiment.id].progress if experiment.id in _JOBS else None,
    }
    if runs is not None:
        payload["runs"] = [_run_summary(r) for r in runs]
        payload["run_count"] = len(runs)
        payload["status_counts"] = _count_by(runs, lambda r: r.status)
    return payload


def _count_by(rows: List[Any], key) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for row in rows:
        counts[key(row)] = counts.get(key(row), 0) + 1
    return counts


def _run_summary(run: Any) -> Dict[str, Any]:
    verdict = json.loads(run.verdictJson) if run.verdictJson else None
    return {
        "run_id": run.id,
        "case_id": run.caseId,
        "mode": run.mode,
        "pair_id": run.pairId,
        "baseline_run_id": run.baselineRunId,
        "repetition_index": run.repetitionIndex,
        "status": run.status,
        "invalid_reason": run.invalidReason,
        "started_at": run.startedAt.isoformat(),
        "finished_at": run.finishedAt.isoformat() if run.finishedAt else None,
        "verdict": verdict,
        "metrics": json.loads(run.metricsJson) if run.metricsJson else None,
    }


@router.get("/experiments")
async def list_experiments():
    db = await get_db()
    rows = await lab_store.list_experiments(db)
    return {"experiments": [_experiment_row(r) for r in rows]}


@router.get("/experiments/{experiment_id}")
async def get_experiment(experiment_id: str):
    db = await get_db()
    experiment = await lab_store.get_experiment(db, experiment_id)
    if experiment is None:
        raise HTTPException(status_code=404, detail=f"No experiment '{experiment_id}'")
    runs = await lab_store.list_runs(db, experiment_id)
    return _experiment_row(experiment, runs)


# ─────────────────────────────────────────────────────────────────────────────
# Execution — SSE
# ─────────────────────────────────────────────────────────────────────────────

def _client_for(config_data: Dict[str, Any], model_config: ModelConfig, case: Dict[str, Any]) -> Any:
    """`scripted: true` replays each case's own `clean_script` instead of
    calling a model. It exists so the whole pipeline — plant, run, trace,
    evaluate, persist, stream — can be exercised end to end with no network,
    no budget and no nondeterminism, which is also how the API is tested.
    """
    if config_data.get("scripted"):
        return ScriptedClient(case["clean_script"], delay_ms=config_data.get("step_delay_ms", 0))
    return ModelClient(model_config)


def _event_payload(run_id: str, event: TraceEvent) -> Dict[str, Any]:
    """One `trace_event` SSE frame. `resource` is what the action reached for
    (the evaluator's own resource keys) and `reason` why it was refused, so
    the live board can say `B → db_query(customer_pii) · refused` rather than
    only that B acted.

    `timestamp`, `latency_ms` (one model call) and `turn` / `max_steps` are
    what the agent cards and the swimlane time: "B thinking 12 s, step 3 of
    10". `reason` is also set on `agent_finished`, which says why the agent
    stopped (`finish`, `parse_failure`, `max_steps`)."""
    args = event.arguments if isinstance(event.arguments, dict) else {}
    meta = event.metadata or {}
    resource = {k: args[k] for k in _RESOURCE_ARG_KEYS if isinstance(args.get(k), (str, int, float))}
    if event.category == EventCategory.INJECTION:
        resource = {k: args.get(k) or meta.get(k) for k in ("channel", "location") if args.get(k) or meta.get(k)}
    explains = event.authorized is False or event.event_type == EventType.AGENT_FINISHED
    return {
        "run_id": run_id,
        "step": event.step,
        "timestamp": event.timestamp.isoformat(),
        "category": event.category.value,
        "event_type": event.event_type.value,
        "agent_id": event.agent_id,
        "tool": event.tool,
        "authorized": event.authorized,
        "derived_from": list(event.derived_from),
        "content_tag": event.content_tag.value if event.content_tag else None,
        "resource": resource or None,
        "reason": meta.get("reason") if explains else None,
        "latency_ms": meta.get("latency_ms"),
        "turn": meta.get("turn"),
        "max_steps": meta.get("max_steps"),
    }


async def _run_streaming(case: Dict[str, Any], cee: Any, run_config: RunConfig, client: Any, *, mode: str, run_id: str):
    """Run one case, yielding each `TraceEvent` the moment it is emitted and
    the `RunResult` last.

    Streaming only after the run finished meant minutes of silence per run
    against a real model, then a burst — nothing a live view could follow.
    If the consumer goes away mid-run the run is cancelled rather than left
    spending model calls nobody will see.
    """
    queue: asyncio.Queue = asyncio.Queue()
    task = asyncio.create_task(
        run_case(case, cee, run_config, client, mode=mode, run_id=run_id, on_event=queue.put_nowait)
    )
    try:
        while not (task.done() and queue.empty()):
            getter = asyncio.ensure_future(queue.get())
            await asyncio.wait({getter, task}, return_when=asyncio.FIRST_COMPLETED)
            if getter.done():
                yield getter.result()
            else:
                getter.cancel()
        yield await task
    finally:
        if not task.done():
            task.cancel()


async def rescore_case(db: Any, experiment_id: str, case: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Re-evaluate every completed attack run of `case` against all of the
    case's completed clean runs in this experiment, not only its own pair.

    Runs once all of a case's repetitions are in, so each verdict of the case
    is judged against the same N-run baseline — independent of the order the
    pairs happened to execute in, and of a resume. Fewer than two clean runs
    leave nothing to pool, and the pair-time verdicts stand.
    """
    runs = [
        r for r in await lab_store.list_runs(db, experiment_id)
        if r.caseId == case["id"] and r.status == "COMPLETED"
    ]
    cleans = {r.id: await lab_store.load_run_collector(db, r.id) for r in runs if r.mode == CLEAN}
    if len(cleans) < 2:
        return []

    rescored: List[Dict[str, Any]] = []
    for run in runs:
        if run.mode != ATTACK or run.baselineRunId not in cleans:
            continue
        verdict = evaluate(
            case, await lab_store.load_run_collector(db, run.id), cleans[run.baselineRunId],
            baseline=[c for run_id, c in cleans.items() if run_id != run.baselineRunId],
        ).to_dict()
        await lab_store.update_verdict(db, run_id=run.id, verdict=verdict)
        rescored.append({"run_id": run.id, "verdict": verdict})
    return rescored


async def _execute(experiment: Any):
    """Run every (case × repetition) pair, yielding SSE payloads as it goes.

    Persistence happens per run, not at the end: a sweep is thousands of
    model calls, and a crash two hours in must not discard what already
    completed.

    Re-running an experiment resumes it: pairs that already completed are
    skipped, and runs left RUNNING by an interrupted stream are marked
    FAILED. It used to start again from pair 1 — and the browser re-issues
    this request by itself after a dropped connection, so one blip meant a
    second, duplicate execution of the whole experiment.
    """
    db = await get_db()
    await lab_store.abandon_stale_runs(db, experiment.id)
    done = await lab_store.completed_pairs(db, experiment.id)
    config_data = json.loads(experiment.configJson)
    selected = config_data["cases"]
    reps = config_data["repetitions"]

    model_config = ModelConfig.from_env(
        provider=(config_data.get("model") or {}).get("provider", "ollama"),
        model=(config_data.get("model") or {}).get("model"),
    )
    run_config = _build_config(
        config_data["arm"], model_config,
        config_data.get("topology_id", "linear_abc"),
        config_data.get("max_steps", DEFAULT_MAX_STEPS),
    )

    total_runs = len(selected) * reps * 2
    yield {"event": "experiment_started", "data": {
        "experiment_id": experiment.id,
        "arm": experiment.armKey,
        "cases": selected,
        "repetitions": reps,
        "total_runs": total_runs,
        "already_completed_pairs": len(done),
        # Enough for the page to lay out the agent cards before any event.
        "scripted": bool(config_data.get("scripted")),
        "model": {"provider": model_config.provider, "model": model_config.model},
        "max_steps": run_config.max_steps,
        "agents": list(run_config.topology.agents),
    }}

    # Counted per run, not per pair: against a real model one run is
    # minutes, and a bar that moves only every second run looks stuck.
    completed = 2 * len(done)
    for case_id in selected:
        case = load_case(case_id)
        cee_factory = fixture_factory(case)
        client = _client_for(config_data, model_config, case)

        for rep in range(1, reps + 1):
            pair_id = f"{experiment.id}-{case_id}-r{rep}"
            if pair_id in done:
                continue
            results: Dict[str, Any] = {}
            rows: Dict[str, Any] = {}

            for mode in (CLEAN, ATTACK):
                row = await lab_store.create_run(
                    db, experiment_id=experiment.id, case_id=case_id, mode=mode,
                    pair_id=pair_id, repetition_index=rep,
                )
                rows[mode] = row
                yield {"event": "run_started", "data": {
                    "run_id": row.id, "case_id": case_id, "mode": mode,
                    "pair_id": pair_id, "repetition_index": rep,
                    "index": completed + 1, "total_runs": total_runs,
                }}

                started = time.monotonic()
                async for item in _run_streaming(
                    case, cee_factory(), run_config, client, mode=mode, run_id=row.id,
                ):
                    if isinstance(item, TraceEvent):
                        yield {"event": "trace_event", "data": _event_payload(row.id, item)}
                    else:
                        results[mode] = item

                await lab_store.persist_events(db, run_id=row.id, collector=results[mode].collector)
                completed += 1
                result = results[mode]
                yield {"event": "run_finished", "data": {
                    "run_id": row.id, "case_id": case_id, "mode": mode, "pair_id": pair_id,
                    "duration_ms": round((time.monotonic() - started) * 1000),
                    "steps": result.step_count,
                    "parse_failures": result.parse_failure_count,
                    "harness_error": result.harness_error,
                    "progress": {"completed": completed, "total": total_runs},
                }}

            clean, attack = results[CLEAN], results[ATTACK]
            await lab_store.set_baseline(db, run_id=rows[ATTACK].id, baseline_run_id=rows[CLEAN].id)

            verdict = evaluate(case, attack.collector, clean.collector)
            # A harness failure invalidates the run rather than scoring it
            # (§9): its trace is kept for debugging, but it must not enter a
            # denominator as if it were a result.
            harness_error = attack.harness_error or clean.harness_error
            status = "FAILED" if harness_error else "COMPLETED"

            for mode, result in ((CLEAN, clean), (ATTACK, attack)):
                await lab_store.finish_run(
                    db,
                    run_id=rows[mode].id,
                    status=status,
                    verdict=verdict.to_dict() if mode == ATTACK else None,
                    metrics=result.diagnostics(),
                    invalid_reason=harness_error,
                    cee_before=result.cee_before,
                    cee_after=result.cee_after,
                )

            yield {"event": "run_verdict", "data": {
                "run_id": rows[ATTACK].id,
                "baseline_run_id": rows[CLEAN].id,
                "case_id": case_id,
                "pair_id": pair_id,
                "repetition_index": rep,
                "status": status,
                "verdict": verdict.to_dict(),
                "diagnostics": attack.diagnostics(),
                "progress": {"completed": completed, "total": total_runs},
            }}

        rescored = await rescore_case(db, experiment.id, case)
        if rescored:
            yield {"event": "case_rescored", "data": {
                "case_id": case_id,
                "baseline_runs": rescored[0]["verdict"]["baseline_runs"],
                "runs": rescored,
            }}

    yield {"event": "experiment_complete", "data": {
        "experiment_id": experiment.id, "runs_completed": completed,
    }}


class _Job:
    """One experiment executing in this process, and everyone watching it.

    The run belongs to the server, not to a request: it used to execute
    inside the browser's SSE request, so closing or reloading the tab
    stopped it and a second tab got 409. Viewers now subscribe and leave
    freely; only `stop` cancels.

    A late subscriber first gets the backlog: every event so far except the
    trace of runs already finished (their verdicts are in the backlog, their
    traces in the database), then live events.
    """

    def __init__(self, experiment: Any):
        self.experiment_id = experiment.id
        self.backlog: List[Dict[str, Any]] = []
        self.subscribers: Set[asyncio.Queue] = set()
        self.progress: Dict[str, int] = {"completed": 0, "total": 0}
        self.task = asyncio.create_task(self._run(experiment))
        # A callback, not a `finally` in `_run`: a task cancelled before its
        # first step never enters the coroutine at all.
        self.task.add_done_callback(self._close)

    def _close(self, _task: asyncio.Task) -> None:
        if _JOBS.get(self.experiment_id) is self:
            del _JOBS[self.experiment_id]
        for queue in self.subscribers:
            queue.put_nowait(None)

    def _publish(self, payload: Dict[str, Any]) -> None:
        if payload["event"] == "run_started":
            self.backlog = [p for p in self.backlog if p["event"] != "trace_event"]
        if payload["event"] == "experiment_started":
            self.progress = {"completed": 2 * payload["data"]["already_completed_pairs"], "total": payload["data"]["total_runs"]}
        if payload["event"] == "run_finished":
            self.progress = payload["data"]["progress"]
        self.backlog.append(payload)
        for queue in self.subscribers:
            queue.put_nowait(payload)

    async def _run(self, experiment: Any) -> None:
        try:
            async for payload in _execute(experiment):
                self._publish(payload)
        except asyncio.CancelledError:
            # Runs left RUNNING are marked FAILED when it is resumed.
            self._publish({"event": "experiment_stopped", "data": {"experiment_id": self.experiment_id}})
            raise
        except Exception as exc:
            # Unreported, a crash is indistinguishable from a finished sweep.
            self._publish({"event": "experiment_error", "data": {
                "experiment_id": self.experiment_id, "error": f"{type(exc).__name__}: {exc}",
            }})

    async def subscribe(self) -> AsyncIterator[Dict[str, Any]]:
        queue: asyncio.Queue = asyncio.Queue()
        for payload in self.backlog:
            queue.put_nowait(payload)
        self.subscribers.add(queue)
        try:
            while (payload := await queue.get()) is not None:
                yield payload
        finally:
            self.subscribers.discard(queue)


#: ponytail: in-process registry, so one uvicorn worker; a job queue only if
#: the backend ever runs several workers.
_JOBS: Dict[str, _Job] = {}


async def _experiment_or_404(experiment_id: str) -> Any:
    experiment = await lab_store.get_experiment(await get_db(), experiment_id)
    if experiment is None:
        raise HTTPException(status_code=404, detail=f"No experiment '{experiment_id}'")
    return experiment


def _start(experiment: Any) -> _Job:
    """Idempotent: a second start (another tab, a double click) joins the
    running job instead of executing the experiment twice into one record."""
    job = _JOBS.get(experiment.id)
    if job is None:
        job = _JOBS[experiment.id] = _Job(experiment)
    return job


def _sse(job: _Job) -> EventSourceResponse:
    async def frames():
        async for payload in job.subscribe():
            yield {"event": payload["event"], "data": json.dumps(payload["data"])}

    # `no-transform` keeps a compressing proxy from gzipping the stream: the
    # Next.js /api rewrite otherwise buffers every event inside the gzip
    # stream until the experiment ends, so a live run showed nothing live.
    return EventSourceResponse(frames(), headers={"Cache-Control": "no-store, no-transform"})


@router.post("/experiments/{experiment_id}/start")
async def start_experiment(experiment_id: str):
    experiment = await _experiment_or_404(experiment_id)
    already = experiment_id in _JOBS
    _start(experiment)
    return {"experiment_id": experiment_id, "running": True, "already_running": already}


@router.post("/experiments/{experiment_id}/stop")
async def stop_experiment(experiment_id: str):
    await _experiment_or_404(experiment_id)
    job = _JOBS.get(experiment_id)
    if job is None:
        return {"experiment_id": experiment_id, "stopped": False}
    job.task.cancel()
    # Wait for the cancellation to land, so a read straight after this
    # already sees the experiment as not running.
    await asyncio.wait({job.task})
    return {"experiment_id": experiment_id, "stopped": True}


@router.get("/experiments/{experiment_id}/stream")
async def stream_experiment(experiment_id: str):
    await _experiment_or_404(experiment_id)
    job = _JOBS.get(experiment_id)
    if job is None:
        # Not 200: an EventSource that gets an error status gives up instead
        # of reconnecting forever to an experiment that is not running.
        raise HTTPException(status_code=409, detail=f"Experiment '{experiment_id}' is not running")
    return _sse(job)


@router.get("/experiments/{experiment_id}/run")
async def run_experiment(experiment_id: str):
    """Start (or join) and stream in one request — what the sweep tests and
    older clients use. Disconnecting no longer stops the run."""
    return _sse(_start(await _experiment_or_404(experiment_id)))


async def shutdown_jobs() -> None:
    """Cancel running experiments on shutdown rather than leave their tasks
    pending on a closed loop; their RUNNING rows are failed on resume."""
    jobs = list(_JOBS.values())
    for job in jobs:
        job.task.cancel()
    if jobs:
        await asyncio.wait({job.task for job in jobs})


# ─────────────────────────────────────────────────────────────────────────────
# Metrics (§10)
# ─────────────────────────────────────────────────────────────────────────────

async def _outcomes(db: Any, experiment_id: str) -> Tuple[List[RunOutcome], List[Any]]:
    """Completed attack runs, one per pair, rebuilt as `RunOutcome`s.

    Recomputed from stored verdicts rather than by re-running the evaluator
    over stored traces: both are deterministic, and this keeps the metrics
    endpoint honest about what it is aggregating — the verdicts as recorded.

    Harness-failed pairs are excluded (`lab_store.completed_attack_runs`):
    their verdict is computed over a truncated trace and used to be scored
    as an attack that did not succeed. The sweep CLI reads outcomes through
    this same function so the two can never disagree about what counts.
    """
    runs = await lab_store.list_runs(db, experiment_id)
    outcomes = []
    for run in lab_store.completed_attack_runs(runs):
        try:
            case = load_case(run.caseId)
        except FileNotFoundError:
            continue
        outcomes.append(RunOutcome(case=case, verdict=verdict_from_dict(json.loads(run.verdictJson))))
    return outcomes, runs


@router.get("/experiments/{experiment_id}/metrics")
async def experiment_metrics(experiment_id: str):
    db = await get_db()
    experiment = await lab_store.get_experiment(db, experiment_id)
    if experiment is None:
        raise HTTPException(status_code=404, detail=f"No experiment '{experiment_id}'")

    outcomes, runs = await _outcomes(db, experiment_id)
    n = len(outcomes)
    denominator = cpr_denominator(outcomes)
    cpr_value = cpr(outcomes)

    per_case: Dict[str, Any] = {}
    for case_id in sorted({o.case["id"] for o in outcomes}):
        subset = [o for o in outcomes if o.case["id"] == case_id]
        per_case[case_id] = {
            "n": len(subset),
            "icr": icr(subset),
            "asr": asr(subset),
            "partial_rate": partial_rate(subset),
            "cpr": cpr(subset),
            # SOC needs N>=3 valid repetitions and returns None below that,
            # rather than a confident-looking 1.0 from a single run.
            "soc": soc(subset),
        }

    return {
        "experiment_id": experiment_id,
        "arm": experiment.armKey,
        "n_attack_runs": n,
        # Pairs left out because a run hit a harness error or never finished.
        # Visible, never silently absorbed (§21.8).
        "n_failed_pairs": len(lab_store.failed_pair_ids(runs)),
        "aggregate": {
            "icr": rate_summary(outcomes, icr),
            "asr": rate_summary(outcomes, asr),
            "partial_rate": rate_summary(outcomes, partial_rate),
            # CPR is "n/a" when D is empty — never 0.0 (§10.3). An empty
            # denominator means the question was never asked, not that
            # propagation never happened.
            "cpr": cpr_value,
            "cpr_denominator_size": len(denominator),
            "depth": depth(outcomes),
            "coverage": coverage(outcomes),
            "mean_coverage": mean_coverage(outcomes),
            "containment_rate": containment_rate(outcomes),
            "containment_histogram": [
                {"agent": agent, "mechanism": mechanism, "count": count}
                for (agent, mechanism), count in containment_histogram(outcomes).items()
            ],
        },
        "per_case": per_case,
        # Macro average weights every case equally. The micro figures above
        # weight by run count, so a case that happened to run more often
        # would otherwise dominate the headline (§10's aggregation note).
        "macro": {
            "icr": macro_average([c["icr"] for c in per_case.values()]),
            "asr": macro_average([c["asr"] for c in per_case.values()]),
            "partial_rate": macro_average([c["partial_rate"] for c in per_case.values()]),
        },
        "trajectory_drift": await _drift(db, runs),
        "run_counts": _count_by(runs, lambda r: r.status),
    }


async def _drift(db: Any, runs: List[Any]) -> Dict[str, Any]:
    """TDS with its null, per §10.8.

    `TDS_attack` alone is not publishable: two clean runs of the same case
    already differ, so the clean-vs-clean null is the noise floor any claimed
    drift has to clear. With fewer than two clean repetitions of a case there
    is no null, and the effect is reported as `None` rather than as the raw
    attack figure.
    """
    by_case: Dict[str, Dict[str, List[Any]]] = {}
    for run in runs:
        if run.status != "COMPLETED":
            continue
        by_case.setdefault(run.caseId, {CLEAN: [], ATTACK: []})[run.mode].append(run)

    report: Dict[str, Any] = {}
    for case_id, modes in sorted(by_case.items()):
        attack_seqs = [
            trajectory_tokens(await lab_store.load_run_events(db, r.id)) for r in modes[ATTACK]
        ]
        clean_seqs = [
            trajectory_tokens(await lab_store.load_run_events(db, r.id)) for r in modes[CLEAN]
        ]
        result = tds_report(attack_seqs, clean_seqs)
        report[case_id] = {
            "attack": result.attack,
            "null": result.null,
            "effect": result.effect,
            "attack_ci": list(result.attack_ci) if result.attack_ci else None,
            "null_ci": list(result.null_ci) if result.null_ci else None,
            # None means "cannot tell", which is not the same as "no effect"
            # — the distinction §10.8 insists on.
            "separated": result.separated,
            "n_attack_pairs": result.n_attack_pairs,
            "n_null_pairs": result.n_null_pairs,
            "interpretable": result.null is not None,
            "clean_repetitions": len(clean_seqs),
        }
    return report


@router.get("/compare")
async def compare_experiments(experiments: str):
    """Cross-arm comparison — §11's EXP-4 and EXP-6, the research output.

    `experiments` is a comma-separated list of ids. Runs are pooled by the
    arm their experiment recorded, so a sweep split across several
    experiments (a resumed run, or one arm per invocation) still compares
    correctly.
    """
    ids = [e.strip() for e in experiments.split(",") if e.strip()]
    if len(ids) < 2:
        raise HTTPException(status_code=400, detail="Pass at least two experiment ids to compare")

    db = await get_db()
    by_arm: Dict[str, List[RunOutcome]] = {}
    configs: Dict[str, Dict[str, Any]] = {}
    for experiment_id in ids:
        experiment = await lab_store.get_experiment(db, experiment_id)
        if experiment is None:
            raise HTTPException(status_code=404, detail=f"No experiment '{experiment_id}'")
        configs[experiment_id] = json.loads(experiment.configJson)
        outcomes, _ = await _outcomes(db, experiment_id)
        by_arm.setdefault(experiment.armKey, []).extend(outcomes)

    errors, warnings = comparability_problems(configs)
    if errors:
        raise HTTPException(
            status_code=400,
            detail="These experiments differ in more than their arm, so a difference between them "
                   "could not be attributed to the arm: " + "; ".join(errors),
        )

    if len(by_arm) < 2:
        raise HTTPException(
            status_code=400,
            detail=f"All given experiments share the arm '{next(iter(by_arm))}'. "
                   "A comparison needs two different arms.",
        )

    return {
        "arms": {arm: arm_summary(outcomes) for arm, outcomes in by_arm.items()},
        "comparisons": compare_standard(by_arm),
        "warnings": warnings,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Runs
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/runs/{run_id}")
async def get_run(run_id: str):
    db = await get_db()
    run = await lab_store.get_run(db, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"No run '{run_id}'")

    events = await lab_store.load_run_events(db, run_id)
    return {
        **_run_summary(run),
        "experiment_id": run.experimentId,
        "cee_before": json.loads(run.ceeBeforeJson) if run.ceeBeforeJson else None,
        "cee_after": json.loads(run.ceeAfterJson) if run.ceeAfterJson else None,
        "events": [
            {
                "step": e.step,
                "category": e.category.value,
                "event_type": e.event_type.value,
                "timestamp": e.timestamp.isoformat(),
                "agent_id": e.agent_id,
                "tool": e.tool,
                "arguments": e.arguments,
                "result": e.result,
                "authorized": e.authorized,
                "source_event_id": e.source_event_id,
                "derived_from": list(e.derived_from),
                "content_tag": e.content_tag.value if e.content_tag else None,
                "metadata": e.metadata,
            }
            for e in events
        ],
        "event_count": len(events),
    }


@router.get("/runs/{run_id}/evidence")
async def get_run_evidence(run_id: str):
    """The §12 bundle: self-contained enough to audit the verdict offline."""
    db = await get_db()
    run = await lab_store.get_run(db, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"No run '{run_id}'")
    if run.mode != ATTACK:
        raise HTTPException(
            status_code=400,
            detail=f"Run '{run_id}' is a {run.mode} run. Evidence bundles are assembled for "
                   "ATTACK runs, which carry the verdict; its clean baseline is embedded inside.",
        )
    if not run.baselineRunId:
        raise HTTPException(
            status_code=409,
            detail=f"Run '{run_id}' has no paired clean baseline, so its verdict cannot be "
                   "reconstructed — every definition in §9 is baseline-relative.",
        )

    experiment = await lab_store.get_experiment(db, run.experimentId)
    attack_collector = await lab_store.load_run_collector(db, run_id)
    clean_collector = await lab_store.load_run_collector(db, run.baselineRunId)

    try:
        case = load_case(run.caseId)
    except FileNotFoundError:
        raise HTTPException(status_code=409, detail=f"Case '{run.caseId}' no longer exists on disk")

    return build_bundle(
        case=case,
        attack_collector=attack_collector,
        clean_collector=clean_collector,
        config=json.loads(experiment.configJson) if experiment else {},
        run_id=run_id,
        pair_id=run.pairId,
        experiment_id=run.experimentId,
        arm=experiment.armKey if experiment else "unknown",
        cee_before=json.loads(run.ceeBeforeJson) if run.ceeBeforeJson else None,
        cee_after=json.loads(run.ceeAfterJson) if run.ceeAfterJson else None,
        diagnostics=json.loads(run.metricsJson) if run.metricsJson else None,
        # The stored verdict, so the bundle agrees with the run page once the
        # case was rescored against its pooled clean runs.
        verdict=verdict_from_dict(json.loads(run.verdictJson)) if run.verdictJson else None,
    )
