# CLAUDE.md

Project-specific guidance for Claude Code when working in this repository. This
complements `AGENTS.md` (general agent/setup instructions) — read that one too.
See `README.md` for the full feature overview and architecture diagram.

## What this is

RedGuard has **two modes that answer different questions**. Know which one you
are working in before changing anything.

**Mode A — the probe benchmark (the original).** Fires 50 adversarial
"probes" (prompt injection, memory poisoning, tool hijacking, etc.) across 8
attack families and 12 simulated scenarios at a pluggable set of LLM agents,
then scores replies against refusal-keyword rules. Lives in `backend/`
(scanner, inspector, agents) and `core/datasets`, `core/probes`,
`core/scenarios`. Routes: `/`, `/corpus`, `/runs`, `/models`, `/settings`.

**Mode B — the multi-agent lab (`core/lab/`, `backend/lab_*`, `/lab`).**
Answers what a *system* of agents did after an attack entered it: which agent
was influenced, how far it propagated, where it was contained. The model
proposes one JSON action per step and the harness executes it, so every event
is observed rather than self-reported. See
[`MULTI_AGENT_LAB_PLAN.md`](./MULTI_AGENT_LAB_PLAN.md) for the design and
[`MULTI_AGENT_LAB_PROGRESS.md`](./MULTI_AGENT_LAB_PROGRESS.md) for what is
built (that one opens with a plain-language summary).

**Mode B is additive and Mode A is frozen.** No Mode B change may touch
`scanner.py`, `inspector.py`, `agent_loader.py`, `backend/agents/*`,
`core/datasets/*`, `core/probes/*`, `core/scenarios/*`, the 5 original Prisma
models, or any existing endpoint. The only shared surfaces are additive
constants in `core/version.py` and a Wilson-CI helper imported from
`core.benchmark.statistics`. The refusal-keyword list is **copied, not
imported**, so Mode B cannot alter Mode A's verdicts.

Two halves of the codebase matter and don't overlap much:
- **`app/`, `components/`, `lib/`** — Next.js 16 / React 19 / TypeScript UI.
- **`backend/`, `core/`** — FastAPI service + the benchmark libraries.
  `core/` is pure Python and is imported by `backend/` (`sys.path` hack in
  `backend/app.py`), never the other way around — including `core/lab/`,
  which must not import anything from `backend/`.

## Commands

```bash
npm run dev:all       # frontend (:3000) + backend (:8000) together
npm run lint           # ESLint
npm run typecheck      # tsc --noEmit
```

```bash
cd backend && source .venv/bin/activate
pytest tests/                 # backend: inspector, scanner, lab_store, lab_api
pytest ../core/tests/         # core: BDS metric, statistics, schema validation, all of Mode B
pytest ../core/tests/ tests/  # everything (471 tests, no LLM needed)
```

Mode B has its own entry points, none of which need an LLM except `smoke`:

```bash
python -m core.lab.cases                     # validate the 9 security test cases
python -m core.lab.smoke --scripted          # whole pipeline, no model calls
python -m core.lab.smoke --provider nvidia --model nvidia/nemotron-3-super-120b-a12b

cd backend
DATABASE_URL="file:/tmp/sweep.db" python sweep.py --scripted --reps 2
DATABASE_URL="file:/tmp/sweep.db" python sweep.py --report <experiment_ids>
```

There is no frontend test suite currently — verify UI changes by running
`npm run dev` and checking the page in a browser, plus `lint`/`typecheck`.

## Conventions in this repo

- **Attack family datasets are data, not code.** The 50 probes live as JSON in
  `core/datasets/*.json` (validated against `core/datasets/schema.json`).
  Prefer editing/adding JSON entries over hardcoding probe text in TypeScript
  or Python. `lib/data-service.ts` reads from `core/datasets` — if you move a
  dataset file, update the loader on both sides (`core/datasets/loader.py`
  and `lib/data-service.ts`).
- **Agents are auto-discovered plugins.** Everything in `backend/agents/*.py`
  is picked up automatically by `backend/agent_loader.py` (any `.py` file not
  prefixed with `_`). A new agent just needs module-level `AGENT_NAME`,
  `AGENT_DESCRIPTION`, and an async `invoke(prompt)` — copy
  `example_custom_agent.py` rather than editing the loader.
- **`backend/prisma/dev.db` is intentionally committed.** It's whitelisted in
  `.gitignore` (`*.db` / `!backend/prisma/dev.db`) as seed data for the demo
  UI. Don't `rm` or `.gitignore` it without checking with the user first —
  regenerating it from scratch loses the seeded scan history.
  **Two traps worth knowing:** `git status` will not show changes to it —
  it is flagged `assume-unchanged` (`git ls-files -v` shows `h`), so verify
  by querying row counts, not by trusting git. And `npm run dev:all` points
  the backend at this file, so any lab experiment launched that way writes
  into the committed demo data. Point `DATABASE_URL` at a copy when running
  experiments.
- **Mode B cases are data too.** The 9 security test cases live as JSON in
  `core/lab/cases/*.json` with a schema of record beside them, loaded and
  validated by `core/lab/cases.py`. Each ships a `clean_script` — a compliant
  action sequence that powers two CI checks: the clean trace must complete
  the benign task, and must *not* satisfy the attacker's objective. A case
  whose objective is reachable by ordinary task completion measures task
  behaviour, not attack effect.
- **`policy.yaml`** (`backend/policy.yaml`) drives the inspector's rule-based
  detection layer, separate from the ML classifier (`CLASSIFIER_URL`). Treat
  changes to it as changes to detection behavior, not just config.
- **Version numbers are centralized** in `core/version.py`
  (`BENCHMARK_VERSION`, `DATASET_VERSION`, `PROBE_SCHEMA_VERSION`). The README
  badges and `app/datasets/page.tsx` read from the same source of truth —
  bump there, not by hand-editing badges. Mode B adds six of its own
  (`LAB_SCHEMA_VERSION`, `CASE_SCHEMA_VERSION`, `CEE_VERSION`,
  `TOPOLOGY_VERSION`, `EVALUATOR_VERSION`, `METRIC_VERSION`) exposed through a
  *separate* `get_lab_version_info()`, so Mode A consumers see no new keys.
  Bumping `METRIC_VERSION` means previously published numbers are no longer
  comparable — that is why it is separate from the rest.
- No frontend comments beyond what's already there; this codebase generally
  favors self-explanatory names over comments — match existing style.

## Things to leave alone

- The `<!-- BEGIN:nextjs-agent-rules --> ... <!-- END:nextjs-agent-rules -->`
  block in `AGENTS.md` is regenerated by `next dev` itself
  (`node_modules/next/dist/server/lib/generate-agent-files.js`). Don't delete
  it; edits outside that block are yours to keep.
- `scripts/*.py` (`redteam_agent.py`, `dashboard.py`, `audit_report.py`,
  `add_custom_probes.py`) are legacy standalone CLI tools kept for offline use
  — they don't talk to the FastAPI server or Prisma DB. Don't assume they're
  wired into the current web app (see `scripts/CLI_README.md`).
