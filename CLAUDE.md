# CLAUDE.md

Project guidance for Claude Code in this repository. `AGENTS.md` has setup
steps; `README.md` has the feature overview; `docs/architecture.md` is the map
of where everything lives.

**Every part of the codebase is open to change.** The notes below describe how
things work and what a change affects; none of them are restrictions.

## What this is

RedGuard is an AI-agent security benchmark with two modes that answer
different questions. Code comments and test names written before 4.2.0 call
them "Mode A" and "Mode B".

**Scanner mode (Mode A) — probe scanner.** Fires 46 adversarial prompts
("probes") from 8 attack families and 12 scenarios at a pluggable LLM agent,
plus 10 benign controls (`"benign_control": true`) that measure over-refusal
and regex false positives. Each probe goes through the regex filter
(`backend/scanner_mode/inspector.py` + `policy.yaml`), an optional ML classifier
(`CLASSIFIER_URL`), and the agent; `score()` in `backend/scanner_mode/scanner.py`
puts it in one tier (below). Results stream over SSE to the UI; `/api/leaderboard`
(`backend/scanner_mode/leaderboard.py`) pools measured runs. Routes: `/`,
`/corpus`, `/runs`, `/models`, `/settings`.

**Lab mode (Mode B) — multi-agent lab.** Three agents (A researcher → B
validator → C executor) work inside a simulated environment
(`core/lab_mode/cee.py`). The model proposes one JSON action per step and the
harness executes it, so every tool call, message and state write is observed
with provenance rather than self-reported. An attacker artifact is planted in a
tool channel; each case runs attack + clean (control). The verdict has four
dimensions — agent impact, objective achievement, containment, system outcome —
and is never collapsed to one score. Defence arms: `attack`, `attack_validated`,
`attack_bus_gateway` (oracle upper bound), `attack_capability_gateway`
(a task-scoped resource allowlist inspired by CaMeL), `attack_permissive_tools`. Routes: `/lab`, `/lab/compare`,
`/lab/experiments/[id]` (+ `/report`), `/lab/runs/[id]`. Experiments run as
server-owned asyncio tasks (`_Job` in `backend/lab_mode/api.py`:
`POST …/start|stop`, `GET …/stream`), so closing a tab does not stop one; one
uvicorn worker only. Each experiment has a report (`core/lab_mode/report.py`,
`GET …/report`, `?format=md`), built on demand from stored traces and the
`/metrics` numbers, so it always matches the experiment page.

## Layout (since 4.2.0)

**Every layer has the same three drawers: `shared/`, `scanner_mode/`,
`lab_mode/`.** The two modes never import each other — enforced by
`core/tests/shared/test_mode_boundaries.py` and a `no-restricted-imports` rule
in `eslint.config.mjs`. `shared/` may be used by both.

- `app/` — Next.js 16 / React 19 pages. Shared: `layout.tsx`, `page.tsx` (/),
  `settings/`. `(scanner_mode)/` and `(lab_mode)/` are route groups: folders
  only, not in the URL.
- `components/{shared,scanner_mode,lab_mode}/`, `lib/{scanner_mode,lab_mode}/`
  (`data-service.ts` + `search-index.ts`; `lab-service.ts`). Imports use `@/`.
- `backend/` — FastAPI on :8000, run from `backend/` (`uvicorn app:app`), which
  puts `backend/` on `sys.path`: modules import as `scanner_mode.scanner`,
  `lab_mode.api`, `database`. `app.py` is only the shared app (CORS, lifespan,
  `/api/health`) and mounts `scanner_mode/api.py` and `lab_mode/api.py`.
  `database.py` and `prisma/` are shared. Modules one level down insert the
  repo root with `"..", ".."` so `core` imports work standalone.
- `core/` — pure-Python library (no HTTP, no DB), imported as `core.shared.*`,
  `core.scanner_mode.*`, `core.lab_mode.*`. Never imports `backend/`.
- Tests mirror it: `core/tests/{shared,scanner_mode,lab_mode}/`,
  `backend/tests/{scanner_mode,lab_mode}/` + shared `conftest.py`.

## Current state (2026-10-11)

