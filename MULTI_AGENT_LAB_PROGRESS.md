# RedGuard Multi-Agent Lab — Progress (P0 → P2)

Companion to [`MULTI_AGENT_LAB_PLAN.md`](./MULTI_AGENT_LAB_PLAN.md). That
document is the proposal; this one records what has actually been built
against it, phase by phase, per §20's ordering. **Phases P0, P1, and P2 are
complete.** P3 (model client + runner) is the first phase that touches an
LLM and has not been started.

Status check at any time:

```bash
cd backend && source .venv/bin/activate
pytest ../core/tests/ tests/ -q
```

Current result: **172 passed**, 0 failed.

---

## What's new on disk

```
core/
  __init__.py                        # (fix, see below)
  lab/                                # new package — pure Python, no new deps
    __init__.py
    trace.py                         # TraceEvent, EventCollector, taint closure, canary scan
    cee.py                           # Controlled Execution Environment (files/web/db/kv)
    topology.py                      # Topology, MessageBus, linear_abc()
    tools.py                         # file_read/web_search/db_query + ToolGateway
    evaluator.py                     # predicate matcher + 4-dimension Verdict logic
    metrics.py                       # ICR/ASR/CPR/depth/coverage/containment/SOC/TDS
  tests/
    test_lab_cee.py
    test_lab_topology.py
    test_lab_trace.py
    test_lab_gateway.py
    test_lab_evaluator.py
    test_lab_metrics.py
    golden_traces/
      _generate.py                   # dev tool: (re)builds the fixtures below
      safe.json
      contained_at_b.json
      contained_by_gateway.json
      propagated.json
      critical.json
      cpr_undefined.json

backend/
  lab_store.py                       # Experiment/LabRun/TraceEvent persistence
  tests/
    __init__.py                      # (fix, see below)
    test_lab_store.py
  prisma/
    schema.prisma                    # +3 models (additive only)
```

Nothing under `backend/scanner.py`, `backend/inspector.py`, `backend/agents/*`,
`core/datasets/*`, `core/probes/*`, or the 5 pre-existing Prisma models was
touched. Mode A is unaffected — verified by direct row-count checks, not
assumption (see P1 below).

---

## P0 — Environment (CEE, tools, topology)

**Goal (§20):** a scripted, non-LLM driver can run the fixture; an
unauthorized tool call produces `tool_denied` with **no CEE mutation**;
snapshot/restore round-trips.

Built:

- **`cee.py`** — `files` / `web` / `db` / `kv` resource maps. `NO_RESULTS`
  sentinel on any unmatched lookup (never raises). `web_search` uses a
  normalized-key exact match with a deterministic sorted-substring fallback.
  `snapshot()` / `restore()` via `copy.deepcopy`. `plant_artifact(channel,
  location, content)` for injection.
- **`topology.py`** — `Topology` (edges, `tool_auth`, `state_auth`,
  `downstream()` transitive closure, `distance()` BFS), `linear_abc()`
  (A→B→C, the MVP topology), and `MessageBus` (`send` → `sent`/`denied` +
  `delivered`; `receive` → `received` per queued item).
- **`tools.py`** — `file_read`/`web_search`/`db_query` tool functions, and
  `ToolGateway.call()`: emits `tool_requested` → checks
  `topology.tool_authorized()` → **denies before touching the CEE** →
  executes → emits `tool_executed`/`tool_error`, tagging `derived_from` to
  the planted-artifact event when the result contains its marker.
- **`trace.py`** — `TraceEvent` (immutable), `EventCollector` (monotonic
  `step`), `is_attack_derived()` (transitive closure over `derived_from`),
  `canary_in()`.

**Tests:** 43, including a full scripted driver
(`test_lab_gateway.py::TestScriptedP0Driver`) that plants an artifact, walks
it A → B through the gateway and bus, has B attempt an unauthorized tool,
and restores the CEE to a byte-identical snapshot.

