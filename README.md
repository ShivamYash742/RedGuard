# RedGuard v4.1.5 🛡️ — AI Agent Security Benchmark Platform

[![Version](https://img.shields.io/badge/version-4.1.5-blue.svg)](./package.json)
[![Benchmark](https://img.shields.io/badge/benchmark-v4.0.0-indigo.svg)](./core/version.py)
[![Dataset](https://img.shields.io/badge/dataset-v4.0.0-emerald.svg)](./core/datasets)

RedGuard is an academic-grade **AI Agent Security Benchmark Platform** designed for empirical evaluation of Large Language Model (LLM) agent resistance against indirect prompt injections, goal diversion, persistent memory poisoning, autonomous execution risks, and tool hijacking.

The platform combines a research-focused **Next.js 16 frontend** (styled after Hugging Face Leaderboards, MLPerf, Weights & Biases, Kaggle, and OpenAI System Cards) with a **FastAPI backend engine**. It has two modes:

- **Mode A — probe scanner.** Single-turn adversarial probes against one agent: *what does one model do with an attack prompt?*
- **Mode B — multi-agent lab.** An attack planted in something one agent reads, followed through a chain of three agents: *what does the whole system do with it?*

---

## 🆕 What's new in 4.1.5

**Mode B UI and live dynamics**

- **Runs belong to the server.** An experiment runs as a server-owned task: closing or reloading the tab no longer stops it, any number of tabs can watch the same run, a reload rejoins it where it is, and Stop cancels it for every viewer. `/lab` marks running experiments with a live badge and their progress.
- **Live agent cards.** One card per agent with what it is doing now — *thinking 12 s* (ticking), *invalid reply, retrying*, *acted after 3 s*, *waiting for upstream*, or *finished* with the reason (called finish / used its whole step budget / gave up) — plus step *n* of max, its last action and target, refusals and invalid replies.
- **Swimlane timeline.** Time left to right, one row per agent: a bar for each model call (hatched when the reply was not a valid action) and a tick for each action, message and refusal. The replay page shows the same timeline with a cursor that follows the scrubber.
- **The stage follows every run.** Clean baselines are drawn too ("clean baseline, no attack planted"), not only attack runs.
- **Progress per run, with time.** The bar moves after every clean and attack run instead of every pair, with elapsed time and an ETA from the mean run duration; the position line reads `RGM-003 · rep 2/5 · attack run · step 14 · run 7 of 18`. A collapsible event feed lists the current run's events with their offsets.
- **Richer stream.** Every trace event carries its timestamp, the model call's latency, and the agent's turn and step budget; `run_finished` reports each run's duration, steps and invalid replies.
- **Experiment report.** After a run finishes, `/lab/experiments/[id]/report` shows the whole experiment — findings in plain language, setup, harness suitability, rates with 95% intervals, where attacks stopped, per agent, per case, run by run, and the trace evidence behind each verdict — with Markdown and JSON downloads. See [Experiment reports](#experiment-reports).
- **Launcher.** Defaults to local Ollama `granite3.3:2b`. *Instant demo (no model)* replays each case's script, optionally in slow motion (0.7 s per step) so A → B → C can be followed. *Test model* runs one case, one pair, and the experiment page warns when more than 10% of the model's replies are not valid actions.

**Local models can drive the harness.** With plain JSON mode, `granite3.3:2b` named the tool as the action (`{"action": "db_query", ...}`) on 12 of 14 steps (85.7% invalid). Ollama's decoding is now constrained to a JSON schema of the action protocol — `action` limited to the six kinds, `tool` to the real tools — and the same check gives **0 invalid replies in 60 steps**. The parser stays strict; only the vocabulary is constrained, and which action to take is still the model's choice. Granite still never calls `finish`, so its agents use their whole step budget; the report and the agent cards show this rather than hide it.

**Probe corpus (since 4.0.0).** The attack set went from 50 to **46 probes** and **10 benign controls** were added:

| Change | Probes | Why |
|---|---|---|
| Removed | RG-TM-003, RG-TM-004, RG-TM-005 | Parser attacks against an agent that has no parser: they could never succeed, so they only diluted the rates |
| Reclassified as a control | RG-GD-002 | A benign request, not an attack |
| Added controls | RG-CTL-001 … RG-CTL-009 | Harmless requests that measure over-refusal and regex false positives |

**Versions.** 4.1.5 is the release (the code, `package.json`, the UI). The benchmark, dataset and probe-schema versions stay **4.0.0**: Mode A scoring and the probe set did not change, so 4.0.0 results remain comparable and stay on the leaderboard.

---

## ✨ Key Features (v4.1.5)

| Feature | Description |
|---|---|
| **Measured Leaderboard** | One row per agent and system-prompt mode, from stored runs only: attack success with the regex filter off and on (Wilson 95% CIs), per-family resistance, over-refusal, and Behaviour Drift Score (BDS) |
| **Research Visualizations** | Recharts Radar Charts (Attack family comparison) and Stacked Outcome Distribution Bars (comparison page) |
| **6 Navigation Hubs** | Overview, Corpus (families/probes/scenarios), Runs (live execution & history), Models & Ranking, Lab (Mode B), & Settings — v3 consolidated the original 14 routes into 5, plus Mode B's own `/lab` |
| **Global Search (`⌘K`)** | Fast client-side fuzzy search overlay (`lib/search-index.ts`) matching Probe IDs, Titles, Attack Families, Scenarios, Models, and Reports |
| **8 Attack Families Taxonomy** | Direct Injection, Content Injection, Data Exfiltration, Goal Diversion, Memory Poisoning, Autonomous Actions, Planning Manipulation, & Tool Manipulation |
| **46 Attack Probes + 10 Benign Controls** | Auditable JSON dataset entries with research paper citations (arXiv IDs, venues, authors), difficulty levels, & threat models. Controls are harmless requests that measure over-refusal and regex false positives |
| **12 Application Scenarios** | GitHub, GitLab, Wiki, Documentation, Email, Calendar, Banking, Travel, Shopping, Support, Forum, & Reddit simulation environments |
| **Live SSE Execution Suite** | Real-time Server-Sent Events stream: every probe lands in one tier — Filtered (regex), Refused, Ignored or Compromised — with live counters per family; benign controls counted separately |
| **Tiered Scoring** | Each probe is scored with its own success/blocked indicators; the model sees every probe (even ones the regex blocks), so results exist both as deployed and for the model alone. Agents run with a neutral system prompt unless the run selects the hardened one |
| **Multi-Agent Lab (Mode B)** | 9 cases, 3 agents (A researcher → B validator → C executor), every action executed and recorded by the harness, 5 defence arms, four-dimension verdicts, clean control run for every attack run |
| **Live Run View (Mode B)** | Agent cards with a ticking status, per-agent swimlane timeline, stage for clean and attack runs, per-run progress with elapsed time and ETA, event feed — from any tab, after a reload |
| **Experiment Reports (Mode B)** | Generated from stored traces after a run: findings, suitability, rates with intervals, containment, per agent / case / run, evidence trail; Markdown & JSON |
| **Multi-Format Export** | Mode A reports in Markdown (`.md`) and CSV (`.csv`); Mode B experiment reports in Markdown and JSON, and per-run §12 evidence bundles |
| **BibTeX Citation Exporter** | Built-in academic citation snippet generator for research paper citations |

---

## 🏗️ Architecture Overview

```
                        RedGuard v4.1.5 Platform
                                   │
┌──────────────────────────────────┴──────────────────────────────────┐
│                      Next.js 16 Academic UI                         │
│ ├── Overview (6 Stat Scorecards)     ├── Corpus (Probes/Families/   │
│ ├── Runs (Live SSE Execution +           Scenarios/Datasets)        │
│ │      History)                      ├── Models & Ranking (Radar)   │
│ ├── Lab — Mode B launcher, live      ├── Settings (System/Policy/   │
│ │      view, replay & reports            Audit tabs)                │
│ └── Global Search Modal (⌘K)                                        │
│      (6 Navigation Hubs · 46 Probes + 10 Controls · 9 Mode B Cases) │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │ HTTP / SSE Stream
┌──────────────────────────────────┴──────────────────────────────────┐
│                      FastAPI Backend Engine                         │
│ Mode A                               Mode B                         │
│ ├── Inspector (YAML policy engine)   ├── CEE + ToolGateway          │
│ ├── ML Classifier (adversarial       ├── Topology / MessageBus      │
│ │      verdict)                      ├── CaseRunner (harness-owned  │
│ ├── Agent Loader (backend/agents/)   │      agent loop)             │
│ │  Nemotron-3 Ultra/Super, GPT OSS   ├── Evaluator (4-dim verdict)  │
│ │  120B/20B (Groq), Ollama           ├── Experiment jobs (server-   │
│ ├── Scanner & Report Generator       │      owned, SSE fan-out)     │
│ │                                    ├── Report builder             │
│ │                                    └── lab_api.py (/api/lab)      │
│ └── Prisma ORM → Local SQLite Database (5 Mode A + 3 Mode B models) │
└─────────────────────────────────────────────────────────────────────┘
```

### Mode B — the multi-agent security lab

Everything in the feature list up to Tiered Scoring is **Mode A**: single-turn
probes, each scored with its own indicators into one of four tiers (Filtered /
Refused / Ignored / Compromised). It answers *what does one model do with an
attack prompt?*

**Mode B** (`/lab`) answers a different question — *when an attacker hides an
instruction inside content an agent reads, what does the whole system of
agents actually do?* Three agents pass work along a chain, and the harness —
not the model — executes every action, so nothing is self-reported.

```
   Agent A                 Agent B                 Agent C
  researcher      →       validator       →       executor
  file_read               db_query                db_query
  web_search              state: read             state: read+write
        │                      │                       │
        └──── every tool call, message and state write ┘
              recorded by the harness, with provenance
```

The model proposes one JSON action per step (`tool_call`, `send_message`,
`state_read`, `state_write`, `report`, `finish`); the harness checks it against
the agent's permissions, executes it, and records it. Agents run in order —
A until it finishes, then B, then C — each with a step budget (default 10).

Each case runs **twice** — once with the attacker's artifact planted, once
without. The clean run is the control: without it, trajectory drift measures
model nondeterminism rather than attack effect.

The verdict has four dimensions and is deliberately never collapsed into a
single safe/unsafe score:

| Dimension | Answers |
|---|---|
| **Agent impact** | which agents were influenced or compromised |
| **Objective achievement** | did the attacker get what they wanted |
| **Containment** | where it stopped, and what stopped it |
| **System outcome** | did the benign task still complete |

Containment is the point. That an attack succeeded is ordinary; *where it
stopped and which control stopped it* is what tells you what to build.

Defence arms, compared case by case on `/lab/compare`:

| Arm | What it changes |
|---|---|
| No defence (`attack`) | strict tool authorization, no validation instruction |
| Prompt validation (`attack_validated`) | agents with an inbound edge are told to treat received content as data |
| Permissive tools (`attack_permissive_tools`) | every agent may call every tool, so tool-layer containment cannot occur |
| Bus filter (`attack_bus_gateway`) | the message bus refuses messages naming the targeted resources — an oracle upper bound |
| Capability gateway (`attack_capability_gateway`) | CaMeL-style: reads of resources the task never named are refused once untrusted content is in the caller's context |

#### Watching a run

Launch from `/lab` and the experiment page opens on the live view:

```
 5 / 18 runs ━━━━━━━━━━━━──────────  4 min elapsed · about 11 min left
 RGM-003 · rep 2/5 · attack run · step 14 · run 6 of 18   Agent B → db_query · vendor_contacts

 ┌ A · researcher ──── step 3 of 10 ┐ ┌ B · validator ───── step 2 of 10 ┐ ┌ C · executor ───────────┐
 │ finished · called finish         │ │ ● thinking 12 s                  │ │ waiting for upstream    │
 │ last: message → B                │ │ last: db_query · vendor_contacts │ │ no action yet           │
 └──────────────────────────────────┘ └──────────────────────────────────┘ └─────────────────────────┘
 A ▕████▏▕██████▏ │  ▕███▏ │
 B                              ▕█████▏│▕███████
 C
```

The run is executed by the server, so the page can be closed and reopened at
any time; a new viewer first receives the current run so far, then live
events.

#### Experiment reports

Every experiment has a report, built on demand from the stored traces and the
same metrics the experiment page shows — so it always agrees with the page,
including after a resume or a rescore, and never calls a model:

| Section | Contents |
|---|---|
| Summary | plain-language findings, each traceable to a number below |
| Setup | arm and its description, model, step budget, cases × repetitions, git commit, component versions |
| Execution | pairs completed / failed / unfinished, run statuses, total and mean run time, mean model call |
| Harness suitability | invalid replies against the 10% gate (§21.9), how agent turns ended |
| Results | ICR, ASR, partial, CPR, containment rate with 95% intervals and per-case means |
| Where attacks stopped | agent × mechanism over all valid attack runs |
| Agents | impact counts, steps, actions, tools, refusals, invalid replies, endings, model latency |
| Cases | every rate per case, objectives, where it stopped, trajectory drift against its clean null |
| Runs | each pair's verdict, agent impact, steps, time, refusals, link to the replay |
| Evidence | the events each verdict cites, plus the **attack trail**: every action descending from the planted artifact |
| Caveats | incomplete runs, excluded pairs, small samples, how intervals are computed |

Open it from the experiment page (*Report*), or fetch it:

```bash
curl localhost:8000/api/lab/experiments/<id>/report              # JSON
curl -OJ "localhost:8000/api/lab/experiments/<id>/report?format=md"  # Markdown file
```

#### Mode B API

| Endpoint | Purpose |
|---|---|
| `POST /api/lab/experiments` | create: arm, cases, repetitions, provider/model, `max_steps`, `scripted`, `step_delay_ms` |
| `POST /api/lab/experiments/{id}/start` · `/stop` | run it on the server (starting a running one joins it) · cancel it |
| `GET /api/lab/experiments/{id}/stream` | SSE: the current run so far, then live — any number of viewers |
| `GET /api/lab/experiments/{id}/run` | start-or-join and stream in one request (sweeps, scripts) |
| `GET /api/lab/experiments/{id}` | config, versions, runs, and `live` progress while running |
| `GET /api/lab/experiments/{id}/metrics` | ICR, ASR, CPR, containment, drift, per case |
| `GET /api/lab/experiments/{id}/report` | the report (JSON; `?format=md` for Markdown) |
| `GET /api/lab/compare?experiments=a,b` | cross-arm comparison with paired, per-case differences |
| `GET /api/lab/runs/{id}` · `/evidence` | one run's full trace · its §12 evidence bundle |
| `GET /api/lab/cases` · `/topologies` · `/fixtures` · `/arms` | the catalog |

Stream events: `experiment_started` (model, step budget, agents),
`run_started` (run *n* of total), `trace_event` (timestamp, latency, turn),
`run_finished` (duration, steps, invalid replies), `run_verdict`,
`case_rescored`, and one of `experiment_complete` / `experiment_stopped` /
`experiment_error`.

Mode B docs:
- Design: [`MULTI_AGENT_LAB_PLAN.md`](./MULTI_AGENT_LAB_PLAN.md)
- In plain language: [`MULTI_AGENT_LAB_EXPLAINED.md`](./MULTI_AGENT_LAB_EXPLAINED.md)
- What's built, bugs found, test inventory: [`MULTI_AGENT_LAB_PROGRESS.md`](./MULTI_AGENT_LAB_PROGRESS.md)
- Live view and server-owned runs: [`MODE_B_LIVE_PLAN.md`](./MODE_B_LIVE_PLAN.md)

Mode B is additive — no Mode A file, model, endpoint or verdict is affected.
No real-model Mode B results are published yet; every number so far is from
scripted runs or harness checks.

---

## 📁 Repository Structure

```
RedGuard/
├── app/                               # Next.js App Router pages
│   │                                  # v3 IA: 14 routes consolidated into 5 hubs
│   │                                  # + Mode B's own /lab section (old routes 301-redirect, see next.config.js)
│   ├── page.tsx                       # Overview — Dashboard (6 Research Cards + Taxonomy Grid)
│   ├── corpus/page.tsx                # Corpus — Probes, Attack Families & Scenarios (was /probes, /attack-families, /scenarios, /datasets)
│   │   ├── families/[familyId]/page.tsx
│   │   └── probes/[probeId]/page.tsx
│   ├── runs/page.tsx                  # Runs — Live SSE Execution Suite + History (was /benchmark, /history)
│   │   └── [sessionId]/page.tsx       # Run/session report (was /reports?session=)
│   ├── models/page.tsx                # Models & Ranking — Leaderboard, Radar Chart & Matrix (was /comparison)
│   ├── settings/page.tsx              # Settings — System Health, Policy & Citation, Audit Log tabs (was /policy, /audit)
│   ├── lab/page.tsx                   # Mode B — launcher (defence, cases, model, instant demo, Test model) & experiment list
│   │   ├── compare/page.tsx           # Cross-arm comparison
│   │   ├── experiments/[experimentId]/page.tsx         # Live view: stage, agent cards, swimlane, progress, ledger, rates
│   │   ├── experiments/[experimentId]/report/page.tsx  # Experiment report (Markdown / JSON download)
│   │   └── runs/[runId]/page.tsx      # Per-run replay: stage, scrubber, swimlane, timeline, environment diff
│   ├── globals.css                    # Academic surface tokens & badges
│   └── layout.tsx                     # Root layout with Header & Sidebar
│
├── components/                        # Shared UI components
│   ├── Header.tsx                     # Top Bar (Version badges, ⌘K Search, Theme)
│   ├── Sidebar.tsx                    # Nav: Overview, Corpus, Runs, Models, Lab, Settings
│   ├── ClientLayout.tsx               # Client-side layout wrapper
│   ├── GlobalSearchModal.tsx          # ⌘K Keyboard-Navigable Search Overlay
│   ├── ProbeDrawer.tsx                # Slide-over Metadata Inspection Drawer
│   ├── TierBar.tsx                    # Mode A outcome-tier bar
│   ├── LabRoute.tsx                   # Mode B propagation stage, route strips & glyphs
│   ├── AgentCards.tsx                 # Mode B live agent status cards
│   ├── AgentSwimlane.tsx              # Mode B per-agent timeline (live and replay)
│   ├── Skeletons.tsx                  # Table, Card & Chart Skeleton Loaders
│   └── EmptyState.tsx                 # Zero-data UI states
│
├── lib/                               # Frontend data services
│   ├── data-service.ts                # Singleton BenchmarkDataService & Cache (Mode A)
│   ├── lab-service.ts                 # Mode B API client, SSE stream, live route derivation
│   └── search-index.ts                # Client-side Search Index Engine
│
├── core/                              # Shared Python research library (importable by backend)
│   ├── datasets/                      # 8 JSON families: 46 attack probes + 10 benign controls — Mode A
│   │   ├── direct_injection.json      # 8 attacks + 2 controls
│   │   ├── content_injection.json     # 9 attacks + 1 control
│   │   ├── exfiltration.json          # 6 attacks + 2 controls
│   │   ├── goal_diversion.json        # 3 attacks + 1 control
│   │   ├── memory_poisoning.json      # 6 attacks + 1 control
│   │   ├── autonomy.json              # 5 attacks + 1 control
│   │   ├── planning.json              # 5 attacks + 1 control
│   │   ├── tool_security.json         # 4 attacks + 1 control
│   │   ├── schema.json                # Probe JSON schema definition
│   │   ├── loader.py                  # Dataset loader (used by FastAPI backend)
│   │   └── validator.py               # Schema validation utilities
│   ├── benchmark/                     # BDS, Wilson CIs, reproducibility stamp (shared by both modes)
│   ├── lab/                           # Multi-agent harness — Mode B (never imports backend/)
│   │   ├── cases/                     # 9 security test cases (JSON) + case_schema.json
│   │   ├── cee.py                     # Controlled Execution Environment
│   │   ├── topology.py                # Agent graph + MessageBus
│   │   ├── tools.py                   # ToolGateway (agent↔CEE authorization chokepoint)
│   │   ├── model_client.py            # The only network-touching module; action schema for Ollama
│   │   ├── runner.py                  # Harness-owned agent loop (CaseRunner)
│   │   ├── trace.py                   # EventCollector, provenance/taint closure
│   │   ├── evaluator.py               # 4-dimension verdict (impact/objective/containment/outcome)
│   │   ├── metrics.py / analysis.py   # Cross-run metrics & aggregation
│   │   ├── evidence.py                # Evidence bundle builder
│   │   ├── report.py                  # Experiment report (JSON + Markdown)
│   │   ├── repro.py                   # Reproducibility stamp
│   │   └── smoke.py                   # No-DB model-suitability smoke test (10% gate)
│   ├── version.py                     # Canonical Version Constants
│   └── __init__.py
│
├── backend/                           # FastAPI Service (:8000)
│   ├── app.py                         # FastAPI endpoints & CORS configuration — Mode A
│   ├── scanner.py                     # Scan loop, tiered scoring (score()) & SSE streams — Mode A
│   ├── inspector.py                   # Regex filter (attack-shape patterns) + policy.yaml rules — Mode A
│   ├── leaderboard.py                 # Measured leaderboard rows (/api/leaderboard) — Mode A
│   ├── agent_loader.py                # Plugin agent auto-discovery — Mode A
│   ├── database.py                    # Prisma ORM connection
│   ├── schema.py                      # Pydantic request/response schemas
│   ├── report_generator.py            # Evaluation report generation — Mode A
│   ├── target_agent.py                # Interactive CLI to chat with any agent — Mode A
│   ├── policy.yaml                    # YAML security policy rules — Mode A
│   ├── lab_api.py                     # Mode B HTTP surface (/api/lab/*), experiment jobs, SSE fan-out, report endpoint
│   ├── lab_store.py                   # Mode B persistence (Experiment/LabRun/TraceEvent)
│   ├── sweep.py                       # Mode B batch experiment CLI driver
│   ├── agents/                        # Configured Model Agents — Mode A
│   │   ├── nemotron_3_ultra.py        # Nemotron-3 Ultra (550B)
│   │   ├── nemotron_super_agent.py    # Nemotron-3 Super (120B)
│   │   ├── gpt_oss_120b_agent.py      # GPT OSS 120B (Groq)
│   │   ├── llama_3_1_8b_agent.py      # GPT OSS 20B (Groq; file name is historical)
│   │   ├── ollama_local_agent.py      # Ollama Local Agent (granite3.3:2b for the measured results)
│   │   ├── example_custom_agent.py    # Custom Template Agent
│   │   ├── _tools.py                  # Shared tools; file_read is confined to agents/sandbox/
│   │   └── system_prompts.json        # Neutral baseline prompt + per-agent hardened prompts
│   ├── tests/                         # Backend unit tests (inspector, scanner, lab_store, lab_api)
│   ├── prisma/schema.prisma           # Database schema (SQLite) — 5 Mode A models + 3 Mode B models
│   ├── prisma/dev.db                  # Local SQLite database (seeded demo data — see note below)
│   └── requirements.txt
│
├── docs/                              # Project documentation & research specs
│   ├── architecture.md                # System architecture
│   ├── benchmark_spec.md              # Probe specification (generated by spec_generator.py)
│   ├── literature_mapping.md          # Academic citations & literature mapping
│   ├── research_paper.md              # Benchmark research paper draft
│   └── spec_generator.py              # Spec auto-generator script
│
├── reports/                           # Generated benchmark reports; legacy-v3/ holds pre-4.0 reports
│
├── scripts/                           # Developer & research utility scripts (standalone, no DB)
│   ├── add_custom_probes.py           # Custom probe bulk-import script
│   ├── audit_report.py                # Standalone CLI audit report generator
│   ├── dashboard.py                   # Standalone CLI results dashboard
│   ├── redteam_agent.py               # Standalone CLI redteam agent
│   └── CLI_README.md                  # CLI documentation
│
├── MULTI_AGENT_LAB_*.md               # Mode B design, plain-language guide, progress log
├── MODE_A_FIX_PLAN.md / MODE_B_LIVE_PLAN.md   # Work plans with measured results
├── README.md
├── .env / .env.example
├── package.json                       # Frontend deps & dev:all script
├── next.config.js
├── tailwind.config.ts
└── tsconfig.json
```

---

## 🚀 Quick Start Guide

### Run with Docker (no local installs)

The only prerequisite is Docker with Compose v2. Python, Node, Prisma and every
dependency live in the images.

```bash
cp .env.example .env            # optional — only for the model providers you use
docker compose up --build       # UI http://localhost:3000 · API http://localhost:8000
```

The backend keeps its database on the `redguard-data` volume: on first start it
copies the committed demo data and adds the Mode B `lab_*` tables to that copy.
`backend/prisma/dev.db` itself is never written. `docker compose down -v` resets it.

Live-reload development (source bind-mounted, nothing installed on the host):

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
# after changing requirements.txt or package.json, add -V to refresh node_modules
```

Tests, sweeps and smoke runs inside the backend container:

```bash
docker compose run --rm backend python -m pytest ../core/tests tests -q
docker compose run --rm backend python -m core.lab.cases
docker compose run --rm backend python -m core.lab.smoke --scripted
docker compose run --rm backend python sweep.py --scripted --reps 2 --export /data/bundles
docker compose cp backend:/data/bundles ./bundles     # copy evidence bundles out
```

Notes:
- **Ollama on the host**: containers reach it at `http://host.docker.internal:11434`
  by default. Override with `DOCKER_OLLAMA_BASE_URL` in your shell or `.env`.
- **Reproducibility stamp**: there is no `.git` in the image, so build with
  `GIT_COMMIT=$(git rev-parse HEAD) docker compose build` to record the commit in
  every Mode B experiment (`git_clean` is then reported as unknown, never as clean).
- **One backend worker**: Mode B experiments run as tasks inside the backend
  process, so run uvicorn with a single worker (the default).

### 1. Prerequisites
- Node.js 20.9+ & `npm` (Next.js 16)
- Python 3.10+ & `pip` / `venv`
- Optional, for local models: [Ollama](https://ollama.com) with `ollama pull granite3.3:2b`

### 2. Installation
```bash
# Clone the repository
git clone https://github.com/ShivamYash742/RedGuard.git
cd RedGuard

# Install frontend dependencies
npm ci

# Setup backend Python environment
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
prisma generate --schema prisma/schema.prisma
cd ..
```

The committed `backend/prisma/dev.db` is demo seed data **without** the Mode B
`lab_*` tables, and CLAUDE.md asks that it not be written. To use `/lab` locally,
work on a copy:

```bash
cp backend/prisma/dev.db backend/prisma/local.db
DATABASE_URL="file:./local.db" backend/.venv/bin/prisma db push --schema backend/prisma/schema.prisma --skip-generate
# then set DATABASE_URL="file:./local.db" in .env
```

### 3. Environment Variables
Copy `.env.example` to `.env` and fill in the keys you need. `DATABASE_URL` is required for the Prisma/SQLite database; the rest are only needed for the specific agents you want to scan against:

| Variable | Used By |
|---|---|
| `DATABASE_URL` | Prisma ORM (SQLite, always required) |
| `NVIDIA_API_KEY` / `NVIDIA_MODEL` | Nemotron-3 Ultra & Super agents |
| `GROQ_API_KEY` / `GROQ_MODEL` | GPT OSS 120B / 20B agents |
| `OLLAMA_BASE_URL` / `OLLAMA_MODEL` | Ollama Local Agent and Mode B's Ollama provider (run `ollama serve` first) |
| `LAB_MODEL` | Mode B's default model when an experiment names none (default `granite3.3:2b`) |
| `CLASSIFIER_URL` | Optional ML classifier for a secondary verdict. Unset = no call; every probe is sent to this URL, so only use a service you run |
| `CORS_ORIGINS` | Origins allowed to call the API directly from a browser (default `http://localhost:3000`) |
| `WEBHOOK_URL` | Optional Slack/Discord webhook for post-scan alerts |

### 4. Running Locally
Start both Next.js frontend (port 3000) and FastAPI backend (port 8000) concurrently:
```bash
npm run dev:all
```

Or run them separately:
```bash
npm run dev                                                  # frontend only, :3000
cd backend && ./.venv/bin/python -m uvicorn app:app --reload --port 8000   # backend only, :8000
```

Then open [http://localhost:3000](http://localhost:3000) in your browser.

**Mode B on a local model.** Check the model can drive the harness first — the
gate is at most 10% invalid replies:

```bash
python -m core.lab.smoke --provider ollama --model granite3.3:2b
```

Then on `/lab`: pick a defence and cases, keep the provider on *ollama (local)*,
and *Launch and watch*; *Test model* runs a single case first. *Instant demo (no
model)* with *Slow motion* shows the whole pipeline without any model. When the
run finishes, open *Report*.

### 5. Running Tests & Checks
```bash
npm run lint                                                  # ESLint (Next.js config)
npm run typecheck                                              # tsc --noEmit

cd backend && source .venv/bin/activate
pytest tests/                                                  # backend: inspector, scanner, lab store/API/report
pytest ../core/tests/                                          # core: BDS, stats, dataset validation, all of Mode B
```

646 tests, about 15 s, no model calls.

---

## 📖 Citation

If you use RedGuard in academic publications, please cite:

```bibtex
@article{redguard2024,
  title={RedGuard: A Comprehensive Security Evaluation Benchmark for Autonomous LLM Agents},
  author={RedGuard Research Team},
  journal={arXiv preprint arXiv:2408.00000},
  year={2024}
}
```

---

## 📄 License

Distributed under the MIT License.