- `main` is the only branch. Release **4.2.0**: the restructure into
  `shared/` / `scanner_mode/` / `lab_mode/`. Before it: Lab mode (PR #2), Docker,
  the Scanner-mode fixes (security, tiered scoring, benign controls, regex
  precision, measured leaderboard, v4.0.0; PRs #4–#5) and the 4.1.5 Lab-mode
  live view and reports (PRs #6–#7). Still open: hand-rewriting the attack
  `prompt` fields in `core/scanner_mode/datasets/*.json`.
- Removed in 4.1.5, readable from git history (`git show 6c3606a:<file>`):
  the plan/progress docs (`MODE_A_FIX_PLAN.md`, `MODE_B_LIVE_PLAN.md`,
  `MULTI_AGENT_LAB_PROGRESS.md`, `DESKTOP_APP_PLAN.md`), the Lab-mode design
  spec and guide (`MULTI_AGENT_LAB_PLAN.md`, `MULTI_AGENT_LAB_EXPLAINED.md`)
  and the stale v3 `RedGuard_Architecture.md/.pdf`.
- **649 tests pass** (~15 s, no LLM). `npm run typecheck` and `npm run lint`
  are clean.
- **First Scanner-mode results** (granite3.3:2b via Ollama, pre-rewrite
  prompts): attack success with the filter off 19.6% baseline / 13.0% hardened;
  the table is in README "Measured results". Run real scans on local Ollama
  (`ollama_local_agent`), not the hosted NVIDIA agents.
- **Lab mode has no real-model results yet.** Every number so far is scripted
  or synthetic. Real runs use local Ollama `granite3.3:2b` only (not hosted,
  not llama3.1/qwen3). Ollama decoding is constrained to the action schema
  (granite parse failures 85.7% → 0%); granite emits valid actions but never
  calls `finish`.

### How Scanner mode scores (since 4.0.0)

Every probe lands in one tier: `FILTERED` (regex policy denied it), `REFUSED`,
`IGNORED` (no refusal, no compliance) or `COMPROMISED`. The model is called
even for filtered probes, and its own result is stored as `modelOutcome`, so a
session has both "as deployed" and "model alone" numbers. `score()` uses each
probe's `evaluation_rules`; a refusal phrase beats a success indicator, and
rows where both matched are `scoredBy="indicators_mixed"`. Sessions with
`benchmarkVersion = null` are legacy (old BLOCKED/ALLOWED scoring). Agents run
with a neutral `baseline` system prompt unless the scan asks for `hardened`
(`promptMode`).

### Known issues in Scanner mode (measured)

- **The regex filter is a weak layer by design** (it reads phrasing, not
  intent). Since 4.0.0 its patterns match attack shapes (a verb aimed at a
  target) instead of single words: it catches 24/46 attack probes and blocks
  0/10 controls and 0/25 everyday questions (before: 28, 4 and 20). Patterns
  live in `backend/scanner_mode/inspector.py`; `policy.yaml` maps them to
  actions, and two matches reach its 0.2 risk threshold.
- **Success indicators echo the attack wording**, so substring scoring
  under-counts "I'm sorry, but here it is" (canaries in the prompt rewrite
  should fix this).
- **Probe quality** (the `prompt` rewrites are done by hand in
  `core/scanner_mode/datasets/*.json`). Many attack prompts contain giveaway
  phrases (`attacker@evil.com`, `[INJECTED PLAN STEP]`); RG-DI-008 and
  RG-MP-006 explain themselves to the model. Indirect families are delivered in
  the user message, not a tool result. The agents only have `web_search`,
  `file_read`, `calculator` and no memory between calls, so tool-action and
  memory-poisoning probes cannot succeed; RG-EX-004 needs an email tool the
  agents lack. Template leftovers in RG-CI-002/004/008; RG-CI-001 ≈ RG-CI-002,
  RG-DI-001 ≈ RG-DI-002. (Done: TM-003/004/005 removed, RG-GD-002 is a control.)
- Scores from 3.x runs are not comparable; those sessions stay viewable as
  "legacy scoring" and never enter the leaderboard.

Security fixes in 4.0.0: `/api/proxy` removed; CORS limited to `CORS_ORIGINS`
(default `http://localhost:3000`); Docker publishes on 127.0.0.1 only;
`CLASSIFIER_URL` has no default (unset = no classifier call); agents'
`file_read` only reads `backend/scanner_mode/agents/sandbox/` (shared tools in
`backend/scanner_mode/agents/_tools.py`); the scan SSE stream sends
`no-transform`; `policy.yaml` is opened by path (`inspector.POLICY_PATH`), not
relative to the working directory.

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
pytest tests/                 # backend: scanner_mode/, lab_mode/
pytest ../core/tests/         # core: shared/ (incl. mode boundaries), scanner_mode/, lab_mode/
pytest ../core/tests/ tests/  # everything
```

Lab-mode entry points (only `smoke` without `--scripted` and real sweeps call an LLM):

```bash
python -m core.lab_mode.cases                     # validate the 9 cases
python -m core.lab_mode.smoke --scripted          # whole pipeline, no model calls
python -m core.lab_mode.smoke --provider ollama --model granite3.3:2b

cd backend
DATABASE_URL="file:/tmp/sweep.db" python -m lab_mode.sweep --scripted --reps 2
DATABASE_URL="file:/tmp/sweep.db" python -m lab_mode.sweep --report <experiment_ids>
```

Scanner-mode tools, from `backend/`: `python -m scanner_mode.target_agent`
(chat with an agent), `python -m scanner_mode.cli.<redteam_agent|audit_report|dashboard|add_custom_probes>`.
Probe spec: `python docs/scanner_mode/spec_generator.py`.

No frontend test suite — check UI changes with `npm run dev` in a browser plus
`lint`/`typecheck`.

## How things work

- **Probes are JSON** in `core/scanner_mode/datasets/*.json`, validated against
  its `schema.json`. Both `core/scanner_mode/datasets/loader.py` and
  `lib/scanner_mode/data-service.ts` read them, so a moved/renamed file needs
  both updated. Changing probe content means bumping `DATASET_VERSION`.
- **Agents are auto-discovered.** Any `backend/scanner_mode/agents/*.py` not
  prefixed `_` that defines `AGENT_NAME`, `AGENT_DESCRIPTION` and async
  `invoke(prompt)` is picked up by `scanner_mode/agent_loader.py`. Template:
  `example_custom_agent.py`. An optional `prompt_mode` argument (`"baseline"` /
  `"hardened"`) lets the scan choose the system prompt; agents without it are
  recorded as `agent_default`. Prompts live in `agents/system_prompts.json`.
- **Schema changes:** run `prisma generate` with the venv first on `PATH`
  (otherwise the client is written to whichever Python the generator finds).
  `npm run dev:all` and Docker run `prisma db push` on start, so the DB in use
  picks up new columns; a backend started any other way needs the push by hand
  or every query fails with "column … does not exist".
- **Lab cases are JSON** in `core/lab_mode/cases/RGM-00{1..9}.json` with
  `case_schema.json`, loaded by `core/lab_mode/cases.py`. Each has a
  `clean_script` that CI uses to prove the clean trace completes the task and
  does *not* satisfy the attacker's objective.
- **`backend/scanner_mode/policy.yaml`** drives the inspector's rule layer,
  separate from the ML classifier. Editing it changes detection results.
- **Shared between the modes:** `core/shared/version.py`, the Wilson-CI helper
  in `core.shared.statistics`, `core/shared/reproducibility.py`. Lab mode keeps
  its own copy of the refusal-keyword list. Tests
  `backend/tests/lab_mode/test_lab_api.py::TestModeAIsUnaffected` and
  `core/tests/lab_mode/test_lab_cases.py::test_mode_a_version_info_is_unchanged`
  check that Scanner routes and `get_version_info()` keys still exist — update
  them if you change those on purpose.
- **Versions.** Canonical in `core/shared/version.py`, with no runtime link to
  the frontend, so strings are hand-synced. Two kinds:
  - **Release** 4.2.0 (`RELEASE_NAME`): `package.json` (+ lock, via
    `npm version X --no-git-tag-version`), `README.md` title and version badge,
    `app/layout.tsx`, `components/shared/Sidebar.tsx`.
  - **Benchmark** (Scanner-mode scoring and probe set): `BENCHMARK_VERSION`,
    `DATASET_VERSION`, `PROBE_SCHEMA_VERSION`, all 4.0.0: `README.md` benchmark
    and dataset badges, `components/shared/Header.tsx`,
    `app/(scanner_mode)/runs/page.tsx`, `app/(scanner_mode)/corpus/page.tsx`;
    then regenerate `docs/scanner_mode/benchmark_spec.md` with
    `python docs/scanner_mode/spec_generator.py`. The leaderboard pools runs
    whose `BENCHMARK_VERSION` matches exactly, so bump it only when scores stop
    being comparable (a release-only change keeps it).
  Lab mode: `LAB_SCHEMA_VERSION`, `CASE_SCHEMA_VERSION`, `CEE_VERSION`,
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
- `backend/scanner_mode/cli/*.py` are legacy standalone CLI tools; they don't
  talk to the FastAPI server or the Prisma DB (`cli/CLI_README.md`).
- Frontend style: few comments, self-explanatory names.

## Docs map

- `docs/architecture.md` — the map: layers × drawers, how a request flows in
  each mode, where to add things.
- `MULTI_AGENT_LAB_PLAN.md` — the Lab-mode design spec that the `§N` comments
  in code cite. Removed in 4.1.5; read it from git history:
  `git show 6c3606a:MULTI_AGENT_LAB_PLAN.md`.
- `docs/` — also research paper draft, literature mapping, and
  `docs/scanner_mode/benchmark_spec.md` (generated).
- `PRODUCT.md` — product/design context.
- `graphify-out/` — deleted 2026-10-11; rebuild with `/graphify` before relying
  on it. Until then, read the docs above and the code directly.