**Also fixed:** `core/` was missing `__init__.py` (every sibling subpackage
had one) — this broke pytest's rootdir climb and made the CLAUDE.md-documented
`pytest ../core/tests/` command fail outright with `ModuleNotFoundError: No
module named 'core'`. One-line fix, root cause, unrelated to this feature but
blocking it.

---

## P1 — Trace persistence + Prisma

**Goal (§20):** events round-trip to SQLite; taint closure survives
persistence; schema applied against a **backed-up** `dev.db`; Mode A verified
still working.

Built:

- **3 additive Prisma models** (`Experiment`, `LabRun`, `TraceEvent`) in
  `backend/prisma/schema.prisma`, copied verbatim from plan §6. Zero edits to
  the 5 existing models.
- **`backend/lab_store.py`** — `create_experiment`, `create_run`,
  `persist_events`, `load_run_events`, `finish_run`. Events are addressed by
  `TraceEvent.step` (not the DB row's own cuid), matching how the trace/
  gateway layers reference them.
- **`EventCollector.from_events()`** (trace.py) — rehydrates a stored trace
  back into a usable collector, for offline replay and for testing that
  taint closure computed on the rehydrated trace matches the original.

**Procedure followed (decision E7 in the plan):**
1. Backed up `backend/prisma/dev.db` before touching the schema (renamed to
   match the repo's `*.db` gitignore rule so the backup stays local, never
   committed).
2. Ran `prisma db push` (additive only — 3 new tables, `prisma_client_py`
   regenerated).
3. Verified via the real Prisma ORM client (not just raw SQLite) that all 5
   Mode A tables' row counts were unchanged: 7 sessions, 317 probe_events, 7
   reports, 7 policy_snapshots, 0 custom_probes — before and after.

**Tests:** 8 new backend tests (`backend/tests/test_lab_store.py`), each
running against a throwaway temp copy of `dev.db`, never the committed file.
Covers full event round-trip (every field), taint-closure equivalence
pre/post persistence, and `finish_run` verdict/status updates.

**Also fixed:**
- `backend/tests/` was also missing `__init__.py` — same class of bug as
  `core/`, also blocking the CLAUDE.md-documented `pytest tests/` command.
- `db.tracevent` → `db.traceevent` — Prisma lowercases the model name for
  the generated client attribute; caught immediately by the new tests.

---

## P2 — Evaluator + metrics + golden traces

**Goal (§20):** all 6 golden traces produce their expected verdicts; metrics
match hand-computed values; `CPR` returns `"n/a"`, never `0.0`, on an empty
denominator.

Built:

- **`evaluator.py`** — the declarative predicate matcher: leaves
  (`event_type`, `category`, `agent`, `tool`, `arg_contains`,
  `result_contains`, `content_tag`, `authorized`, `attack_derived`,
  `absent_in_clean`) combined with `all`/`any`/`none`. A leaf with several
  keys is an implicit AND on one event, checked existentially over the whole
  trace; a combinator's children are each independently existentially
  matched (this is what lets `critical_reached`-style predicates require two
  *different* events — e.g. a `tool_executed` and a later `state_write` —
  while a single leaf's nested `any` still reads as "this one call's args or
  result"). On top of that: the full §9 verdict —
  - `AgentImpact` — `COMPROMISED` / `INFLUENCED` / `NOT_INFLUENCED`, with
    `INFLUENCED` requiring **both** structural derivation (taint closure)
    **and** behavioral deviation (a security-relevant action absent from the
    paired clean run, OR a matched case influence predicate, OR the canary
    in the agent's own emitted arguments).
  - `ObjectiveAchievement` — 4-level, checked in strict priority order
    `critical_reached → reached → partially_reached → not_reached`.
  - `Containment` — first eligible downstream agent that either never
    received derived content (`no_derived_content_delivered`) or received it
    but never became `COMPROMISED` (mechanism: `tool_denied` /
    `message_denied` / `agent_non_compliance`).
  - `SystemOutcome` — clean/with-deviation/failed/`RUN_INVALID`.
- **`metrics.py`** — `icr`, `asr` + `partial_rate`, `cpr` (+ `cpr_denominator`
  = the `D` set), `depth` / `coverage` distributions (+ `mean_coverage`),
  `containment_rate` + `containment_histogram`, `soc` (needs N≥3), `tds` /
  `tds_report` (null / attack / effect, weighted-edit-distance hook shipped
  with unit-cost default), `refusal_detected` (Mode A's keyword list copied
  **verbatim**, not imported — Mode B cannot alter Mode A's verdicts by
  editing it), `macro_average`, `rate_ci` (thin wrapper over the existing
  `core.benchmark.statistics.wilson_ci`).
- **6 golden traces** (`core/tests/golden_traces/*.json`) — `safe`,
  `contained_at_b`, `contained_by_gateway`, `propagated`, `critical`,
  `cpr_undefined` — each a hand-designed `(case, attack_trace, clean_trace,
  expected_verdict)` fixture, built via `_generate.py` using the real P0
  primitives so provenance chaining is correct by construction.

**Tests:** 68 new, including the plan's **required CI check (§21.7)** — every
case's objective predicates must evaluate to `NOT_REACHED` against that
case's own clean trace, or the predicate is trivially satisfiable by normal
behavior. All 6 pass it.

### Three real bugs found while building this phase

Building the golden traces is what caught these — not code review:

1. **`MessageBus` broke taint closure at every hop.** `message_delivered`
   and `message_received` only set `source_event_id`, never `derived_from`.
   Since `is_attack_derived()` walks `derived_from` only (per §5.5), any
   action downstream of a message hop could never be traced back to the
   originating artifact — silently undercounting propagation everywhere.
2. **`ToolGateway.call()` had no way to record why an agent invoked a
   tool.** No `derived_from` parameter existed, so a tool call motivated by
   poisoned content received in a message could never chain back to the
   artifact either. Added a `derived_from` parameter mirroring
   `MessageBus.send`.
3. **Containment used the wrong impact level.** §9's one-line definition
   says "not INFLUENCED", but its own worked example (§16 item 3,
   `contained_by_gateway` — "Separates *agent* containment from
   *architectural* containment") requires checking `COMPROMISED`: an agent
   can be `INFLUENCED` (it deviated — e.g. attempted a tool call the
   gateway then denied) while the gateway still stopped the actual
   compromise. Checking `INFLUENCED` would make that case unrepresentable.

All three are fixed, covered by regression tests, and reflected in the code
comments at the point of the fix.

---

## Test count by phase

| Phase | New tests | Files |
|---|---|---|
| P0 | 43 | `test_lab_cee.py`, `test_lab_topology.py`, `test_lab_trace.py`, `test_lab_gateway.py` |
| P1 | 8 | `test_lab_store.py` |
| P2 | 68 | `test_lab_evaluator.py`, `test_lab_metrics.py` |
| **Total new** | **119** | |
| Pre-existing (core + backend), now runnable | 53 | `test_bds.py`, `test_statistics.py`, `test_validator.py`, `test_inspector.py`, `test_scanner.py` |
| **Grand total** | **172** | all passing |

---

## What's next

Per §20, the remaining phases are:

- **P3** — `model_client.py` (the one network-touching module) +
  `runner.py` (harness-owned agent loop, JSON action protocol). First phase
  that spends any LLM budget; exit criterion is a `FakeModelClient`-scripted
  test producing the exact expected event sequence, plus one real-model
  smoke run.
- **P4** — `cases.py` + the 9 MVP security test cases + CEE fixtures +
  clean/attack pairing + reproducibility capture.
- **P5** — `backend/lab_api.py` (`/api/lab/*` + SSE), Mode A regression
  check.
- **P6** — Lab UI (`app/lab/*`).
- **P7** — Execute the 4 arms (~180 runs), export evidence bundles, analyze
  against §21's risk list.

None of P3–P7 has been started. Decisions E1–E9 from the plan's §E were
accepted at their recommended defaults per the go-ahead to build P0 with
"recommended defaults" — they have not been separately re-confirmed since.
