# 🛡️ RedGuard AI Security Dashboard — New UI Features & Architecture Showcase

Welcome to the newly built **RedGuard AI Security & Red-Teaming Dashboard**! This document provides a complete guide to all the newly added UI modules, design system elements, interactive charts, and benchmark runner features.

---

## 🎨 1. Design System & Theme Aesthetics

- **Cybersecurity Dark Mode Aesthetic**: Built with a sleek dark slate background (`#090D16`), crimson attack accents (`#EF4444`), emerald security status indicators (`#10B981`), electric indigo (`#6366F1`), and cyan metrics.
- **Glassmorphism & Micro-Animations**: Card surfaces feature backdrop blur (`backdrop-blur-md`), subtle borders, cyber glows, smooth hover translate effects, and custom scrollbars.
- **Typography & Font System**: Configured with `Inter` for crisp body copy and `JetBrains Mono` for technical prompt payloads, regex rules, and telemetry outputs.
- **Loading & Empty States**: Integrated animated shimmer skeletons ([components/ui/skeleton.tsx](file:///home/shivammishra/Pictures/RedGuard/components/ui/skeleton.tsx)), friendly empty state illustrations ([components/ui/empty-state.tsx](file:///home/shivammishra/Pictures/RedGuard/components/ui/empty-state.tsx)), and error boundaries ([components/ui/error-state.tsx](file:///home/shivammishra/Pictures/RedGuard/components/ui/error-state.tsx)).

---

## 🧭 2. Global Layout & Command Palette Search

- **Collapsible Sidebar Navigation** ([components/Sidebar.tsx](file:///home/shivammishra/Pictures/RedGuard/components/Sidebar.tsx)):
  - Icon-based menu matching all 10 feature routes.
  - Active path highlighting, category item counts, and collapsible drawer toggle (`ChevronLeft` / `ChevronRight`).
  - Deep Packet Inspection (DPI) live status badge.
- **Dynamic Header Bar** ([components/TopBar.tsx](file:///home/shivammishra/Pictures/RedGuard/components/TopBar.tsx)):
  - Context-aware page breadcrumbs and version tag.
  - Real-time FastAPI backend health status indicator (`FastAPI Online` / `Mock Data Active`).
  - Global Search trigger bar (`Cmd+K` shortcut indicator).
  - Quick action CTA button to launch a **New Benchmark**.
- **Global Command Palette Modal** ([components/GlobalSearch.tsx](file:///home/shivammishra/Pictures/RedGuard/components/GlobalSearch.tsx)):
  - Press <kbd>Cmd+K</kbd> or <kbd>Ctrl+K</kbd> anywhere in the application to open the instant search modal.
  - Search across **Probes**, **Attack Families**, **Scenarios**, **Benchmark Runs**, **Leaderboard Models**, and **Audit Reports** with instant keyboard navigation.

---

## 💻 3. Complete Page Modules & Features

### 📊 3.1 Dashboard Overview (`/`)
- **Stat Cards** ([components/StatCard.tsx](file:///home/shivammishra/Pictures/RedGuard/components/StatCard.tsx)): Displays **Total Benchmark Runs**, **Probes Executed**, **Security Block Rate (%)**, and **Attack Success Rate (ASR %)** with trend indicators and variant glows.
- **Attack Vector Matrix**: Interactive resilience vs ASR progress bars for all 8 threat categories.
- **Top Model Resilience Preview**: Quick leaderboard snapshot highlighting top-ranked LLM models.
- **Recent Benchmark Runs Table**: Live log table with run IDs, probe counts, blocked/compromised breakdown, status badges, and direct report links.

### 🛡️ 3.2 Attack Families Directory (`/attack-families` & `/attack-families/[familyId]`)
- **8 Attack Vector Cards**: Covers **Direct Prompt Injection**, **Indirect Content Injection**, **Data Exfiltration**, **Tool Abuse**, **Goal Diversion**, **Memory Poisoning**, **Unchecked Autonomy**, and **Planning Evasion**.
- **Search & Severity Filtering**: Filter families by `CRITICAL`, `HIGH`, `MEDIUM` severity or keyword search.
- **Family Detail Page (`/attack-families/[familyId]`)**: Shows adversarial methodology, raw sample attack payloads, defense/mitigation strategies, DPI regex rules, and associated probe listings.

### 🔬 3.3 Probes Directory (`/probes` & `/probes/[probeId]`)
- **Adversarial Payload Registry**: Browse and search 50+ registered attack probes.
- **Metadata Detail View (`/probes/[probeId]`)**: Raw attack prompt text, expected refusal indicators, `policy.yaml` regex pattern traps, target scenario context, and ML intent classifier categories (`ADVERSARIAL_ROLEPLAY`, `INDIRECT_PROMPT_INJECTION`, `DATA_EXFILTRATION`, `COMMAND_INJECTION`).

### 📦 3.4 Scenarios & Agent Environments (`/scenarios` & `/scenarios/[scenarioId]`)
- **Real-World Agent Tool Environments**: Multi-tool agent scenarios including **Automated Banking**, **Executive Email Assistant**, **GitHub DevOps Bot**, and **E-Commerce Concierge**.
- **Environment Detail View (`/scenarios/[scenarioId]`)**: Displays exposed tool declarations, mock environment state summaries, and sample adversarial prompt injects.

### ⚡ 3.5 Live Benchmark Execution Engine (`/benchmark`)
- **Target LLM Agent Picker**: Select from the exact 5 backend target agents (**Nemotron-3 Ultra 550B**, **Nemotron-3 Super 120B**, **DeepSeek V4 Flash**, **Meta Llama 3.3 70B**, and **Ollama Local / Offline**).
- **Single / Multi Attack Family Selector**:
  - Run **all 8 families** at once, OR select **only one specific family** (e.g. run only `Data Exfiltration` or only `Direct Prompt Injection`).
  - Supports URL query parameters (`/benchmark?family=exfiltration`) for 1-click single family testing.
- **Real-Time Live Telemetry Engine**:
  - Animated progress bar and probe ticker.
  - Live metric counters for **Total Executed**, **Resisted (Blocked)**, and **Compromised (ASR)**.
  - Real-time terminal log feed streaming DPI verdicts as probes execute.

### 📈 3.6 Results & Visualizations Suite (`/results` & `/results/[sessionId]`)
- **Radar Chart**: Displays multi-axis security resilience scores across 8 attack families.
- **Stacked Bar Chart**: Visual breakdown of Blocked vs Allowed (ASR) probes per category.
- **Line Chart**: Execution latency (ms) and risk score distribution across probes.
- **Category Risk Heatmap Grid**: Visual color-coded matrix highlighting category threat levels.
- **Audit Event Log Table**: Filterable audit log of every individual probe event with latency and verdicts.

### 🏆 3.7 Model Leaderboard & Comparator (`/comparison`)
- **Sortable & Filterable Rankings Table**: Sort LLMs by **Security Score**, **ASR (%)**, or **Average Latency (ms)**.
- **Head-to-Head Model Comparator**: Select Model A vs Model B side-by-side to visually compare resilience metrics, ASR, and latency.

### 📄 3.8 Security Audit Reports (`/reports`)
- **Executive Security Reports List**: View generated audit reports with risk levels (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`).
- **Interactive Markdown Preview Modal**: In-app rendered markdown report viewer.
- **Single-Click Downloads**: Download reports formatted as `.MD` or `.JSON`.

### 📜 3.9 Benchmark History Timeline (`/history`)
- **Chronological History Stream**: Interactive vertical timeline of all past evaluation sessions with dates, target agents, and block rate drift metrics.

### 🗄️ 3.10 Dataset Coverage & Custom Probe Builder (`/datasets`)
- **Dataset File Explorer**: Inspect built-in dataset schemas (`autonomy.json`, `content_injection.json`, `direct_injection.json`, `exfiltration.json`, `goal_diversion.json`, `memory_poisoning.json`, `planning.json`, `tool_security.json`).
- **Custom Probe Authoring Builder**: Form with schema validator to author and save custom attack prompts to the benchmark queue.

---

## ⚙️ 4. API Client & Hybrid Fallback Architecture

- **Data Service Layer** ([lib/data-service.ts](file:///home/shivammishra/Pictures/RedGuard/lib/data-service.ts)):
  - Automatically queries live backend endpoints (`/api/stats`, `/api/sessions`, `/api/sessions/{id}`, `/api/events`).
  - Seamlessly falls back to rich built-in mock datasets if the FastAPI server is offline or starting up, ensuring **100% uptime and smooth UI development**.

---

## 🛠️ 5. Verification & Build Confirmation

- **TypeScript Typecheck**:
  ```bash
  npm run typecheck
  # ✓ Passed cleanly with 0 errors
  ```
- **Next.js Production Build**:
  ```bash
  npm run build
  # ✓ Compiled successfully (16/16 static & dynamic pages)
  ```
