# RedGuard architecture — where everything lives

RedGuard tests AI agents for security in two ways:

| Mode | Question it answers | How |
|---|---|---|
| **Scanner mode** (was "Mode A") | What does *one* model do with an attack prompt? | Fires 46 adversarial probes and 10 harmless controls at one agent and scores each reply: Filtered, Refused, Ignored or Compromised. |
| **Lab mode** (was "Mode B") | When an attack hides in content an agent reads, what does a *chain* of agents do with it? | Three agents (A researcher → B validator → C executor) work in a simulated environment; the harness executes every action, plants the attack, runs a clean control, and judges four dimensions. |

## The one rule

**Every layer has the same three drawers: `shared/`, `scanner_mode/`, `lab_mode/`.**
Scanner mode and Lab mode never import each other; `shared/` may be used by
both. Two checks keep it true: `core/tests/shared/test_mode_boundaries.py`
(Python) and a `no-restricted-imports` rule in `eslint.config.mjs` (TypeScript).

| Layer | `shared/` | `scanner_mode/` | `lab_mode/` |
|---|---|---|---|
| **Pages** `app/` | `/` overview, `/settings`, layout | `(scanner_mode)/` → `/corpus`, `/runs`, `/models` | `(lab_mode)/` → `/lab/…` |
| **UI parts** `components/` | header, sidebar, search, empty states, skeletons | probe drawer, tier bar | propagation stage, agent cards, swimlane |
| **UI data** `lib/` | — | `data-service.ts`, `search-index.ts` | `lab-service.ts` |
| **API** `backend/` | `app.py` (app, CORS, `/api/health`), `request_guard.py` (Origin and JSON checks on every route), `database.py`, `prisma/` | `api.py` (all `/api/…` scan routes), scanner, inspector + `policy.yaml`, agents (one scaffold, shared tools and prompts, mock action tools, fixture-backed read tools, sandbox), leaderboard, reports, `filter_eval.py`, `cli/` | `api.py` (`/api/lab/…`), `store.py`, `sweep.py` |
| **Library** `core/` | `version.py`, `statistics.py`, `reproducibility.py` | `datasets/` (the probe corpus), `benign_sets/` (XSTest safe prompts), `bds.py` | harness: environment, topology, tools, model client, runner, trace, evaluator, metrics, report, cases |
| **Tests** | `core/tests/shared/`, `backend/tests/conftest.py` | `core/tests/scanner_mode/`, `backend/tests/scanner_mode/` | `core/tests/lab_mode/`, `backend/tests/lab_mode/` |
| **Docs** | this file, `research_paper.md`, `literature_mapping.md` | `scanner_mode/benchmark_spec.md` (+ its generator) | — |

Folders in parentheses under `app/` are Next.js route groups: they organise
files without appearing in the URL, so `/corpus` and `/lab` are unchanged.
`core/` is a pure library (no HTTP, no database) and never imports `backend/`.

## How a request flows

**Scanner mode — a scan**

```
/runs page ──► lib/scanner_mode/data-service.ts
           ──► POST /api/scan/start, GET /api/scan/family (SSE)       backend/scanner_mode/api.py
           ──► scanner.py: for each probe in core/scanner_mode/datasets/
                 inspector.py + policy.yaml  (regex filter)
                 agents/<agent>.py + _scaffold.py  (the model under test, in the shared scaffold)
                 score()                      → Filtered / Refused / Ignored / Compromised
           ──► Prisma (backend/prisma/)      → /models leaderboard, /runs/<id> report
```

**Lab mode — an experiment**

```
/lab page ──► lib/lab_mode/lab-service.ts
          ──► POST /api/lab/experiments, …/start, GET …/stream (SSE)   backend/lab_mode/api.py
          ──► a server-owned job runs each case twice (clean + attack) with core/lab_mode/:
                cases/ + fixtures/   what is planted where
                runner.py            asks the model for one JSON action per step (model_client.py)
                tools.py, topology.py  the harness checks permissions and executes it
                trace.py             every event, with provenance
                evaluator.py         four-dimension verdict
          ──► store.py → Prisma      → /lab/experiments/<id> live view, /report, /lab/runs/<id> replay
```

## Where to add things

| To add… | Put it in |
|---|---|
| a probe | `core/scanner_mode/datasets/<family>.json` (validated by `schema.json`; score it with `success_actions`, a `canary`, or compliance-phrase `success_indicators`; plant indirect payloads in `tool_fixtures`; bump `DATASET_VERSION`; cite only arXiv papers listed in `core/tests/scanner_mode/verified_arxiv.json`) |
| an agent to scan | `backend/scanner_mode/agents/<name>.py` with `AGENT_NAME`, `AGENT_DESCRIPTION`, `model_config()`, an LLM factory and an async `invoke()` that calls `_scaffold.run_agent` (the model is the only thing that may differ) — discovered automatically |
| a Lab case | `core/lab_mode/cases/RGM-0xx.json` (validated by `case_schema.json`, needs a `clean_script`, exact `arg_equals` names in tool-call predicates, a `role` and `objective_reachable_in_arms`) |
| a Scanner page / API route | `app/(scanner_mode)/…` / `backend/scanner_mode/api.py` |
| a Lab page / API route | `app/(lab_mode)/lab/…` / `backend/lab_mode/api.py` |
| something both modes use | the layer's `shared/` |

## Commands

```bash
npm run dev:all                                     # UI :3000 + API :8000
cd backend && pytest ../core/tests tests            # every test, no model calls

python -m core.lab_mode.cases                       # validate the Lab cases
python -m core.lab_mode.smoke --scripted            # Lab pipeline without a model
cd backend && python -m lab_mode.sweep --help       # Lab batch runs
cd backend && python -m scanner_mode.target_agent   # chat with a Scanner agent
python docs/scanner_mode/spec_generator.py          # regenerate the probe spec
```

Code comments and test names written before 4.2.0 still say "Mode A" and
"Mode B"; read them as Scanner mode and Lab mode.
