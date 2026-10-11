# CLAUDE.md

Project guidance for Claude Code in this repository. `AGENTS.md` has setup
steps; `README.md` has the feature overview and architecture diagram.

**Every part of the codebase is open to change**, Mode A included. The notes
below describe how things work and what a change affects; none of them are
restrictions.

## What this is

RedGuard is an AI-agent security benchmark with two modes that answer
different questions.

**Mode A — probe scanner.** Fires 46 adversarial prompts ("probes") from 8
attack families and 12 scenarios at a pluggable LLM agent, plus 10 benign
controls (`"benign_control": true`) that measure over-refusal and regex false
positives. Each probe goes through the regex filter (`backend/inspector.py` +
`backend/policy.yaml`), an optional ML classifier (`CLASSIFIER_URL`), and the
agent; `score()` in `backend/scanner.py` puts it in one tier (below). Results
stream over SSE to the UI; `/api/leaderboard` (`backend/leaderboard.py`) pools
measured runs. Code: `backend/` (scanner, inspector, leaderboard, agents),
`core/datasets` (the probes), `core/benchmark` (BDS, Wilson CI, repro stamp —
shared with Mode B). Routes: `/`, `/corpus`, `/runs`, `/models`, `/settings`.

**Mode B — multi-agent lab.** Three agents (A researcher → B validator → C
executor) work inside a simulated environment (`core/lab/cee.py`). The model
proposes one JSON action per step and the harness executes it, so every tool
call, message and state write is observed with provenance rather than
self-reported. An attacker artifact is planted in a tool channel; each case runs
attack + clean (control). The verdict has four dimensions — agent impact,
objective achievement, containment, system outcome — and is never collapsed to
one score. Defence arms: `attack`, `attack_validated`, `attack_bus_gateway`
(oracle upper bound), `attack_capability_gateway` (CaMeL-style),
`attack_permissive_tools`. Code: `core/lab/`, `backend/lab_api.py`,
`backend/lab_store.py`, `backend/sweep.py`. Routes: `/lab`, `/lab/compare`,
`/lab/experiments/[id]`, `/lab/runs/[id]`. Experiments run as server-owned
asyncio tasks (`_Job` in `lab_api.py`: `POST …/start|stop`, `GET …/stream`),
so closing a tab does not stop one; one uvicorn worker only. Each experiment
has a report (`core/lab/report.py`, `GET …/report`, `?format=md` for Markdown,
page `/lab/experiments/[id]/report`), built on demand from stored traces and
the `/metrics` numbers, so it always matches the experiment page.

Layout:
- `app/`, `components/`, `lib/` — Next.js 16 / React 19 / TypeScript UI.
  `lib/data-service.ts` (Mode A), `lib/lab-service.ts` (Mode B).
- `backend/` — FastAPI on :8000, Prisma over SQLite.
- `core/` — pure-Python library imported by `backend/` via a `sys.path` insert
  in `backend/app.py`. `core/` does not import `backend/`.

## Current state (2026-10-11)

