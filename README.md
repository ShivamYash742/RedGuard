# RedGuard v4.0.0 🛡️ — AI Agent Security Benchmark Platform

[![Version](https://img.shields.io/badge/version-4.0.0-blue.svg)](file:///home/shivammishra/Pictures/RedGuard/core/version.py)
[![Benchmark](https://img.shields.io/badge/benchmark-v4.0.0-indigo.svg)](file:///home/shivammishra/Pictures/RedGuard/core/version.py)
[![Dataset](https://img.shields.io/badge/dataset-v4.0.0-emerald.svg)](file:///home/shivammishra/Pictures/RedGuard/core/datasets)

RedGuard is an academic-grade **AI Agent Security Benchmark Platform** designed for empirical evaluation of Large Language Model (LLM) agent resistance against indirect prompt injections, goal diversion, persistent memory poisoning, autonomous execution risks, and tool hijacking.

The platform combines a research-focused **Next.js 16 frontend** (styled after Hugging Face Leaderboards, MLPerf, Weights & Biases, Kaggle, and OpenAI System Cards) with a **FastAPI backend engine**.

---

## ✨ Key Features (v4.0.0)

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
| **Multi-Format Export** | Download evaluation benchmark reports in Markdown (`.md`) and CSV (`.csv`) formats |
| **BibTeX Citation Exporter** | Built-in academic citation snippet generator for research paper citations |

---

## 🏗️ Architecture Overview

```
                        RedGuard v4.0.0 Platform
                                   │
┌──────────────────────────────────┴──────────────────────────────────┐
│                      Next.js 16 Academic UI                          │
│ ├── Overview (6 Stat Scorecards)     ├── Corpus (Probes/Families/   │
│ ├── Runs (Live SSE Execution +          Scenarios/Datasets)          │
│ │      History)                      ├── Models & Ranking (Radar)   │
│ ├── Lab — Mode B launcher & traces   ├── Settings (System/Policy/   │
│ └── Global Search Modal (⌘K)             Audit tabs)                │
│        (6 Navigation Hubs · 46 Probes + 10 Controls · 9 Mode B Cases) │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │ HTTP / SSE Stream
┌──────────────────────────────────┴──────────────────────────────────┐
│                      FastAPI Backend Engine                          │
│ Mode A                                Mode B                        │
│ ├── Inspector (YAML policy engine)   ├── CEE + ToolGateway           │
│ ├── ML Classifier (adversarial       ├── Topology / MessageBus      │
│ │      verdict)                      ├── CaseRunner (harness-owned  │
│ ├── Agent Loader (backend/agents/)   │      agent loop)             │
│ │  Nemotron-3 Ultra/Super, Llama     ├── Evaluator (4-dim verdict)  │
│ │  3.3 70B, DeepSeek V4, Ollama      └── lab_api.py (SSE, /api/lab) │
│ ├── Scanner & Report Generator                                       │
│ └── Prisma ORM → Local SQLite Database (5 Mode A + 3 Mode B models)  │
└─────────────────────────────────────────────────────────────────────┘
```

### Mode B — the multi-agent security lab

Everything above is **Mode A**: single-turn probes, each scored with its own
indicators into one of four tiers (Filtered / Refused / Ignored / Compromised).
It answers *what does one model do with an attack prompt?*

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

- Design: [`MULTI_AGENT_LAB_PLAN.md`](./MULTI_AGENT_LAB_PLAN.md)
- Status, in plain language: [`MULTI_AGENT_LAB_PROGRESS.md`](./MULTI_AGENT_LAB_PROGRESS.md)

Mode B is additive — no Mode A file, model, endpoint or verdict is affected.

---

## 📁 Repository Structure

```
RedGuard/
├── app/                               # Next.js App Router pages (v4.0.0)
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
│   ├── lab/page.tsx                   # Mode B — case launcher & live runs
│   │   ├── experiments/[experimentId]/page.tsx
│   │   └── runs/[runId]/page.tsx      # Per-run trace viewer
│   ├── globals.css                    # Academic surface tokens & badges
│   └── layout.tsx                     # Root layout with Header & Sidebar
│
├── components/                        # Shared UI components
│   ├── Header.tsx                     # Top Bar (Version badges, ⌘K Search, Theme)
│   ├── Sidebar.tsx                    # Nav: Overview, Corpus, Runs, Models, Lab, Settings
│   ├── ClientLayout.tsx               # Client-side layout wrapper
│   ├── GlobalSearchModal.tsx          # ⌘K Keyboard-Navigable Search Overlay
│   ├── ProbeDrawer.tsx                # Slide-over Metadata Inspection Drawer
│   ├── Skeletons.tsx                  # Table, Card & Chart Skeleton Loaders
│   └── EmptyState.tsx                 # Zero-data UI states
│
├── lib/                               # Frontend data services
│   ├── data-service.ts                # Singleton BenchmarkDataService & Cache (Mode A)
│   ├── lab-service.ts                 # Mode B API client & SSE stream (/lab)
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
│   ├── lab/                           # Multi-agent harness — Mode B (frozen boundary: never imports backend/)
│   │   ├── cases/                     # 9 security test cases (JSON) + case_schema.json
│   │   ├── cee.py                     # Controlled Execution Environment
│   │   ├── topology.py                # Agent graph + MessageBus
│   │   ├── tools.py                   # ToolGateway (agent↔CEE authorization chokepoint)
│   │   ├── model_client.py            # The only network-touching module in core/lab/
│   │   ├── runner.py                  # Harness-owned agent loop (CaseRunner)
│   │   ├── trace.py                   # EventCollector, provenance/taint closure
│   │   ├── evaluator.py               # 4-dimension verdict (impact/objective/containment/outcome)
│   │   ├── metrics.py / analysis.py   # Cross-run metrics & aggregation
│   │   ├── evidence.py                # Evidence bundle builder
│   │   ├── repro.py                   # Reproducibility stamp
│   │   └── smoke.py                   # No-DB model-suitability smoke test
│   ├── version.py                     # Canonical Version Constants (v4.0.0)
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
│   ├── lab_api.py                     # Mode B HTTP surface (/api/lab/*, SSE experiment stream)
│   ├── lab_store.py                   # Mode B persistence (Experiment/LabRun/TraceEvent)
│   ├── sweep.py                       # Mode B batch experiment CLI driver
│   ├── agents/                        # Configured Model Agents — Mode A
│   │   ├── nemotron_3_ultra.py        # Nemotron-3 Ultra (550B)
│   │   ├── nemotron_super_agent.py    # Nemotron-3 Super (120B)
│   │   ├── gpt_oss_120b_agent.py      # GPT OSS 120B (Groq)
│   │   ├── llama_3_1_8b_agent.py      # GPT OSS 20B (Groq; file name is historical)
│   │   ├── ollama_local_agent.py      # Ollama Local Agent
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
├── reports/                           # Generated benchmark reports (JSON & MD)
│
├── scripts/                           # Developer & research utility scripts
│   ├── add_custom_probes.py           # Custom probe bulk-import script
│   ├── audit_report.py                # Standalone CLI audit report generator
│   ├── dashboard.py                   # Standalone CLI results dashboard
│   ├── redteam_agent.py               # Standalone CLI redteam agent
│   └── CLI_README.md                  # CLI documentation
│
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

### 1. Prerequisites
- Node.js 20.9+ & `npm` (Next.js 16)
- Python 3.10+ & `pip` / `venv`

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
| `NVIDIA_API_KEY` / `NVIDIA_MODEL` | Nemotron-3 Ultra & Super agents (default agents) |

| `GOOGLE_API_KEY` / `GEMINI_MODEL` | Gemini Flash agent |
| `OLLAMA_BASE_URL` / `OLLAMA_MODEL` | Ollama Local Agent (run `ollama serve` first) |
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

### 5. Running Tests & Checks
```bash
npm run lint                                                  # ESLint (Next.js config)
npm run typecheck                                              # tsc --noEmit

cd backend && source .venv/bin/activate
pytest tests/                                                  # backend: inspector, scanner, lab store/API
pytest ../core/tests/                                          # core: BDS, stats, dataset validation, all of Mode B
```

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
