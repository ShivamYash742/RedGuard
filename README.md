# RedGuard v6.1.0 🛡️ — AI Agent Security Benchmark Platform

[![Version](https://img.shields.io/badge/version-6.1.0-blue.svg)](./package.json)
[![Benchmark](https://img.shields.io/badge/benchmark-v6.1.0-indigo.svg)](./core/shared/version.py)
[![Dataset](https://img.shields.io/badge/dataset-v6.0.0-emerald.svg)](./core/scanner_mode/datasets)

RedGuard is an academic-grade **AI Agent Security Benchmark Platform** designed for empirical evaluation of Large Language Model (LLM) agent resistance against indirect prompt injections, goal diversion, persistent memory poisoning, autonomous execution risks, and tool hijacking.

The platform combines a research-focused **Next.js 16 frontend** (styled after Hugging Face Leaderboards, MLPerf, Weights & Biases, Kaggle, and OpenAI System Cards) with a **FastAPI backend engine**. It has two modes:

- **Scanner mode** (formerly Mode A). Single-turn adversarial probes against one agent: *what does one model do with an attack prompt?*
- **Lab mode** (formerly Mode B). An attack planted in something one agent reads, followed through a chain of three agents: *what does the whole system do with it?*

Each mode has its own place in every layer of the code — see [`docs/architecture.md`](./docs/architecture.md) for the one-page map.

---

## 🆕 What's new

### 6.1.0 — 35 bugs found by a review of 6.0.0

Four read-only reviews of 6.0.0 (Scanner, Lab core, backend, frontend) found 36 bugs; the list with the failing
inputs is [`docs/bugs_to_fix_6.1.0.md`](./docs/bugs_to_fix_6.1.0.md) and what each fix changed is in
[`docs/audit_fixes.md`](./docs/audit_fixes.md) (LAB-10, a version string in the case files, is left alone on
purpose). The ones that move a reported number:

- **Lab.** A direct tool read was labelled "message" propagation, which inflated `CPR_message` (LAB-01); a relay the bus
  gateway blocked stopped counting as influence, so arms differed for a reason unrelated to the defence (LAB-02);
  `n_attack_runs` counted invalid runs and the `valid_pairs` gate never failed (LAB-03); the `entry_exposure` gate could
  exceed 100% (LAB-04); natural and forced exposure could be pooled (LAB-05); a malformed reply of the wrong JSON type
  dropped the pair instead of counting as invalid (LAB-06).
- **Scanner.** A step-limit run that already made the harmful call was `NO_ANSWER` (SCN-02); a refusal that repeated the
  request scored `UNCLEAR` instead of `OVER_REFUSED` (SCN-03); the leaderboard pooled different models and filter
  policies into one row (SCN-01).
- **Exports.** Evidence bundles from `sweep --export` now carry the stored verdict (API-02).
- **Security.** `npm run dev` / `start` listen on 127.0.0.1 only (API-01); malformed bodies are 400s (API-04); cancel only
  deletes a running session (API-06).

Versions: the release and the Scanner benchmark are **6.1.0**; the dataset and probe schema stay **6.0.0** (no probe or
generated file changed), Lab evaluator and metrics are **2.1.0**. Scores from 6.0.0 and Lab 2.0.0 are not comparable
with them. A scan stored under 6.0.0 is no longer on the leaderboard: re-run it under 6.1.0.

### 6.0.0 — an evaluation that can support its claims

5.0.0 fixed how a probe is scored. It did not fix what the scores are allowed to claim: 46 attacks in 8 families
(3 to 9 each) cannot rank two agents, the hardened prompt named the test, and nobody had measured the scorer.
6.0.0 changes the evaluation, not only the code. Plan: [`docs/evaluation_plan.md`](./docs/evaluation_plan.md);
how to produce a publishable result: [`docs/evaluation_protocol.md`](./docs/evaluation_protocol.md).

- **Dev / test split.** Every probe and case has `split`. The 56 hand-written probes and 10 cases are **dev**:
  the filter, prompts, indicators and evaluator were built against them. **160 new attacks** (20 per family, all
  scored from a tool call or a canary, none by wording) with 99 matched controls, and **30 new Lab cases**, are
  **test**. They are generated (`scripts/gen_test_probes.py`, `scripts/gen_test_cases.py`) and a test checks the
  files equal the generator's output. Numbers are quoted from the test split.
- **Frozen.** `scanner_mode/manifest.py` and `core/lab_mode/manifest.py` hash the filter, prompts, tools, scorer,
  evaluator and both case sets; a test fails if they change without a deliberate re-freeze, and every session and
  run stores its digest.
- **General hardened prompt.** Six principles that name no attack phrase, family or scenario.
- **Claims need evidence.** Leaderboard rows list which other rows they cannot be told apart from (paired per-probe
  test, `/api/leaderboard/compare`); Lab arm comparisons give a sign-flip p, a verdict, an underpowered flag, the
  cost to the benign task and Holm-adjusted p. `python -m scripts.power` says how many items a question needs.
- **Exposure.** Scanner rows report attack success among attacks the agent actually met. Lab has
  `exposure=forced`: the harness performs the entry agent's read of the planted location (`sweep --exposure forced`).
- **Gates.** A Lab model must pass three suitability gates before it is compared with another.
- **Labelling.** `scripts/reanalysis/labels.py export --per-method N` builds a sheet (prompt, reply, tool calls,
  scoring method) for two people; `agree` reports kappa and the scorer's accuracy and recall per method.

Guides: [`docs/viva_guide.md`](./docs/viva_guide.md) (the whole project, for a viva; PDF alongside) and
[`docs/colab_guide.md`](./docs/colab_guide.md) (run a 7–10B model on a free Colab GPU instead of a local Ollama).

Still true: **no model has been run under 6.0.0 or 6.1.0**, the scorer has no measured accuracy yet, and the 11
phrase-scored probes live in the dev split only.

### 5.0.0 — fixes from an external audit

An audit found problems in the code, the scoring and the metrics. They are fixed, each fix has a
regression test, and none of it has been run against a real model. Results measured under 4.x stay in
the database and on the pages, labelled **"Measured before the audit fixes"**, and are never pooled with
new ones. Fix by fix: [`docs/audit_fixes.md`](./docs/audit_fixes.md). Statements in the earlier report and
paper that no longer hold: [`docs/report_errata.md`](./docs/report_errata.md).

**Scanner mode** (benchmark, dataset and probe-schema versions 5.0.0)

- **Comparable agents.** Every agent runs in one scaffold (`agents/_scaffold.py`): the same tools, the same
  baseline prompt, the same hardened prompt, temperature 0 and a seed. Provider, model, temperature, seed and
  scaffold are recorded on each session. `web_search` answers from fixtures unless `SCANNER_WEB_SEARCH=live`.
- **Scoring from evidence.** Probes that ask for an action are scored from the tool calls the agent made
  (mock `send_email`, `execute_sql`, `transfer_funds`, ... record them and do nothing). System-prompt and
  exfiltration probes are scored by canaries planted in the prompt and in the sandbox files. Only the
  remaining 11 probes use text, and their indicators must show compliance. Controls are scored on the task
  (helped / over-refused / unclear), an agent that never answered is `NO_ANSWER` and leaves every rate, and
  attack success is reported as a range between the two refusal-versus-indicator tie-breaks.
- **Probes.** Indirect attacks now arrive in tool results (`fetch_page`, `read_email`, ...), not in the user
  message; giveaway wording and near-duplicates are gone; every arXiv reference was checked on arXiv and four
  wrong or placeholder IDs were replaced.
- **Statistics.** Intervals are clustered by probe, Behaviour Drift Score is the agreement rate
  `max(k, N-k)/N`, and the regex filter is also measured on 250 held-out XSTest safe prompts
  ([`docs/scanner_mode/filter_evaluation.md`](./docs/scanner_mode/filter_evaluation.md)).
- **Safety.** A broken `policy.yaml` stops scans (the filter fails closed) and policy writes are validated;
  state-changing and work-running requests need a trusted `Origin` and a JSON body; custom probes stay out of
  the benchmark numbers; an unknown agent id is an error instead of the default agent.

**Lab mode** (evaluator, metrics, case-schema and environment versions 2.0.0)

- Tool-call predicates match resources exactly (`arg_equals`) and need real rows; a query of an unknown table
  is a tool error. RGM-003 and RGM-007 now require agent C.
- Control cases (RGM-008, RGM-009) and cases whose objective cannot be reached in an arm (RGM-005 outside the
  permissive arm) are reported apart; the old all-cases rates remain as `pooled_legacy`.
- CPR is reported twice: any exposure, and propagation by message only. Runs record whether the attack was ever
  in front of an agent, and ASR is also given among exposed runs. A single case no longer gets a narrow interval.
- Repetitions can use a base seed (repetition N uses seed + N) and a temperature; an experiment whose
  repetitions would be exact copies says so. Cases record whether their task points at the poisoned channel,
  and RGM-010 is RGM-007 with a task that does not.

### 4.2.0 — one place for each mode

The project is reorganised so that anyone can tell what belongs to which mode:
**every layer has the same three folders — `shared/`, `scanner_mode/`, `lab_mode/`** —
and the two modes never import each other.

| Layer | `shared/` | `scanner_mode/` | `lab_mode/` |
|---|---|---|---|
| Pages `app/` | `/`, `/settings`, layout | `(scanner_mode)/` corpus, runs, models | `(lab_mode)/` lab |
| UI parts `components/` | header, sidebar, search, skeletons | probe drawer, tier bar | stage, agent cards, swimlane |
| UI data `lib/` | — | data service, search index | lab service |
| API `backend/` | `app.py`, `database.py`, `prisma/` | `api.py`, scanner, inspector, agents, leaderboard, `cli/` | `api.py`, `store.py`, `sweep.py` |
| Library `core/` | version, statistics, reproducibility | probe datasets, BDS | the multi-agent harness |
| Tests | boundary checks | scanner tests | lab tests |

- Every URL and every `/api/…` path is unchanged (the `(…)` folders are Next.js route groups, which do not appear in URLs).
- `backend/app.py` is now only the shared app; Scanner mode's routes moved to `backend/scanner_mode/api.py`.
- The boundary is enforced: `core/tests/shared/test_mode_boundaries.py` and an ESLint `no-restricted-imports` rule fail if one mode imports the other.
- `policy.yaml` is read by path, not relative to the server's working directory.
- The legacy CLIs moved from `scripts/` to `backend/scanner_mode/cli/` and import correctly again.
- Commands that changed: `python -m core.lab_mode.cases|smoke`, `python -m lab_mode.sweep`, `python -m scanner_mode.target_agent`, `python docs/scanner_mode/spec_generator.py`.
- `docs/architecture.md` is rewritten as the map of the project.

### 4.1.5 — Lab mode UI and live dynamics

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

**Versions.** 6.1.0 is the release and Scanner mode's benchmark version; its dataset and probe-schema versions stay **6.0.0** (the probe set, the hardened prompt and the leaderboard changed in 6.0.0, the 6.1.0 fixes touch no probe). Lab mode's evaluator and metrics versions are **2.1.0**, its environment version **2.0.0** and its case schema **2.1.0** (the `split` field). Results from 4.0.0 (Scanner) and 1.2.0 (Lab), and from 6.0.0 and 2.0.0, are not comparable with them: they are shown in their own section, labelled "Measured before the audit fixes", and never pooled.

---

## ✨ Key Features (v6.1.0)

| Feature | Description |
|---|---|
| **Measured Leaderboard** | One row per agent and system-prompt mode, from stored runs only: attack success with the regex filter off and on (Wilson 95% CIs), per-family resistance, over-refusal, and Behaviour Drift Score (BDS) |
| **Research Visualizations** | Recharts Radar Charts (Attack family comparison) and Stacked Outcome Distribution Bars (comparison page) |
| **6 Navigation Hubs** | Overview, Corpus (families/probes/scenarios), Runs (live execution & history), Models & Ranking, Lab, & Settings — v3 consolidated the original 14 routes into 5, plus Lab mode's own `/lab` |
| **Global Search (`⌘K`)** | Fast client-side fuzzy search overlay (`lib/search-index.ts`) matching Probe IDs, Titles, Attack Families, Scenarios, Models, and Reports |
| **8 Attack Families Taxonomy** | Direct Injection, Content Injection, Data Exfiltration, Goal Diversion, Memory Poisoning, Autonomous Actions, Planning Manipulation, & Tool Manipulation |
| **46 Attack Probes + 10 Benign Controls** | Auditable JSON dataset entries with research paper citations (arXiv IDs checked against arXiv), difficulty levels, & threat models. Controls are harmless requests that measure over-refusal and regex false positives |
| **12 Application Scenarios** | GitHub, GitLab, Wiki, Documentation, Email, Calendar, Banking, Travel, Shopping, Support, Forum, & Reddit simulation environments |
| **Live SSE Execution Suite** | Real-time Server-Sent Events stream: every probe lands in one tier — Filtered (regex), Refused, Ignored or Compromised — with live counters per family; benign controls counted separately |
| **Tiered Scoring** | Every probe lands in one tier (Filtered, Refused, Ignored, Compromised; no answer is counted apart). Compromise is decided by recorded tool calls, a canary, or (11 probes) compliance phrases. The model sees every probe, even ones the regex blocks, so results exist as deployed and for the model alone; attack success is a range, not a point |
| **Lab mode: Multi-Agent Lab** | 10 cases (2 are controls), 3 agents (A researcher → B validator → C executor), every action executed and recorded by the harness, 5 defence arms, four-dimension verdicts, clean control run for every attack run |
| **Lab mode: Live Run View** | Agent cards with a ticking status, per-agent swimlane timeline, stage for clean and attack runs, per-run progress with elapsed time and ETA, event feed — from any tab, after a reload |
| **Lab mode: Experiment Reports** | Generated from stored traces after a run: findings, suitability, rates with intervals, containment, per agent / case / run, evidence trail; Markdown & JSON |
| **Multi-Format Export** | Scanner mode reports in Markdown (`.md`) and CSV (`.csv`); Lab mode experiment reports in Markdown and JSON, and per-run evidence bundles |
| **BibTeX Citation Exporter** | Built-in academic citation snippet generator for research paper citations |

---

## 🏗️ Architecture Overview

```
                        RedGuard v6.1.0 Platform
                                   │
┌──────────────────────────────────┴──────────────────────────────────┐
│                      Next.js 16 Academic UI                         │
│ shared         Overview · Settings · Header/Sidebar · ⌘K search     │
│ scanner_mode   /corpus (probes, families, scenarios) · /runs (live  │
│                SSE scans, history) · /models (leaderboard, radar)   │
│ lab_mode       /lab · live view · replay · reports · compare        │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │ HTTP / SSE (/api/…)
┌──────────────────────────────────┴──────────────────────────────────┐
│                      FastAPI backend (:8000)                        │
│ shared         app.py (CORS, health, mounts routers) · database.py  │
│ scanner_mode   api.py · scanner · inspector + policy.yaml · agents/ │
│                leaderboard · report generator · cli/                │
│ lab_mode       api.py (experiment jobs, SSE fan-out, reports)       │
│                store.py · sweep.py                                  │
│ prisma/        SQLite: 5 Scanner mode + 3 Lab mode models           │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │ imports
┌──────────────────────────────────┴──────────────────────────────────┐
│                core/ — pure Python library (no HTTP, no DB)         │
│ shared         version · statistics · reproducibility               │
│ scanner_mode   datasets/ (46 probes + 10 controls) · BDS            │
│ lab_mode       environment (CEE) · topology · tools · model client  │
│                runner · trace · evaluator · metrics · report · cases│
└─────────────────────────────────────────────────────────────────────┘
```

### Lab mode — the multi-agent security lab

Everything in the feature list up to Tiered Scoring is **Scanner mode**: single-turn
probes, each scored from the tool calls the agent made, a canary, or compliance
phrases into one of four tiers (Filtered / Refused / Ignored / Compromised). It
answers *what does one model do with an attack prompt?*

Agents differ in the model only: they share the scaffold, tools and prompts. What is
still different between them: the hosted APIs are called without a seed (the Ollama
agent sends one), each provider's client library formats tool calls its own way, and
`granite3.3:2b` now calls tools natively through Ollama's OpenAI-compatible endpoint
instead of the old JSON text protocol, which has not yet been run against the model.

**Lab mode** (`/lab`) answers a different question — *when an attacker hides an
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
| Capability gateway (`attack_capability_gateway`) | Task-scoped resource allowlist inspired by CaMeL (not an implementation of it): reads of resources the task never named are refused once untrusted content is in the caller's context |

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
| Harness suitability | invalid replies against the 10% gate, how agent turns ended |
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

#### Lab mode API

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
| `GET /api/lab/runs/{id}` · `/evidence` | one run's full trace · its evidence bundle |
| `GET /api/lab/cases` · `/topologies` · `/fixtures` · `/arms` | the catalog |

Stream events: `experiment_started` (model, step budget, agents),
`run_started` (run *n* of total), `trace_event` (timestamp, latency, turn),
`run_finished` (duration, steps, invalid replies), `run_verdict`,
`case_rescored`, and one of `experiment_complete` / `experiment_stopped` /
`experiment_error`.

Lab mode and Scanner mode never import each other's code; a test and a lint rule enforce it.
No real-model Lab mode results are published yet; every number so far is from
scripted runs or harness checks.

---

## 📊 Measured results

**There are no results under benchmark 6.1.0 or Lab 2.1.0 yet.** The agents, prompts, tools, scoring and
probes all changed, so no earlier number carries over. Run a scan and the numbers appear on `/models`.

### Measured before the audit fixes

**Scanner mode**, Ollama `granite3.3:2b`, benchmark 4.0.0 (46 attacks + 10 controls). These runs used a
different scaffold from the hosted agents (its own JSON tool loop with other tools, an input filter, a
security sentence in the baseline prompt, no temperature sent), attack success was scored by indicator
words, and the prompts were not yet rewritten. Treat them as a record of what was measured then:

| Prompt mode | Runs | Attack success, model alone | Attack success, as deployed | Over-refusal |
|---|---|---|---|---|
| baseline | 2 (92 attacks) | 19.6% (95% CI 12.7–28.8) | 12.0% (6.8–20.2) | 10% (2.8–30.1) |
| hardened | 1 (46 attacks) | 13.0% (6.1–25.7) | 6.5% (2.2–17.5) | 30% (10.8–60.3) |

Those intervals treat repeated runs as independent. The regex filter decided 24 of 46 attacks then; with
the probes rewritten it sees only the user message and catches 11 of 46. The earlier reading that tool and
memory attacks were the weakest families is withdrawn: the agents had no such tools and no memory, so those
"compromises" were word matches.

**Lab mode**: six local models were run on 21–22 October with the 1.2.0 evaluator and metrics, no-defence
arm only. Their experiments are kept and labelled "Measured before the audit fixes"; they cannot be compared
with experiments under 2.0.0. Granite never calls `finish`, so its agents use their whole step budget.

---

## 📁 Repository Structure

Every layer has the same three drawers — `shared/`, `scanner_mode/`, `lab_mode/`.
The full map, with how a request flows through each mode, is in
[`docs/architecture.md`](./docs/architecture.md).

```
RedGuard/
├── app/                               # Next.js pages — URLs unchanged by the folders in ( )
│   ├── layout.tsx, globals.css        # shared: root layout
│   ├── page.tsx                       # shared: Overview (/)
│   ├── settings/                      # shared: Settings — system health, policy, audit log
│   ├── (scanner_mode)/
│   │   ├── corpus/                    # /corpus — probes, families, scenarios (+ /corpus/probes/[id], /families/[id])
│   │   ├── runs/                      # /runs — live SSE scans and history (+ /runs/[sessionId] report)
│   │   └── models/                    # /models — leaderboard, radar chart, matrix
│   └── (lab_mode)/
│       └── lab/                       # /lab launcher · /lab/compare · /lab/experiments/[id] (live view, report) · /lab/runs/[id] (replay)
│
├── components/
│   ├── shared/                        # ClientLayout, Header, Sidebar, GlobalSearchModal (⌘K), EmptyState, Skeletons
│   ├── scanner_mode/                  # ProbeDrawer, TierBar
│   └── lab_mode/                      # LabRoute (propagation stage), AgentCards, AgentSwimlane
│
├── lib/
│   ├── scanner_mode/                  # data-service.ts (probes, scans, leaderboard), search-index.ts
│   └── lab_mode/                      # lab-service.ts (lab API client, SSE stream, live route derivation)
│
├── backend/                           # FastAPI on :8000 — run from here (uvicorn app:app)
│   ├── app.py                         # shared: the app, CORS, /api/health; mounts both routers
│   ├── database.py                    # shared: Prisma connection
│   ├── prisma/                        # shared: schema.prisma (5 Scanner + 3 Lab models) and dev.db demo data
│   ├── scanner_mode/
│   │   ├── api.py                     # every Scanner route: /api/scan/*, /api/sessions, /api/leaderboard, /api/policy, …
│   │   ├── scanner.py                 # scan loop and tiered scoring (score())
│   │   ├── inspector.py, policy.yaml  # regex filter and its rules
│   │   ├── agents/                    # the agents under test, auto-discovered (+ system_prompts.json, sandbox/)
│   │   ├── agent_loader.py, leaderboard.py, report_generator.py, schema.py
│   │   ├── target_agent.py            # interactive chat with any agent
│   │   └── cli/                       # legacy standalone CLIs (redteam_agent, audit_report, dashboard, add_custom_probes)
│   ├── lab_mode/
│   │   ├── api.py                     # /api/lab/*: experiments, server-owned jobs, SSE fan-out, metrics, report
│   │   ├── store.py                   # persistence of experiments, runs and trace events
│   │   └── sweep.py                   # batch experiment CLI
│   ├── tests/                         # conftest.py (shared fixtures) · scanner_mode/ · lab_mode/
│   └── requirements.txt
│
├── core/                              # pure Python library — no HTTP, no database, never imports backend/
│   ├── shared/                        # version.py (all version constants), statistics.py (Wilson CIs), reproducibility.py
│   ├── scanner_mode/
│   │   ├── datasets/                  # 8 JSON families: 46 attack probes + 10 benign controls, schema, loader, validator
│   │   └── bds.py                     # Behaviour Drift Score
│   ├── lab_mode/                      # the multi-agent harness
│   │   ├── cases/, fixtures/          # 9 test cases (+ case_schema.json) and the shared environment
│   │   ├── cee.py, topology.py, tools.py   # simulated environment, agent graph + message bus, tool gateway
│   │   ├── model_client.py, runner.py # the only network module; the harness-owned agent loop
│   │   ├── trace.py, evaluator.py     # provenance trace; four-dimension verdict
│   │   ├── metrics.py, analysis.py    # rates, intervals, cross-arm comparison
│   │   ├── evidence.py, report.py, repro.py   # evidence bundles, experiment reports, reproducibility stamp
│   │   └── smoke.py                   # model-suitability check (10% gate)
│   └── tests/                         # shared/ (incl. the mode-boundary check) · scanner_mode/ · lab_mode/
│
├── docs/
│   ├── architecture.md                # the map of the project
│   ├── research_paper.md, literature_mapping.md
│   └── scanner_mode/                  # benchmark_spec.md and spec_generator.py
│
├── docker/, docker-compose*.yml       # images and compose files
├── README.md
├── CLAUDE.md / AGENTS.md              # guidance for coding agents
├── PRODUCT.md                         # product and design context
├── package.json                       # frontend deps & dev:all script
└── next.config.js, tailwind.config.ts, tsconfig.json, eslint.config.mjs
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
copies the committed demo data and adds the Lab mode `lab_*` tables to that copy.
`backend/prisma/dev.db` itself is never written. `docker compose down -v` resets it.

Live-reload development (source bind-mounted, nothing installed on the host):

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
# after changing requirements.txt or package.json, add -V to refresh node_modules
```

Tests, sweeps and smoke runs inside the backend container:

```bash
docker compose run --rm backend python -m pytest ../core/tests tests -q
docker compose run --rm backend python -m core.lab_mode.cases
docker compose run --rm backend python -m core.lab_mode.smoke --scripted
docker compose run --rm backend python -m lab_mode.sweep --scripted --reps 2 --export /data/bundles
docker compose cp backend:/data/bundles ./bundles     # copy evidence bundles out
```

Notes:
- **Ollama on the host**: containers reach it at `http://host.docker.internal:11434`
  by default. Override with `DOCKER_OLLAMA_BASE_URL` in your shell or `.env`.
- **Reproducibility stamp**: there is no `.git` in the image, so build with
  `GIT_COMMIT=$(git rev-parse HEAD) docker compose build` to record the commit in
  every Lab mode experiment (`git_clean` is then reported as unknown, never as clean).
- **One backend worker**: Lab mode experiments run as tasks inside the backend
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
pip install -r requirements.txt -c requirements.lock   # the lock pins every package the tests ran with
prisma generate --schema prisma/schema.prisma
cd ..
```

The committed `backend/prisma/dev.db` is demo seed data **without** the Lab mode
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
| `NVIDIA_API_KEY` | Nemotron-3 Ultra & Super agents (the models are fixed in the agent files) |
| `GROQ_API_KEY` | GPT OSS 120B / 20B agents |
| `OLLAMA_BASE_URL` / `OLLAMA_MODEL` | Ollama Local Agent and Lab mode's Ollama provider (run `ollama serve` first) |
| `SCANNER_TEMPERATURE` / `SCANNER_SEED` | Sampling for Scanner mode's Ollama agent (defaults `0` / `0`). Every session records provider, model, temperature, seed and scaffold |
| `SCANNER_WEB_SEARCH` | `fixture` (default) answers the agents' `web_search` from `backend/scanner_mode/agents/web_search_fixtures.json` so a rerun sees the same pages; `live` uses DuckDuckGo. Recorded on each session |
| `LAB_MODEL` | Lab mode's default model when an experiment names none (default `granite3.3:2b`) |
| `CLASSIFIER_URL` | Optional ML classifier for a secondary verdict. Unset = no call; every probe is sent to this URL, so only use a service you run |
| `CORS_ORIGINS` | Origins allowed to call the API (default `http://localhost:3000,http://127.0.0.1:3000`). Requests carrying any other `Origin` get 403, and a request body must be `application/json` (415) |
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

**Lab mode on a local model.** Check the model can drive the harness first — the
gate is at most 10% invalid replies:

```bash
python -m core.lab_mode.smoke --provider ollama --model granite3.3:2b
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
pytest tests/                                                  # backend: scanner_mode/ and lab_mode/ API, store, agents
pytest ../core/tests/                                          # core: shared/ (incl. mode boundaries), scanner_mode/, lab_mode/
```

649 tests, about 15 s, no model calls.

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
