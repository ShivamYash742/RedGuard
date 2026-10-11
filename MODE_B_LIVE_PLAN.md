# Mode B Live View Plan

Goal: while an experiment runs, you can see **which agent is working, what it
is doing, for how long, and how far the whole experiment has got** — from any
tab, after a reload, and without keeping one page open.

Measured on 2026-10-11 against the code on `mode-a-fixes`.

## Status (2026-10-11, branch `mode-b-live-view`)

All four phases are built. 643 tests pass; `typecheck` and `lint` are clean.
Live view checked in headless Chrome mid-run at 1280 px and 390 px.

- **Phase 1.** Launcher defaults to Ollama `granite3.3:2b` (the only model
  used for real runs). Scripted is "Instant demo (no model)" with a slow
  motion option (`step_delay_ms`, 700 ms). "Test model" launches a one-case,
  one-pair experiment; the experiment page shows a warning banner once more
  than 10% of replies are not a valid action (at least 10 steps).
  - Plain JSON mode did **not** fix granite: 85.7% parse failures (12/14),
    because it named the tool as the action (`{"action": "db_query", ...}`)
    and the repair retry repeated it. Ollama now gets a JSON *schema*
    (`ACTION_SCHEMA`: `action` limited to the six kinds, `tool` to the real
    tools). Result: **0 / 60 steps** failed to parse on RGM-001.
  - Still open: with valid actions, granite never calls `finish` (all 6
    agents ended on `max_steps`), never reads the file via `tool_call` and
    never messages the next agent. That is the model's ability, measured,
    not a protocol fault; prompts were not tuned to change it.
  - Not done: the comparison of `llama3.1` / `qwen3:4b`. Real runs use
    granite only.
- **Phase 2.** `trace_event` carries `timestamp`, `latency_ms`, `turn`,
  `max_steps`, and `reason` on `agent_finished`. `run_started` has `index`
  and `total_runs`; new `run_finished` (duration, steps, parse failures,
  progress). `experiment_started` has model, `max_steps`, agents, scripted.
- **Phase 3.** `components/AgentCards.tsx` (status with ticking timer, step
  n of max, last action, refusals, invalid replies) and
  `components/AgentSwimlane.tsx` (also on the replay page, with a cursor).
  The stage shows clean baselines too; progress moves per run, with elapsed
  and ETA; collapsible event feed.
- **Phase 4.** `POST …/start`, `POST …/stop`, `GET …/stream` (backlog then
  live, any number of viewers); `GET …/run` is start-or-join plus stream.
  `live` progress on every experiment row; `/lab` badges running ones. App
  shutdown cancels jobs; their RUNNING rows are failed on resume.

---

## What is wrong today

| # | Problem | Where |
|---|---|---|
| 1 | The launcher defaults to **scripted** (finishes in about a second, nothing to watch) and to the **NVIDIA** provider | `app/lab/page.tsx:33-34` |
| 2 | Local `granite3.3:2b` cannot drive the harness: **89% of replies are not a valid JSON action** (16 of 18 steps), every agent stops on `parse_failure`, both runs are `RUN_INVALID` in 35 s | `python -m core.lab.smoke --provider ollama --model granite3.3:2b` |
| 3 | The experiment runs **inside the browser's request**: closing or reloading the tab stops it, a second tab gets `409`, nobody else can watch | `backend/lab_api.py` `run_experiment`; page comment "leaving the page must stop it" |
| 4 | The live stage draws **attack runs only**. During each pair's clean baseline (half the time) it says "Waiting for the first attack run" | `app/lab/experiments/[experimentId]/page.tsx:335-358` |
| 5 | Progress moves only when a **whole pair** (clean + attack) finishes, so the bar sits still for minutes with a real model | `run_verdict.progress` in `lab_api.py` |
| 6 | **No timing**: the stream drops each event's timestamp, so there is no "B thinking for 12 s", no step latency, no ETA | `_event_payload` in `lab_api.py` |
| 7 | Agent state is only a pulsing dot and "deciding…" on the stage; no per-agent status (step n of max, last action, invalid replies, why it finished) | `components/LabRoute.tsx:424` |
| 8 | Invalid model replies (`action_parse_failed`) and repair retries are not shown as such while they happen | `lib/lab-service.ts` `deriveRoute` |

What already works and stays: events stream as they are emitted (bug 42),
the proxy no longer buffers them (bug 43), the board batches updates per
animation frame, `agent_step_started` fires right before each model call, and
completed pairs are saved and resumable.

---

## Phase 1 — Make a run worth watching (prerequisite, small)

1. **Launcher defaults:** scripted off, provider `ollama`, model pre-filled
   with the local model that passes the suitability gate (1.2). Scripted is
   relabelled "Instant demo (no model)".
