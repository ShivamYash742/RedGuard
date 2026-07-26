# RedGuard 🛡️

RedGuard is a unified **Next.js dashboard** + **FastAPI backend** for autonomous red-teaming of LLM-based agents, built on the [Franklin et al. 2025 Google DeepMind AI Agent Traps](https://deepmind.google/research/publications/ai-agent-traps/) taxonomy.

It runs **adversarial probes** against any LLM agent of your choice, inspects every prompt through a Deep Packet Inspection (DPI) layer and an ML classifier, then generates comprehensive audit reports — all from a slick browser UI.

---

## ✨ Features

| Feature | Description |
|---|---|
| **One-Click Scans** | Trigger a full 24-probe red-team scan against any agent directly from the UI |
| **Plug-in Agents** | Drop a Python file in `backend/agents/` — it appears in the UI selector instantly |
| **True Proxy Mode** | Intercept and forward traffic seamlessly to OpenAI/Groq with Deep Packet Inspection |
| **Comparison Scans** | Run two agents side-by-side to compare their defenses against the same payload |
| **Custom Probes** | Build your own custom attack payloads in the database via API, augmenting the base 24 probes |
| **Vector RAG Agent** | RAG agent powered by `sentence-transformers` vector similarity, for testing context poisoning |
| **Webhook Alerts** | Automatically alert a Slack/Discord channel if an agent fails a security check during a scan |
| **Live Stream** | Watch probes execute and receive real-time verdicts as they happen |
| **DPI Inspector** | Regex + YAML policy engine catches adversarial prompts before they hit the LLM |
| **ML Classifier** | Fine-tuned MiniLM (F1 0.970) for intent detection and adversarial classification |
| **Mismatch Detection** | Surface gaps where regex missed an attack but ML caught it (or vice-versa) |
| **Audit Trails** | Generate Markdown + JSON reports with SHA-256 manifest for compliance |
| **Policy Editor** | Edit the YAML block/allow policy live from the browser |

---

## 🏗️ Architecture

```
Browser UI (Next.js)
       │
       ▼
FastAPI Backend (:8000)
   ├── Inspector (regex + YAML policy)     ← blocks adversarial prompts
   ├── ML Classifier (external API)        ← secondary detection layer
   ├── Agent Loader                        ← discovers agents in backend/agents/
   │      ├── default_agent.py  (built-in)
   │      ├── example_custom_agent.py
   │      └── your_agent.py  ← add yours here
   ├── Scanner                             ← orchestrates probes
   ├── Report Generator
   └── Prisma ORM → PostgreSQL
```

**Tech stack:**
- **Frontend**: Next.js 16 (App Router) + Vanilla CSS (glassmorphism dark theme)
- **Backend**: FastAPI (Python) with Server-Sent Events for live scan streaming
- **Database**: PostgreSQL via [Prisma Client Python](https://prisma-client-py.readthedocs.io/)
- **LLM**: Groq API (default: `llama-3.1-8b-instant`) — swap in any provider

---

## 📁 Folder Structure

```
RedGuard/
├── app/                        # Next.js frontend (App Router)
│   ├── page.tsx                # Dashboard
│   ├── scan/page.tsx           # Live scan + agent selector
│   ├── audit/page.tsx          # Audit log
│   ├── reports/page.tsx        # Generated reports
│   ├── policy/page.tsx         # Policy editor
│   ├── globals.css             # Design system (CSS variables, glass panels)
│   └── layout.tsx              # Root layout with sidebar
│
├── components/
│   ├── Sidebar.tsx             # Navigation sidebar
│   └── StatCard.tsx            # Dashboard stat card
│
├── backend/
│   ├── agents/                 # ⭐ Plug-in agent folder
│   │   ├── __init__.py
│   │   ├── default_agent.py          # 🛡️ Built-in LangGraph ReAct agent (Groq)
│   │   ├── gemini_flash_agent.py     # Google Gemini Flash with session memory (free API)
│   │   ├── ollama_local_agent.py     # 100% offline Ollama agent (no API key)
│   │   ├── rag_knowledge_agent.py    # RAG pipeline with TF-IDF doc retrieval
│   │   ├── code_auditor_agent.py     # Code security scanner (AST + secret detection)
│   │   └── example_custom_agent.py  # Template — copy this to add your own
│   │
│   ├── agent_loader.py         # Auto-discovers agents in agents/ folder
│   ├── app.py                  # FastAPI app + all API routes
│   ├── scanner.py              # Probe orchestration + SSE streaming
│   ├── inspector.py            # DPI regex engine
│   ├── policy.yaml             # Block/allow rules (editable from UI)
│   ├── probes.py               # 24 adversarial probe definitions (6 categories)
│   ├── report_generator.py     # Markdown + JSON report generation
│   ├── audit_report.py         # Audit log helpers
│   ├── dashboard.py            # Dashboard stats aggregation
│   ├── database.py             # Prisma client singleton
│   ├── schema.py               # Shared utility functions
│   ├── redteam_agent.py        # Red-team attacker agent
│   ├── target_agent.py         # CLI launcher (interactive terminal)
│   ├── requirements.txt
│   └── prisma/
│       └── schema.prisma       # Database schema (Sessions, Events, Reports)
│
├── public/                     # Static assets
├── .env.example                # Environment variable template
├── next.config.js
├── package.json
└── tsconfig.json
```

---

## 🚀 Quickstart (Docker - Recommended)

The easiest way to run RedGuard is using Docker. It automatically sets up PostgreSQL, the FastAPI backend, and the Next.js frontend.

### 1. Clone the repository
```bash
git clone https://github.com/ShivamYash742/RedGuard.git
cd RedGuard
```

### 2. Set environment variables
```bash
cp .env.example .env
```
Edit `.env` and add your API keys:
```env
GROQ_API_KEY="your-groq-api-key"
WEBHOOK_URL="optional-slack-discord-webhook"
```

### 3. Run with Docker Compose
```bash
docker-compose up
```
This will automatically:
- Spin up PostgreSQL
- Push the database schema
- Start the Next.js frontend at `http://localhost:3000`
- Start the FastAPI backend at `http://localhost:8000`

---

## 🛠️ Manual Setup (Without Docker)

If you prefer to run it manually without Docker:

### 1. Install dependencies
```bash
# Frontend
npm install

# Backend
cd backend && pip install -r requirements.txt && cd ..
```

### 2. Configure Database
Set your `DATABASE_URL` in `.env` to point to a running PostgreSQL instance, then push the schema:
```bash
cd backend && npx prisma db push && cd ..
```

### 3. Run the application
```bash
npm run dev:all
```
This starts Next.js on `:3000` and FastAPI on `:8000`.

---

## 🤖 Agent Catalogue

RedGuard ships with **6 agents** out of the box — each demonstrating a different architecture and attack surface.

| File | Name | Unique Abilities |
|------|------|-----------------|
| `default_agent.py` | **Default RedGuard Agent** 🛡️ | LangGraph ReAct, web search, file-read, calculator. The canonical production-agent architecture — prime target for tool-output injection & filesystem exfiltration |
| `gemini_flash_agent.py` | **Google Gemini Flash Agent** | Free Google AI Studio API, 1M token context window, persistent session memory (`remember`/`recall`). Prime target for needle-in-a-haystack payload hiding |
| `ollama_local_agent.py` | **Ollama Local Agent** | 100% offline, zero API keys, runs local Llama 3.2. Custom JSON tool dispatcher — smaller models are less instruction-tuned, more vulnerable to jailbreaks |
| `rag_knowledge_agent.py` | **RAG Knowledge-Base Agent** | TF-IDF retrieval over an in-memory corporate document store. The #1 real-world enterprise AI pattern — classic target for context-poisoning, indirect injection & data exfiltration |
| `code_auditor_agent.py` | **Code Security Auditor** | AST vulnerability scan, secret/credential detection, dependency typosquat checker, complexity metrics. Target for obfuscated payloads & authority-spoofing attacks |
| `example_custom_agent.py` | **Example Custom Agent** | Minimal stub template — copy this to bring your own |

### Adding Your Own Agent

1. Copy the template:
```bash
cp backend/agents/example_custom_agent.py backend/agents/my_agent.py
```

2. Fill in three things:
```python
# backend/agents/my_agent.py

AGENT_NAME = "My Company Agent"
AGENT_DESCRIPTION = "Our internal RAG pipeline backed by GPT-4o."

async def invoke(prompt: str) -> str:
    # YOUR AGENT LOGIC HERE
    # Call OpenAI, Anthropic, LangChain, Ollama, an internal API — anything.
    # Just return the agent's final text response as a string.
    response = await my_internal_api.call(prompt)
    return response.text
```

3. Restart the server — your agent appears in the UI selector instantly:
```bash
npm run dev:all
```

### CLI mode (optional)
```bash
cd backend
python3 target_agent.py                    # default agent
python3 target_agent.py gemini_flash_agent
python3 target_agent.py ollama_local_agent
python3 target_agent.py rag_knowledge_agent
python3 target_agent.py code_auditor_agent
python3 target_agent.py my_agent           # your custom agent
```

---

## ⚔️ Attack Categories (Franklin et al. 2025)

| # | Category | What it tests |
|---|---|---|
| 1 | **Content Injection** | Hidden instructions embedded in tool outputs |
| 2 | **Semantic Manipulation** | Biased framing, role impersonation, authority spoofing |
| 3 | **Cognitive State** | Poisoned context injection, false memory creation |
| 4 | **Behavioural Control** | Embedded jailbreaks, data exfiltration attempts |
| 5 | **Systemic** | Rate-based congestion probes |
| 6 | **Human-in-the-Loop** | Approval fatigue generation, misleading summaries |

---

## 🔌 API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Server + DB health check |
| `GET` | `/api/stats` | Aggregate scan statistics |
| `GET` | `/api/agents` | List all available agents |
| `POST` | `/api/proxy` | True reverse proxy (forward traffic to `x-target-url` after inspection) |
| `POST` | `/api/scan/start` | Start a scan (`{ agentId }` in body) |
| `POST` | `/api/scan/compare` | Run a concurrent scan against two agents |
| `POST` | `/api/scan/replay` | Test a single probe instantly |
| `GET` | `/api/scan/stream?sessionId=` | SSE stream of live probe results |
| `GET` | `/api/probes` | List custom probes |
| `POST/PUT/DEL`| `/api/probes` | CRUD for custom probes |
| `GET` | `/api/sessions` | List all scan sessions |
| `GET` | `/api/sessions/:id` | Session detail + events |
| `GET` | `/api/reports/:id` | Get generated report for a session |
| `GET` | `/api/policy` | Get current YAML policy |
| `PUT` | `/api/policy` | Update YAML policy |
| `GET` | `/api/events` | Query probe events (filterable) |

---

## 🗄️ Database Schema

```
Session        — one row per scan run
ProbeEvent     — one row per adversarial probe (linked to Session)
Report         — generated Markdown + JSON report (linked to Session)
PolicySnapshot — YAML policy captured at scan start (linked to Session)
CustomProbe    — user-defined adversarial payloads stored in the database
```

Managed via **Prisma** — run `npx prisma studio --schema backend/prisma/schema.prisma` to browse the database visually.

---

## 📄 License

MIT
