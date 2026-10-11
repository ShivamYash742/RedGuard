<!-- BEGIN:nextjs-agent-rules -->

# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->

# RedGuard — Agent Instructions

RedGuard is an AI agent security benchmark platform: a Next.js frontend and a
FastAPI backend. Mode A runs 46 adversarial "probes" (prompt injection, memory
poisoning, tool hijacking, goal diversion, etc.) plus 10 benign controls across
8 attack families against pluggable LLM agents, then scores and reports the
results; Mode B (`/lab`) tests a multi-agent system. See `README.md` for the full feature list and architecture
diagram, and `CLAUDE.md` for Claude-Code-specific notes.

## Layout

- `app/`, `components/`, `lib/` — Next.js 16 / React 19 / TypeScript frontend.
- `backend/` — FastAPI service (`app.py`), scanner/inspector engine, Prisma
  ORM over SQLite (`backend/prisma/`), pluggable model agents
  (`backend/agents/*.py`).
- `core/` — pure Python, imported by `backend/` (not the reverse): the probe
  JSON datasets (`core/datasets`), shared statistics (`core/benchmark`), and
  the Mode B lab (`core/lab`).
- `docs/` — architecture notes, benchmark spec, literature mapping.
- `scripts/` — legacy standalone CLI tools (`redteam_agent.py`,
  `dashboard.py`, `audit_report.py`, `add_custom_probes.py`). These do **not**
  talk to the FastAPI server or the Prisma DB — see `scripts/CLI_README.md`
  before assuming they're part of the live app.

## Setup

With Docker (no local installs): `docker compose up --build` — see the
README's "Run with Docker" section for tests, sweeps and the live-reload
override.

Without Docker:

```bash
npm ci
cd backend && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && cd ..
cp .env.example .env   # then fill in the keys for whichever agents you need
```

## Common commands

```bash
npm run dev:all        # frontend (:3000) + backend (:8000) together
npm run dev             # frontend only
npm run lint            # ESLint
npm run typecheck       # tsc --noEmit
npm run build            # production build
```

```bash
cd backend && source .venv/bin/activate
pytest tests/                 # backend: inspector, scanner, lab store/API
pytest ../core/tests/         # core: BDS metric, statistics, dataset schema, Mode B
```

There's no frontend test suite yet — validate UI changes with `npm run dev`
in a browser plus `lint`/`typecheck`.

## Conventions & gotchas

- **Probes are data.** The probes live as JSON in `core/datasets/*.json`,
  validated against `core/datasets/schema.json`. Add/edit probes there rather
  than hardcoding attack text in application code. If you move or rename a
  dataset file, update both `core/datasets/loader.py` and
  `lib/data-service.ts` — the frontend reads the same JSON.
- **Agents are auto-discovered plugins.** Any `.py` file in `backend/agents/`
  (not prefixed with `_`) is picked up automatically by
  `backend/agent_loader.py` as long as it defines `AGENT_NAME`,
  `AGENT_DESCRIPTION`, and an async `invoke(prompt)`. Copy
  `example_custom_agent.py` to add a new one rather than touching the loader.
- **`backend/prisma/dev.db` is intentionally committed** (whitelisted in
  `.gitignore` as demo seed data); regenerating it loses the seeded scan
  history. If your clone flags it assume-unchanged, `git stash` replaces your
  local copy with the committed one — copy it first.
- **`backend/policy.yaml`** drives rule-based detection in the inspector,
  separate from the ML classifier (`CLASSIFIER_URL` in `.env`). Changing it
  changes detection behavior, not just configuration.
- **Version numbers are canonical** in `core/version.py`
  (`BENCHMARK_VERSION`, `DATASET_VERSION`, `PROBE_SCHEMA_VERSION`). Nothing
  reads them at runtime on the frontend, so after a bump also update the copies
  listed in `CLAUDE.md` and run `python docs/spec_generator.py`.
- Don't remove the Next.js-managed block above this section — `next dev`
  regenerates it on its own; everything below it is safe to edit freely.