2. **JSON mode for Ollama:** send `response_format: {"type": "json_object"}`
   from `core/lab/model_client.py` when the provider is `ollama` (Ollama's
   OpenAI endpoint supports it). Re-run the smoke check on `granite3.3:2b`,
   `llama3.1`, `qwen3:4b`; the default is the fastest model under the 10%
   parse-failure gate (§21.9). The gate itself stays.
3. **Slow-motion demo:** optional `step_delay_ms` (scripted runs only, e.g.
   700 ms) so the whole pipeline animates in a viva without any model.
4. **"Test model" button** on the launcher: a new endpoint runs the smoke check
   on one case and returns the parse-failure rate; launching above 10% shows a
   warning that runs will be invalid.

Check: smoke test of the default model ≤ 10% parse failures; a slow-motion
demo run visibly moves through A → B → C.

## Phase 2 — Richer live events (backend, small)

1. Add `timestamp` (ISO, from `TraceEvent.timestamp`) to every `trace_event`.
2. Runner: `agent_step_started` carries `{"turn", "max_steps"}` in metadata;
   `agent_output` and `action_parse_failed` carry `latency_ms` of the model call.
3. Progress per **run**, not per pair: `run_started` gets `index` and
   `total_runs`; a new `run_finished` event (status, duration, steps) fires
   after each clean and each attack run.
4. `experiment_started` includes the model, `max_steps` and the topology's
   agent list, so the page can lay out agent cards before the first event.

No server heartbeat: the page ticks its own timer from the last
`agent_step_started` timestamp, and sse-starlette's ping keeps the connection
alive.

Check: `backend/tests/test_lab_api.py` asserts the new fields; scripted
event order unchanged.

## Phase 3 — Live UI (frontend)

1. **Agent cards** (one per agent in the topology: A researcher, B
   validator, C executor): status — idle / **thinking 12 s** (ticking) /
   acted / waiting for a message / finished (reason) / invalid reply
   (retrying); step *n* of max; last action with its resource; denials;
   invalid-reply count. Derived in `deriveRoute` plus timestamps.
2. **Swimlane timeline** for the current run: time on the x-axis, one row per
   agent, a bar for each model call (thinking) and a tick for each action,
   message and denial — the direct answer to "when is each agent working".
   The replay page (`/lab/runs/[id]`) reuses it.
3. **Stage shows the current run in either mode:** clean baselines drawn
   neutral ("clean baseline — no attack planted"), attack runs as now.
4. **Progress instrument:** bar by runs; position line "RGM-003 · rep 2/5 ·
   attack run · step 14"; elapsed; ETA from the mean finished-run duration.
5. **Live event feed:** compact, scrolling, collapsible list for the current
   run (time, agent, action, allowed/denied), reusing `describeEvent`.

Check: browser screenshots mid-run at desktop width and 390 px; the timer
ticks; reduced-motion respected; lint and typecheck clean.

## Phase 4 — Runs that do not depend on the tab (backend)

1. **Background runner:** `POST /api/lab/experiments/{id}/start` starts
   `_execute` as a server-owned asyncio task; `POST …/stop` cancels it.
   Per-run persistence and resume are unchanged.
2. **Fan-out stream:** `GET …/stream` subscribes any number of viewers. A new
   subscriber first gets the current run's events so far (in-memory buffer)
   plus saved pair verdicts, then live events. Closing a tab no longer stops
   the run; reloading rejoins it.
3. `/lab` lists running experiments with a live badge and progress.
4. Server restart kills the task; on startup `abandon_stale_runs` (exists)
   marks RUNNING runs FAILED and the page offers Resume.

`ponytail:` in-process task registry, so one uvicorn worker; a job queue only
if the backend ever runs several workers.

Check: tests that a second subscriber receives the same events, that a
subscriber disconnecting does not cancel the run, and that stop cancels it;
the old `GET …/run` tests are updated or kept as start-and-stream.

---

## Order and size

1 → 2 → 3 → 4. Phase 1 is a few hours; 2 is small; 3 is the largest (two
new components, page changes); 4 is medium (endpoint + task registry + tests).
Phase 4 can come before 3 if watching from several tabs matters more than the
new visuals.

Files: `app/lab/page.tsx`, `app/lab/experiments/[experimentId]/page.tsx`,
`app/lab/runs/[runId]/page.tsx`, `components/LabRoute.tsx`, new
`components/AgentCards.tsx` and `components/AgentSwimlane.tsx`,
`lib/lab-service.ts`, `backend/lab_api.py`, `core/lab/runner.py`,
`core/lab/model_client.py`, `backend/tests/test_lab_api.py`,
`core/tests/test_lab_runner.py`.

Mode A is not touched. No `METRIC_VERSION` or `EVALUATOR_VERSION` change:
nothing here alters a verdict, only what is shown and when.
