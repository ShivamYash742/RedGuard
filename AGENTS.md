<!-- BEGIN:nextjs-agent-rules -->

# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->

# RedGuard — Agent Instructions

RedGuard is an AI agent security benchmark platform: a Next.js frontend and a
FastAPI backend. **Scanner mode** (formerly Mode A) runs 46 adversarial
"probes" (prompt injection, memory poisoning, tool hijacking, goal diversion,
etc.) plus 10 benign controls across 8 attack families against pluggable LLM
agents, then scores and reports the results; **Lab mode** (formerly Mode B,
`/lab`) tests a multi-agent system. See `docs/architecture.md` for where
everything lives, `README.md` for the feature list, and `CLAUDE.md` for
Claude-Code-specific notes.

## Layout

Every layer has the same three drawers — `shared/`, `scanner_mode/`,
`lab_mode/` — and the two modes never import each other (a test and a lint
rule enforce it).

- `app/` — Next.js 16 / React 19 pages: shared `page.tsx`, `settings/`; route
  groups `(scanner_mode)/` (corpus, runs, models) and `(lab_mode)/` (lab).
- `components/{shared,scanner_mode,lab_mode}/`, `lib/{scanner_mode,lab_mode}/`.
- `backend/` — FastAPI (`app.py` mounts `scanner_mode/api.py` and
  `lab_mode/api.py`), shared `database.py` and Prisma over SQLite
  (`backend/prisma/`); Scanner-mode agents in `backend/scanner_mode/agents/*.py`.
- `core/` — pure Python, imported by `backend/` (not the reverse):
  `core/shared` (versions, statistics), `core/scanner_mode` (probe datasets,
  BDS), `core/lab_mode` (the multi-agent harness).
- `docs/` — `architecture.md` (the map), research paper, literature mapping,
  `scanner_mode/benchmark_spec.md`.
- `backend/scanner_mode/cli/` — legacy standalone CLI tools (`redteam_agent.py`,
  `dashboard.py`, `audit_report.py`, `add_custom_probes.py`), run from
  `backend/` as `python -m scanner_mode.cli.<name>`. These do **not** talk to
  the FastAPI server or the Prisma DB — see `cli/CLI_README.md` before assuming
  they're part of the live app.

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
pytest tests/                 # backend: scanner_mode/, lab_mode/
pytest ../core/tests/         # core: shared/, scanner_mode/, lab_mode/
```

There's no frontend test suite yet — validate UI changes with `npm run dev`
in a browser plus `lint`/`typecheck`.

## Conventions & gotchas

- **Probes are data.** The probes live as JSON in `core/scanner_mode/datasets/*.json`,
  validated against `core/scanner_mode/datasets/schema.json`. Add/edit probes there rather
  than hardcoding attack text in application code. If you move or rename a
  dataset file, update both `core/scanner_mode/datasets/loader.py` and
  `lib/scanner_mode/data-service.ts` — the frontend reads the same JSON.
- **Agents are auto-discovered plugins.** Any `.py` file in `backend/scanner_mode/agents/`
  (not prefixed with `_`) is picked up automatically by
  `backend/scanner_mode/agent_loader.py` as long as it defines `AGENT_NAME`,
  `AGENT_DESCRIPTION`, and an async `invoke(prompt)`. Copy
  `example_custom_agent.py` to add a new one rather than touching the loader.
- **`backend/prisma/dev.db` is intentionally committed** (whitelisted in
  `.gitignore` as demo seed data); regenerating it loses the seeded scan
  history. If your clone flags it assume-unchanged, `git stash` replaces your
  local copy with the committed one — copy it first.
- **`backend/scanner_mode/policy.yaml`** drives rule-based detection in the inspector,
  separate from the ML classifier (`CLASSIFIER_URL` in `.env`). Changing it
  changes detection behavior, not just configuration.
- **Version numbers are canonical** in `core/shared/version.py`
  (`BENCHMARK_VERSION`, `DATASET_VERSION`, `PROBE_SCHEMA_VERSION`). Nothing
  reads them at runtime on the frontend, so after a bump also update the copies
  listed in `CLAUDE.md` and run `python docs/scanner_mode/spec_generator.py`.
- Don't remove the Next.js-managed block above this section — `next dev`
  regenerates it on its own; everything below it is safe to edit freely.