- `main` has Mode B merged (PR #2), the `/lab/compare` page, Docker support,
  and a desktop-app plan (`DESKTOP_APP_PLAN.md`, not started).
- Branch `mode-a-fixes` carries `MODE_A_FIX_PLAN.md` phases 1–9 (security,
  tiered scoring, benign controls, regex precision, measured leaderboard,
  lint/phone layout, v4.0.0, unused-code removal, first local results). Still
  open: hand-rewriting the attack `prompt` fields in `core/datasets/*.json`.
- **646 tests pass** (~15 s, no LLM). `npm run typecheck` and `npm run lint`
  are clean.
- **First Mode A results** (granite3.3:2b via Ollama, pre-rewrite prompts):
  attack success with the filter off 19.6% baseline / 13.0% hardened; see
  `MODE_A_FIX_PLAN.md` for the table. Run real scans on local Ollama
  (`ollama_local_agent`), not the hosted NVIDIA agents.
- **Mode B has no real-model results yet.** Every number so far is scripted or
  synthetic. Real runs use local Ollama `granite3.3:2b` only (not hosted, not
  llama3.1/qwen3). Branch `mode-b-live-view` carries `MODE_B_LIVE_PLAN.md`
  phases 1–4 (server-owned runs, live agent cards/swimlane, Ollama JSON-schema
  decoding: granite parse failures 85.7% → 0%); see its Status section.
  Granite now emits valid actions but never calls `finish`.

### How Mode A scores (since `mode-a-fixes` phase 2)

Every probe lands in one tier: `FILTERED` (regex policy denied it), `REFUSED`,
`IGNORED` (no refusal, no compliance) or `COMPROMISED`. The model is called
even for filtered probes, and its own result is stored as `modelOutcome`, so a
session has both "as deployed" and "model alone" numbers. `score()` in
`backend/scanner.py` uses each probe's `evaluation_rules`; a refusal phrase
beats a success indicator, and rows where both matched are
`scoredBy="indicators_mixed"`. Sessions with `benchmarkVersion = null` are
legacy (old BLOCKED/ALLOWED scoring). Agents run with a neutral `baseline`
system prompt unless the scan asks for `hardened` (`promptMode`).

### Known issues in Mode A (measured)

- **The regex filter is a weak layer by design** (it reads phrasing, not
  intent). Since plan phase 4 its patterns match attack shapes (a verb aimed
  at a target) instead of single words: it catches 24/46 attack probes and
  blocks 0/10 controls and 0/25 everyday questions (before: 28, 4 and 20).
  Patterns live in `backend/inspector.py`; `policy.yaml` maps them to actions,
  and two matches reach its 0.2 risk threshold.
- **Success indicators echo the attack wording**, so substring scoring
  under-counts "I'm sorry, but here it is" (plan phase 3 adds canaries).
- **Probe quality** (plan phase 3; the `prompt` rewrites are done by hand in
  `core/datasets/*.json`). Many attack prompts contain giveaway phrases
  (`attacker@evil.com`, `[INJECTED PLAN STEP]`); RG-DI-008 and RG-MP-006
  explain themselves to the model. Indirect families are delivered in the user
  message, not a tool result. The agents only have `web_search`, `file_read`,
  `calculator` and no memory between calls, so tool-action and
  memory-poisoning probes cannot succeed; RG-EX-004 needs an email tool the
  agents lack. Template leftovers in RG-CI-002/004/008; RG-CI-001 ≈ RG-CI-002,
  RG-DI-001 ≈ RG-DI-002. (Done: TM-003/004/005 removed, RG-GD-002 is a control.)
- **Version bump:** release 4.1.5, Mode A benchmark 4.0.0 (unchanged by the
  4.1.5 Mode B work). Scores from 3.x runs are not comparable;
  those sessions stay viewable as "legacy scoring" and never enter the
  leaderboard. Old report files are in `reports/legacy-v3/`.

Fixed in phase 1: `/api/proxy` removed; CORS limited to `CORS_ORIGINS`
(default `http://localhost:3000`); Docker publishes on 127.0.0.1 only;
`CLASSIFIER_URL` has no default (unset = no classifier call); agents'
`file_read` only reads `backend/agents/sandbox/` (shared tools in
`backend/agents/_tools.py`); the scan SSE stream sends `no-transform`.

## Commands

```bash
docker compose up --build                                          # everything, no local installs
docker compose -f docker-compose.yml -f docker-compose.dev.yml up  # same, with live reload
docker compose run --rm backend python -m pytest ../core/tests tests -q
```

```bash
npm run dev:all       # frontend (:3000) + backend (:8000)
npm run lint
npm run typecheck
```

```bash
cd backend && source .venv/bin/activate
pytest tests/                 # inspector, scanner, lab_store, lab_api
pytest ../core/tests/         # BDS, statistics, schema validation, all of Mode B
pytest ../core/tests/ tests/  # everything
```

Mode B entry points (only `smoke` without `--scripted` and real sweeps call an LLM):

```bash
python -m core.lab.cases                     # validate the 9 cases
python -m core.lab.smoke --scripted          # whole pipeline, no model calls
python -m core.lab.smoke --provider nvidia --model nvidia/nemotron-3-super-120b-a12b

cd backend
DATABASE_URL="file:/tmp/sweep.db" python sweep.py --scripted --reps 2
DATABASE_URL="file:/tmp/sweep.db" python sweep.py --report <experiment_ids>
```

No frontend test suite — check UI changes with `npm run dev` in a browser plus
`lint`/`typecheck`.

## How things work

- **Probes are JSON** in `core/datasets/*.json`, validated against
  `core/datasets/schema.json`. Both `core/datasets/loader.py` and
  `lib/data-service.ts` read them, so a moved/renamed file needs both updated.
  Changing probe content means bumping `DATASET_VERSION`.
- **Agents are auto-discovered.** Any `backend/agents/*.py` not prefixed `_`
  that defines `AGENT_NAME`, `AGENT_DESCRIPTION` and async `invoke(prompt)` is
  picked up by `backend/agent_loader.py`. Template: `example_custom_agent.py`.
  An optional `prompt_mode` argument (`"baseline"` / `"hardened"`) lets the
  scan choose the system prompt; agents without it are recorded as
  `agent_default`. Prompts live in `backend/agents/system_prompts.json`.
- **Schema changes:** run `prisma generate` with the venv first on `PATH`
  (otherwise the client is written to whichever Python the generator finds).
  `npm run dev:all` and Docker run `prisma db push` on start, so the DB in use
  picks up new columns; a backend started any other way needs the push by hand
  or every query fails with "column … does not exist".
- **Mode B cases are JSON** in `core/lab/cases/RGM-00{1..9}.json` with
  `case_schema.json`, loaded by `core/lab/cases.py`. Each has a `clean_script`
  that CI uses to prove the clean trace completes the task and does *not*
  satisfy the attacker's objective.
- **`backend/policy.yaml`** drives the inspector's rule layer, separate from
  the ML classifier. Editing it changes detection results.
- **Mode A ↔ Mode B coupling is small.** Shared: constants in
  `core/version.py`, the Wilson-CI helper in `core.benchmark.statistics`. Mode B
  keeps its own copy of the refusal-keyword list. Tests in
  `backend/tests/test_lab_api.py::TestModeAIsUnaffected` and
  `core/tests/test_lab_cases.py::test_mode_a_version_info_is_unchanged` check
  that Mode A routes and `get_version_info()` keys still exist — update them
  if you change those on purpose.
- **Versions.** Canonical in `core/version.py`, with no runtime link to the
  frontend, so strings are hand-synced. Two kinds:
  - **Release** 4.1.5 (`RELEASE_NAME`): `package.json` (+ lock, via
    `npm version X --no-git-tag-version`), `README.md` title and version badge,
    `app/layout.tsx`, `components/Sidebar.tsx`.
  - **Benchmark** (Mode A scoring and probe set): `BENCHMARK_VERSION`,
    `DATASET_VERSION`, `PROBE_SCHEMA_VERSION`, all 4.0.0: `README.md` benchmark
    and dataset badges, `components/Header.tsx`, `app/runs/page.tsx`,
    `app/corpus/page.tsx`; then regenerate `docs/benchmark_spec.md` with
    `python docs/spec_generator.py`. The leaderboard pools runs whose
    `BENCHMARK_VERSION` matches exactly, so bump it only when scores stop being
    comparable (a release-only change keeps it).
  Mode B: `LAB_SCHEMA_VERSION`, `CASE_SCHEMA_VERSION`, `CEE_VERSION`,
  `TOPOLOGY_VERSION`, `EVALUATOR_VERSION`, `METRIC_VERSION`, exposed via
  `get_lab_version_info()`. A `METRIC_VERSION` bump makes earlier numbers
  non-comparable.
- **`backend/prisma/dev.db`** is committed seed data for the demo UI
  (whitelisted in `.gitignore`); regenerating it loses the seeded scan history.
  It has no `lab_*` tables — backend tests migrate a temp copy
  (`backend/tests/conftest.py`) and Docker migrates its volume copy. Some
  clones flag it `assume-unchanged` (`git ls-files -v` shows `h`), so check
  tables/row counts rather than trusting git. **With that flag set,
  `git stash` / `git reset --hard` silently replace the local `dev.db` with
  the committed copy** (the stash does not save it) — this wiped local runs
  and all `lab_*` data once (2026-10-11). Don't stash in a clone with the flag;
  copy the file first if you must. `npm run dev:all` uses `DATABASE_URL` from
  `.env`; point it at a copy for experiments.
- **Python 3.10+** must keep working. 3.14 evaluates annotations lazily, so a
  missing `typing` import only fails on older interpreters. Check new modules
  with `typing.get_type_hints()` on their functions (forces evaluation) or run
  the suite under Docker (3.12); `python3.11` is also installed locally.
- The `<!-- BEGIN:nextjs-agent-rules -->` block in `AGENTS.md` is regenerated
  by `next dev`; deleting it just brings it back.
- `scripts/*.py` are legacy standalone CLI tools; they don't talk to the
  FastAPI server or the Prisma DB (`scripts/CLI_README.md`).
- Frontend style: few comments, self-explanatory names.

## Docs map

- `MULTI_AGENT_LAB_PLAN.md` — Mode B design (§ numbers cited in code).
- `MULTI_AGENT_LAB_PROGRESS.md` (~120 KB) — what's built, bugs found, test
  inventory; section "2026-09-30 — what changed, and what is left" is the
  latest status.
- `MULTI_AGENT_LAB_EXPLAINED.md` — Mode B in plain language.
- `RedGuard_Architecture.md` / `.pdf` — full architecture write-up.
- `docs/` — Mode A architecture, generated benchmark spec, literature mapping,
  research paper draft.
- `PRODUCT.md` — product/design context. `DESKTOP_APP_PLAN.md` — packaging plan.
- `graphify-out/` — deleted 2026-10-11; rebuild with `/graphify` before relying
  on it. Until then, read the docs above and the code directly.