# RedGuard v2.7.5 🛡️ — AI Agent Security Benchmark Platform

[![Version](https://img.shields.io/badge/version-2.7.5-blue.svg)](file:///home/shivammishra/Pictures/RedGuard/core/version.py)
[![Benchmark](https://img.shields.io/badge/benchmark-v2.7.5-indigo.svg)](file:///home/shivammishra/Pictures/RedGuard/core/version.py)
[![Dataset](https://img.shields.io/badge/dataset-v2.7.5-emerald.svg)](file:///home/shivammishra/Pictures/RedGuard/core/datasets)

RedGuard is an academic-grade **AI Agent Security Benchmark Platform** designed for empirical evaluation of Large Language Model (LLM) agent resistance against indirect prompt injections, goal diversion, persistent memory poisoning, autonomous execution risks, and tool hijacking.

The platform combines a research-focused **Next.js 16 frontend** (styled after Hugging Face Leaderboards, MLPerf, Weights & Biases, Kaggle, and OpenAI System Cards) with a **FastAPI backend engine**.

---

## ✨ Key Features (v2.7.5)

| Feature | Description |
|---|---|
| **Academic Leaderboard & Ranking** | Multi-model ranking across Attack Success Rate (ASR), Behaviour Drift Score (BDS), Security Score, & Tool Resistance |
| **Research Visualizations** | Recharts Radar Charts (Attack family comparison) and Stacked Outcome Distribution Bars (comparison page) |
| **10 Navigation Hubs** | Dedicated sections for Dashboard, Benchmark Execution, Attack Families, Probes, Scenarios, Models & Ranking, Reports & Results, Datasets, Documentation, & Settings |
| **Global Search (`⌘K`)** | Fast client-side fuzzy search overlay (`lib/search-index.ts`) matching Probe IDs, Titles, Attack Families, Scenarios, Models, and Reports |
| **8 Attack Families Taxonomy** | Direct Injection, Content Injection, Data Exfiltration, Goal Diversion, Memory Poisoning, Autonomous Actions, Planning Manipulation, & Tool Manipulation |
| **50 Empirical Probes** | Auditable JSON dataset entries with research paper citations (arXiv IDs, venues, authors), difficulty levels, & threat models |
| **12 Application Scenarios** | GitHub, GitLab, Wiki, Documentation, Email, Calendar, Banking, Travel, Shopping, Support, Forum, & Reddit simulation environments |
| **Live SSE Execution Suite** | Real-time Server-Sent Events stream tracking family progress, live resisted/compromised counters, and pulse border feedback |
| **Multi-Format Export** | Download evaluation benchmark reports in Markdown (`.md`) and CSV (`.csv`) formats |
| **BibTeX Citation Exporter** | Built-in academic citation snippet generator for research paper citations |

---

## 🏗️ Architecture Overview

```
                        RedGuard v2.7.5 Platform
                                   │
┌──────────────────────────────────┴──────────────────────────────────┐
│                      Next.js 16 Academic UI                          │
│ ├── Dashboard (6 Stat Scorecards)    ├── Probes Directory & Drawer  │
│ ├── Live SSE Benchmark Executor      ├── 12 Scenario Contexts       │
│ ├── 8 Attack Family Taxonomy Pages   ├── Leaderboard & Radar Charts  │
│ └── Global Search Modal (⌘K)         └── Reports Export (MD/CSV)    │
│                      (10 Navigation Hubs · 50 Empirical Probes)     │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │ HTTP / SSE Stream
┌──────────────────────────────────┴──────────────────────────────────┐
│                      FastAPI Backend Engine                          │
│ ├── Inspector (Deep Packet Inspection & YAML policy engine)         │
│ ├── ML Classifier (Intent detection & adversarial verdict)           │
│ ├── Agent Loader (Discovers *.py modules in backend/agents/)        │
│ │      ├── Nemotron-3 Ultra (550B)   ├── DeepSeek V4 Flash         │
│ │      ├── Nemotron-3 Super (120B)   ├── Ollama Local Agent        │
│ │      ├── Llama 3.3 70B Instruct    └── Custom Agent Template     │
│ ├── Scanner & Report Generator                                       │
│ └── Prisma ORM → Local SQLite Database                               │
└─────────────────────────────────────────────────────────────────────┘
```

### Mode B — the multi-agent security lab

Everything above is **Mode A**: single-turn probes scored against
refusal-keyword rules. It answers *did the model say something bad?*

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
├── app/                               # Next.js App Router pages (v2.7.5)
│   ├── page.tsx                       # Dashboard (6 Research Cards + Taxonomy Grid)
│   ├── benchmark/page.tsx             # Live Execution Suite (SSE Progress Tracker)
│   ├── attack-families/               # Attack Family Index & Detail Pages
│   │   └── [familyId]/page.tsx
│   ├── probes/                        # Probes Inventory & Canonical Probe Page
│   │   └── [probeId]/page.tsx
│   ├── scenarios/page.tsx             # 12 Application Scenario Cards
│   ├── comparison/page.tsx            # Model Leaderboard, Radar Chart & Matrix
│   ├── reports/page.tsx               # Security Scorecards & Export (MD / CSV)
│   ├── history/page.tsx               # Execution Run Timeline Log
│   ├── datasets/page.tsx              # Dataset Version 2.7.5 & Schema Status
│   ├── policy/page.tsx                # Policy Editor & BibTeX Citation Generator
│   ├── audit/page.tsx                 # Audit Event Log Viewer
│   ├── settings/page.tsx              # FastAPI & Database Health Monitor
│   ├── globals.css                    # Academic surface tokens & badges
│   └── layout.tsx                     # Root layout with Header & Sidebar
│
├── components/                        # Shared UI components
│   ├── Header.tsx                     # Top Bar (Version badges, ⌘K Search, Theme)
│   ├── Sidebar.tsx                    # 10 Research Navigation Items
│   ├── ClientLayout.tsx               # Client-side layout wrapper
│   ├── GlobalSearchModal.tsx          # ⌘K Keyboard-Navigable Search Overlay
│   ├── ProbeDrawer.tsx                # Slide-over Metadata Inspection Drawer
│   ├── StatCard.tsx                   # Dashboard stat card component
│   ├── Skeletons.tsx                  # Table, Card & Chart Skeleton Loaders
│   ├── EmptyState.tsx                 # Zero-data UI states
│   └── ui/                            # Shared UI primitives (button, card, badge…)
│
├── lib/                               # Frontend data services
│   ├── data-service.ts                # Singleton BenchmarkDataService & Cache
│   ├── search-index.ts                # Client-side Search Index Engine
│   └── utils.ts                       # Shared utility functions
│
├── core/                              # Shared Python research library (importable by backend)
│   ├── datasets/                      # 8 JSON Attack Family Datasets (50 Probes total)
│   │   ├── direct_injection.json      # 8 probes
│   │   ├── content_injection.json     # 9 probes
│   │   ├── exfiltration.json          # 6 probes
│   │   ├── goal_diversion.json        # 4 probes
│   │   ├── memory_poisoning.json      # 6 probes
│   │   ├── autonomy.json              # 5 probes
│   │   ├── planning.json              # 5 probes
│   │   ├── tool_security.json         # 7 probes
│   │   ├── schema.json                # Probe JSON schema definition
│   │   ├── loader.py                  # Dataset loader (used by FastAPI backend)
│   │   └── validator.py               # Schema validation utilities
│   ├── probes/                        # Probe class definitions per family
│   ├── scenarios/                     # 12 scenario context classes
│   ├── version.py                     # Canonical Version Constants (v2.7.5)
│   └── __init__.py
│
├── backend/                           # FastAPI Service (:8000)
│   ├── app.py                         # FastAPI endpoints & CORS configuration
│   ├── scanner.py                     # Scanner orchestration & SSE streams
│   ├── inspector.py                   # Regex & YAML policy rules engine
│   ├── agent_loader.py                # Plugin agent auto-discovery
│   ├── database.py                    # Prisma ORM connection
│   ├── schema.py                      # Pydantic request/response schemas
│   ├── report_generator.py            # Evaluation report generation
│   ├── target_agent.py                # Target agent wrapper
│   ├── policy.yaml                    # YAML security policy rules
│   ├── agents/                        # Configured Model Agents
│   │   ├── nemotron_3_ultra.py        # Nemotron-3 Ultra (550B)
│   │   ├── nemotron_super_agent.py    # Nemotron-3 Super (120B)
│   │   ├── llama3_3_70b_agent.py      # Llama 3.3 70B Instruct
│   │   ├── deepseek_flash_agent.py    # DeepSeek V4 Flash
│   │   ├── ollama_local_agent.py      # Ollama Local Agent
│   │   └── example_custom_agent.py    # Custom Template Agent
│   ├── tests/                         # Backend unit tests
│   │   ├── test_inspector.py
│   │   └── test_scanner.py
│   ├── prisma/schema.prisma           # Database schema (SQLite)
│   ├── prisma/dev.db                  # Local SQLite database
│   └── requirements.txt
│
├── docs/                              # Project documentation & research specs
│   ├── architecture.md                # System architecture
│   ├── benchmark_spec.md              # 50-probe formal specification
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

### 1. Prerequisites
- Node.js 18+ & `npm`
- Python 3.10+ & `pip` / `venv`

### 2. Installation
```bash
# Clone the repository
git clone https://github.com/ShivamYash742/RedGuard.git
cd RedGuard

# Install frontend dependencies
npm install

# Setup backend Python environment
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd ..
```

### 3. Environment Variables
Copy `.env.example` to `.env` and fill in the keys you need. `DATABASE_URL` is required for the Prisma/SQLite database; the rest are only needed for the specific agents you want to scan against:

| Variable | Used By |
|---|---|
| `DATABASE_URL` | Prisma ORM (SQLite, always required) |
| `NVIDIA_API_KEY` / `NVIDIA_MODEL` | Nemotron-3 Ultra & Super agents (default agents) |

| `GOOGLE_API_KEY` / `GEMINI_MODEL` | Gemini Flash agent |
| `OLLAMA_BASE_URL` / `OLLAMA_MODEL` | Ollama Local Agent (run `ollama serve` first) |
| `CLASSIFIER_URL` | ML classifier endpoint used for secondary verdicts during a scan |
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
pytest tests/                                                  # backend unit tests (inspector, scanner)
pytest ../core/tests/                                          # core benchmark/dataset tests (BDS, stats, schema validation)
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
