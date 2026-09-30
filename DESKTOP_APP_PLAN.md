# RedGuard Desktop App — Implementation Plan

> **Goal:** a user on **Windows** or **Linux** downloads one file, double-clicks it, and
> RedGuard opens in its own window. No Python, Node, Docker or terminal needed.
>
> **Deliverables:** a Windows installer (`RedGuard-Setup-<version>.exe`), a Linux
> AppImage (`RedGuard-<version>-x86_64.AppImage`) and a Fedora/RHEL package
> (`redguard-<version>.x86_64.rpm`), built automatically by GitHub Actions and attached
> to a GitHub Release whenever a `v*` tag is pushed.
>
> This document is written so it can be executed step by step by a person or an AI
> agent with no other context. Every phase ends with a **"Done when"** checklist; don't
> start the next phase until it passes.

---

## Table of contents

1. [Decisions already made](#1-decisions-already-made)
2. [How the finished app works](#2-how-the-finished-app-works)
3. [Why this design](#3-why-this-design-and-what-it-rules-out)
4. [Repository facts you need](#4-repository-facts-you-need-before-starting)
5. [Rules you must not break](#5-rules-you-must-not-break)
6. [Final file layout](#6-final-file-layout)
7. [Phase 0: Spike (prove the two risky parts)](#phase-0--spike-prove-the-two-risky-parts-first)
8. [Phase 1: Static export of the UI](#phase-1--static-export-of-the-ui)
9. [Phase 2: Backend desktop entry point](#phase-2--backend-desktop-entry-point)
10. [Phase 3: Database bootstrap](#phase-3--database-bootstrap)
11. [Phase 4: The launcher](#phase-4--the-launcher)
12. [Phase 5: Build script + PyInstaller](#phase-5--build-script--pyinstaller)
13. [Phase 6: Windows installer](#phase-6--windows-installer-inno-setup)
14. [Phase 7: Linux AppImage + RPM](#phase-7--linux-appimage--rpm)
15. [Phase 8: GitHub Actions](#phase-8--github-actions)
16. [Phase 9: Settings page + docs](#phase-9--settings-page-api-keys--docs)
17. [Testing matrix](#testing-matrix)
18. [Risks and fallbacks](#risks-and-fallbacks)
19. [Release checklist](#release-checklist)
20. [Troubleshooting guide](#troubleshooting-guide)
21. [Effort estimate](#effort-estimate)
22. [Out of scope / later](#out-of-scope--later)

---

## 1. Decisions already made

| Question | Decision |
|---|---|
| Architecture | **One process.** The Next.js UI is exported as static files and served by the FastAPI backend itself. The backend is frozen with **PyInstaller** and shown in a native window with **pywebview**. |
| Window technology | Windows: **Edge WebView2** (built into Windows 10/11). Linux: **Qt WebEngine** (via PySide6), bundled inside the app. If no webview can start, the app opens the user's **default browser** instead, so it always works. |
| Installer formats | Windows `.exe` installer (Inno Setup), Linux **AppImage**, Linux **RPM** for Fedora. |
| Where it's built | **GitHub Actions**, on real Windows and Linux runners, because PyInstaller cannot cross-compile. |
| Existing web + Docker setups | **Unchanged.** `npm run dev:all`, `npm run build` and `docker compose up` keep working exactly as before. The desktop build is an extra mode switched on by an environment variable. |

---

## 2. How the finished app works

```
User double-clicks RedGuard
        │
        ▼
┌─────────────────────────────── RedGuard (one process) ───────────────────────────────┐
│ desktop/launcher.py  (frozen by PyInstaller)                                         │
│                                                                                      │
│  1. Single-instance check ── already running? → focus/open it, exit                  │
│  2. Resolve folders (platformdirs):                                                  │
│       data   : Windows %LOCALAPPDATA%\RedGuard   Linux ~/.local/share/redguard       │
│       config : Windows %APPDATA%\RedGuard        Linux ~/.config/redguard            │
│       logs   : <data>/logs/redguard.log                                              │
│  3. First run: copy bundled seed DB → <data>/redguard.db,                            │
│               write <config>/.env from the bundled template                          │
│     Every run: apply bundled schema.sql (CREATE TABLE/INDEX IF NOT EXISTS)           │
│  4. Set env: DATABASE_URL, PRISMA_QUERY_ENGINE_BINARY, REDGUARD_GIT_COMMIT,          │
│              REDGUARD_DESKTOP=1, REDGUARD_STATIC_DIR; load <config>/.env             │
│  5. Pick a free port on 127.0.0.1, start uvicorn(backend.desktop_app:app) in a thread│
│  6. Poll http://127.0.0.1:<port>/api/health until OK (timeout → error dialog)        │
│  7. Open a pywebview window on http://127.0.0.1:<port>/                              │
│       └─ fails? → webbrowser.open(url) and keep serving until Ctrl+C / tray quit     │
│  8. Window closed → stop uvicorn → exit 0                                            │
│                                                                                      │
│ backend/desktop_app.py                                                               │
│   = backend/app.py's FastAPI app (all /api routes, untouched)                        │
│   + static files from the Next.js export  (/, /corpus/, /lab/, …)                    │
│   + fallback for pages whose URL holds a runtime ID (/lab/runs/<id>/ …)              │
│   + old-URL redirects (the ones next.config.js used to do)                           │
│   + /api/desktop/info and /api/desktop/open-config                                   │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

The browser page and the API share one origin (`http://127.0.0.1:<port>`), so the
frontend's existing relative calls (`fetch('/api/...')`, `new EventSource('/api/...')`)
work with no changes and no proxy.

---

## 3. Why this design (and what it rules out)

- **No Node.js at runtime.** Every page in `app/` is a client component (`"use client"`)
  and none reads files or env vars on the server. The probe datasets are imported at build
  time (`lib/data-service.ts` imports `core/datasets/*.json`). So the UI can be plain
  HTML/JS/CSS, served by FastAPI.
- **No fixed port.** The current web setup relies on Next.js rewrites, which are frozen at
  build time with a hard-coded backend URL. Serving UI and API from one server removes
  that, so the launcher can choose any free port, and two apps using port 8000 can't
  collide.
- **Smallest download.** Roughly 150–250 MB on Windows, 250–350 MB on Linux (Qt
  WebEngine). An Electron build would add ~100 MB plus a separate Node server.
- **What it costs:** three pages whose URL contains a runtime ID (a run, an experiment, a
  session) need a small change to read the ID from the URL. The old-URL redirects move
  from `next.config.js` into FastAPI for the desktop build. Both are covered below.

Rejected alternatives, for the record:
- **Electron + Next server + backend:** three processes, a baked-in port, larger. Kept
  as the fallback if Phase 0 fails badly.
- **Docker launcher:** requires Docker Desktop on every machine, so it isn't really a
  standalone app.

---

## 4. Repository facts you need before starting

These were checked against `main` at commit `3a3f986` (after PR #2). Re-check them if
`main` has moved a lot.

**Frontend**
- Next.js 16, React 19. Read `node_modules/next/dist/docs/` before writing Next code;
  `AGENTS.md` says this version differs from older training data.
- 12 pages, all client components:
  ```
  app/page.tsx                                  /
  app/corpus/page.tsx                           /corpus
  app/corpus/families/[familyId]/page.tsx       /corpus/families/<id>   ← ID from datasets
  app/corpus/probes/[probeId]/page.tsx          /corpus/probes/<id>     ← ID from datasets
  app/runs/page.tsx                             /runs
  app/runs/[sessionId]/page.tsx                 /runs/<id>              ← runtime ID
  app/models/page.tsx                           /models
  app/settings/page.tsx                         /settings
  app/lab/page.tsx                              /lab
  app/lab/compare/page.tsx                      /lab/compare
  app/lab/experiments/[experimentId]/page.tsx   /lab/experiments/<id>   ← runtime ID
  app/lab/runs/[runId]/page.tsx                 /lab/runs/<id>          ← runtime ID
  ```
- Dynamic pages read their ID like this today:
  ```tsx
  export default function LabRunPage({ params }: { params: Promise<{ runId: string }> }) {
    const { runId } = use(params)
  ```
- `app/layout.tsx` uses `next/font/google` (IBM Plex Sans/Mono). Fonts are downloaded at
  **build** time and self-hosted, so they work offline. No `next/image` anywhere.
- `next.config.js` already switches `output` by env var (`NEXT_OUTPUT=standalone` for
  Docker) and has `rewrites()` (proxy `/api/*`) plus a list of `redirects()` for old
  URLs. Both are incompatible with static export and must be skipped in export mode.
- Only icon asset: `public/shield.svg`.

**Backend**
- `backend/app.py` builds the FastAPI `app`, includes the Mode B router
  (`backend/lab_api.py`), and puts `..` on `sys.path` so `core` imports work.
- Database: SQLite through **prisma-client-py** (`backend/prisma/schema.prisma`, models
  Session, ProbeEvent, Report, PolicySnapshot, CustomProbe, Experiment, LabRun,
  TraceEvent). URL comes from `DATABASE_URL`.
- The prisma **query engine** is a native binary. The generated client needs it at
  runtime; it does **not** need Node at runtime. Node is only needed for the Prisma CLI
  (`generate`, `db push`, `migrate diff`), which we run at **build** time only.
- `backend/prisma/dev.db` is committed demo data **without** the Mode B `lab_*` tables.
  It must never be written to (CLAUDE.md).
- `backend/requirements.txt` has no torch/sentence-transformers any more (removed in PR #1).
- The Mode B reproducibility stamp (`core/lab/repro.py`) falls back to the env var
  `REDGUARD_GIT_COMMIT` when there is no `.git`. The desktop build sets it.
- `backend/policy.yaml` is read by the inspector at runtime and must be bundled.

**Tests and tooling that exist**
- `pytest ../core/tests tests` from `backend/` (≈541+ tests, no LLM needed).
- `backend/tests/conftest.py` → `migrated_db_template` fixture: copies `dev.db` and runs
  `prisma db push` on the copy. Reuse this pattern for the seed DB.
- Docker files in `docker/` show a working Prisma setup (pinned Node 22 copied from
  `node:22-slim`, because Prisma's Python CLI otherwise downloads an unpinned Node that
  needs `libatomic`). Reuse that lesson in CI.

---

## 5. Rules you must not break

1. **Mode A is frozen** (CLAUDE.md): don't modify `scanner.py`, `inspector.py`,
   `agent_loader.py`, `backend/agents/*`, `core/datasets/*`, `core/probes/*`,
   `core/scenarios/*`, the original Prisma models, or existing endpoints. The desktop
   work adds new files. `backend/app.py` is **not edited**; `backend/desktop_app.py`
   wraps it.
2. **Never write `backend/prisma/dev.db`.** The build copies it before running
   `prisma db push`.
3. **`core/` never imports `backend/`.** Desktop code lives in `desktop/` and
   `backend/desktop_app.py`.
4. **Web and Docker behaviour must not change.** Every Next.js config change is gated on
   `NEXT_OUTPUT === 'export'`. The route-ID change (Phase 1) must also work in normal web
   mode.
5. **No new frontend comments** beyond the existing style (CLAUDE.md).
6. Keep the backend bound to **127.0.0.1 only** in the desktop app, never `0.0.0.0`. It
   has no authentication.

---

## 6. Final file layout

New or changed files when everything is done:

```
DESKTOP_APP_PLAN.md                      ← this file
next.config.js                           ← CHANGED: export mode
lib/route-id.ts                          ← NEW: read a runtime ID from the URL
app/corpus/families/[familyId]/page.tsx  ← CHANGED: server wrapper + generateStaticParams
app/corpus/families/[familyId]/FamilyDetail.tsx   ← NEW: the old client component, moved
app/corpus/probes/[probeId]/page.tsx     ← CHANGED (same pattern)
app/corpus/probes/[probeId]/ProbeDetail.tsx       ← NEW
app/runs/[sessionId]/page.tsx            ← CHANGED (same pattern, placeholder "_")
app/runs/[sessionId]/SessionDetail.tsx   ← NEW
app/lab/experiments/[experimentId]/page.tsx       ← CHANGED
app/lab/experiments/[experimentId]/ExperimentDetail.tsx ← NEW
app/lab/runs/[runId]/page.tsx            ← CHANGED
app/lab/runs/[runId]/RunDetail.tsx       ← NEW
app/settings/page.tsx                    ← CHANGED: "API keys file" row (desktop only)

backend/desktop_app.py                   ← NEW: app.py + static UI + fallbacks + redirects
backend/tests/test_desktop_app.py        ← NEW

desktop/
  __init__.py
  launcher.py                            ← NEW: entry point of the frozen app
  paths.py                               ← NEW: data/config/log dirs, bundle dir
  db_bootstrap.py                        ← NEW: seed copy + schema.sql
  single_instance.py                     ← NEW
  build.py                               ← NEW: one command builds everything
  redguard.spec                          ← NEW: PyInstaller spec
  requirements.txt                       ← NEW: pyinstaller, pywebview, platformdirs, (PySide6 on Linux)
  env.template                           ← NEW: first-run config .env (copied from .env.example minus DATABASE_URL)
  assets/                                ← generated icons (.ico, .png) — built, not committed
  windows/redguard.iss                   ← NEW: Inno Setup script
  linux/redguard.desktop                 ← NEW: menu entry
  linux/AppRun                           ← NEW: AppImage entry script
  linux/nfpm.yaml                        ← NEW: RPM definition
  tests/test_db_bootstrap.py             ← NEW
  tests/test_paths.py                    ← NEW

.github/workflows/desktop.yml            ← NEW
README.md, CLAUDE.md, AGENTS.md          ← CHANGED: desktop sections
.gitignore                               ← CHANGED: out/, build/, dist/, desktop/assets/
```

---

## Phase 0: Spike (prove the two risky parts first)

**Why:** two things could force a design change. Test them in a throwaway branch before
writing the rest. Budget: half a day.

### 0.1 Static export + runtime-ID pages
1. In a scratch branch, apply the Phase 1 changes to **one** page only
   (`app/lab/runs/[runId]`) plus `next.config.js`.
2. `NEXT_OUTPUT=export npm run build` → confirm `out/lab/runs/_/index.html` exists.
3. Write a 20-line FastAPI app that serves `out/` and maps `/lab/runs/<anything>/` to
   `out/lab/runs/_/index.html`, and `/lab/runs/<anything>/index.txt` (plus the
   `?_rsc=` variant, see Phase 2) to the `_` equivalents.
4. Start the real backend's scripted experiment (or use an existing run ID), open
   `/lab/runs/<real-id>/` directly, and also navigate to it by clicking from
   `/lab/experiments/<id>/`. Both must show the correct run.

**If client-side navigation misbehaves** (wrong run, blank page, 404 in the console):
switch the three runtime-ID pages to query-string URLs (`/lab/runs/?id=<id>`), update
every `<Link>`/`router.push` pointing at them, and skip the fallback logic. This is the
documented fallback; it's uglier but guaranteed to work with static export.

### 0.2 Prisma in a frozen app
1. `pip install pyinstaller` in the backend venv.
2. Freeze a tiny script that connects the generated Prisma client to a SQLite copy and
   counts `Session` rows, bundling the query engine binary as data.
3. Run it with `PRISMA_QUERY_ENGINE_BINARY=<bundled path>` on a machine **without** Node
   in `PATH`. It must print the row count.

Where the engine lives after `prisma generate`: look in `~/.cache/prisma-python/binaries/`
(Linux) or `%USERPROFILE%\.cache\prisma-python\binaries\` (Windows). The file is named like
`query-engine-debian-openssl-3.0.x` / `query-engine-windows.exe`. `prisma py version`
prints the exact binary paths and platform. Use that in `build.py` instead of guessing.

**Done when:**
- [ ] A runtime-ID page renders the correct record both by direct URL and by in-app click.
- [ ] A frozen script talks to SQLite through Prisma with no Node installed.
- [ ] Decision recorded in this file: fallback route or query-string route.

---

## Phase 1: Static export of the UI

### 1.1 `next.config.js`

Add an export mode. Keep everything else as it is today.

```js
const isExport = process.env.NEXT_OUTPUT === 'export'
const backendUrl = (process.env.BACKEND_URL || 'http://localhost:8000').replace(/\/$/, '')

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: isExport ? 'export' : process.env.NEXT_OUTPUT === 'standalone' ? 'standalone' : undefined,
  // Static export: every route becomes <route>/index.html, which FastAPI serves directly.
  ...(isExport ? { trailingSlash: true, images: { unoptimized: true } } : {}),
  ...(isExport ? {} : {
    async rewrites() { /* unchanged */ },
    async redirects() { /* unchanged */ },
    experimental: { proxyTimeout: 300000 },
  }),
}
module.exports = nextConfig
```

Important details:
- Move the redirect list into a separate file (`lib/legacy-redirects.json`), so both
  `next.config.js` (web) and `backend/desktop_app.py` (desktop) read **one** list and
  can't drift apart.
- `trailingSlash: true` makes the export produce `lab/index.html` instead of
  `lab.html`, which simplifies the FastAPI routing.

### 1.2 `lib/route-id.ts`

One helper used by all three runtime-ID pages. It reads the real ID from the URL
because, in the export, the page was pre-built with the placeholder `_`.

```ts
'use client'
import { usePathname } from 'next/navigation'

export const ROUTE_PLACEHOLDER = '_'

/** The path segment after `prefix`, e.g. idFromPath('/lab/runs/abc123/', '/lab/runs/') === 'abc123'. */
export function idFromPath(pathname: string, prefix: string): string | null {
  if (!pathname.startsWith(prefix)) return null
  const id = decodeURIComponent(pathname.slice(prefix.length).split('/')[0] ?? '')
  return id && id !== ROUTE_PLACEHOLDER ? id : null
}

export function useRouteId(prefix: string, fromParams?: string): string | null {
  const pathname = usePathname()
  return idFromPath(pathname, prefix) ?? (fromParams && fromParams !== ROUTE_PLACEHOLDER ? fromParams : null)
}
```

### 1.3 Pattern for each dynamic page

A client component can't export `generateStaticParams`. Split each dynamic page into:
- `page.tsx`: a **server** component, no `"use client"`, that exports
  `generateStaticParams` and renders the client component.
- `XxxDetail.tsx`: the **existing** page code, moved verbatim, with the `use(params)`
  line replaced.

**Runtime-ID page** (`app/lab/runs/[runId]/page.tsx`):

```tsx
import RunDetail from './RunDetail'

export function generateStaticParams() {
  return [{ runId: '_' }]
}

export default async function Page({ params }: { params: Promise<{ runId: string }> }) {
  const { runId } = await params
  return <RunDetail runIdFromParams={runId} />
}
```

`app/lab/runs/[runId]/RunDetail.tsx` (first lines; everything else unchanged):

```tsx
"use client"
// ...existing imports...
import { useRouteId } from '@/lib/route-id'

export default function RunDetail({ runIdFromParams }: { runIdFromParams: string }) {
  const runId = useRouteId('/lab/runs/', runIdFromParams)
  // ...existing body; guard: if (!runId) render the existing "not found" state...
```

Apply the same to:
| Page | Prefix | Param |
|---|---|---|
| `app/runs/[sessionId]` | `/runs/` | `sessionId` |
| `app/lab/experiments/[experimentId]` | `/lab/experiments/` | `experimentId` |
| `app/lab/runs/[runId]` | `/lab/runs/` | `runId` |

Every `useEffect` that fetches by ID must list the ID in its dependency array. They
already do with `runId` etc.; keep the same variable names so the diff stays small.

Web-mode check: in `npm run dev`, `/lab/runs/abc/` gives `params.runId = 'abc'` and the
pathname also gives `abc`, so behaviour is identical.

**Dataset-ID pages** (`corpus/families/[familyId]`, `corpus/probes/[probeId]`): same split,
but `generateStaticParams` returns **every real ID**, so the export pre-builds each one
and no fallback is needed:

```tsx
import { benchmarkDataService } from '@/lib/data-service'
import ProbeDetail from './ProbeDetail'

export function generateStaticParams() {
  return benchmarkDataService.getAllProbes().map((p) => ({ probeId: p.id }))
}

export default async function Page({ params }: { params: Promise<{ probeId: string }> }) {
  const { probeId } = await params
  return <ProbeDetail probeId={probeId} />
}
```

For families, use the same data-service getter that `app/corpus/families/[familyId]` uses
today to resolve a family, and map its IDs. Check that `lib/data-service.ts` has no
`"use client"`-only code at module top level. It is imported at build time already, so
this should just work. If it touches `window`/`localStorage` at import time, guard it.

**Custom probes caveat:** probes added at runtime through the UI (`CustomProbe` table)
don't exist at build time. If the probe detail page is used for them, give that page the
same `_` placeholder fallback as the runtime-ID pages, and add `/corpus/probes/` to
the fallback list in Phase 2.

### 1.4 Build and inspect

```bash
NEXT_OUTPUT=export npm run build
ls out/                    # index.html, corpus/, lab/, runs/, models/, settings/, _next/, 404.html
ls out/lab/runs/_/         # index.html, index.txt
```

**Done when:**
- [ ] `NEXT_OUTPUT=export npm run build` succeeds, with no warnings about rewrites or redirects.
- [ ] `npm run build` (normal) and `npm run dev` still work, and every page loads in dev.
- [ ] `npm run typecheck` is clean; `npx eslint app lib next.config.js` shows no new errors.
- [ ] `docker compose config` still validates (Docker unchanged).

---

## Phase 2: Backend desktop entry point

### 2.1 `backend/desktop_app.py`

```python
"""
FastAPI app for the desktop build: the normal API (backend/app.py, untouched)
plus the static Next.js export, served from the same origin.

Only the desktop launcher imports this module. The web and Docker setups keep
using `app:app`.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

from fastapi import HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse

from app import app  # registers every /api route first

STATIC_DIR = Path(os.environ.get("REDGUARD_STATIC_DIR", Path(__file__).parent.parent / "out")).resolve()
REDIRECTS = json.loads((Path(__file__).parent.parent / "lib" / "legacy-redirects.json").read_text())  # bundled

#: Pages whose URL carries an ID that only exists at runtime. The export built
#: each one once, under the placeholder "_".
RUNTIME_ID_PREFIXES = ("/runs/", "/lab/experiments/", "/lab/runs/")
```

Routes to add, **after** importing `app` so `/api/*` keeps priority:

1. **Desktop info / open config** (only meaningful in the desktop app):
   ```python
   @app.get("/api/desktop/info")
   async def desktop_info():
       return {"desktop": True, "version": ..., "config_file": os.environ["REDGUARD_CONFIG_FILE"],
               "data_dir": os.environ["REDGUARD_DATA_DIR"], "log_file": os.environ["REDGUARD_LOG_FILE"]}

   @app.post("/api/desktop/open-config")
   async def open_config():
       path = os.environ["REDGUARD_CONFIG_FILE"]
       if sys.platform == "win32":
           os.startfile(path)                      # noqa: S606 — local desktop app
       else:
           subprocess.Popen(["xdg-open", path])
       return {"opened": path}
   ```
   Note: the new `/api/desktop/*` endpoints are additive; no existing endpoint changes.

2. **Catch-all static handler** (register last, `GET` only):
   ```python
   @app.get("/{full_path:path}", include_in_schema=False)
   async def static_ui(full_path: str, request: Request):
       path = "/" + full_path
       if path.startswith("/api/"):
           raise HTTPException(404)

       # 1) legacy redirects (same table the web build uses)
       target = _match_redirect(path, request.query_params)
       if target:
           return RedirectResponse(target, status_code=308)

       # 2) exact file (assets, index.html of a folder)
       file = _resolve(path)
       if file:
           return FileResponse(file)

       # 3) runtime-ID pages → the "_" build of that page
       for prefix in RUNTIME_ID_PREFIXES:
           if path.startswith(prefix):
               rest = path[len(prefix):].split("/", 1)       # "<id>", "index.txt" / ""
               placeholder = prefix + "_/" + (rest[1] if len(rest) > 1 else "")
               file = _resolve(placeholder)
               if file:
                   return FileResponse(file)

       # 4) not found → exported 404 page
       return FileResponse(STATIC_DIR / "404.html", status_code=404)
   ```
   `_resolve(path)` must:
   - map `/x/` → `STATIC_DIR/x/index.html`, `/x` → `STATIC_DIR/x` or `STATIC_DIR/x/index.html`;
   - **reject path traversal**: resolve the candidate and check it's inside `STATIC_DIR`
     (`candidate.resolve().is_relative_to(STATIC_DIR)`);
   - return `None` if the file doesn't exist.

3. **RSC payload requests.** When the user clicks a `<Link>`, the Next router fetches the
   target page's RSC payload (in a trailing-slash export, `…/index.txt`, sometimes with a
   `?_rsc=…` query). Step 3 above already maps `/lab/runs/<id>/index.txt` to
   `/lab/runs/_/index.txt`. Confirm the exact filenames Next 16 requests during Phase 0
   (DevTools → Network) and adjust `_resolve` if it asks for a different name.

4. **Cache headers:** `_next/static/*` files are content-hashed, so serve them with
   `Cache-Control: public, max-age=31536000, immutable`. Everything else gets `no-cache`.

5. **Redirect table format** (`lib/legacy-redirects.json`), extracted from `next.config.js`:
   ```json
   [
     {"source": "/benchmark", "destination": "/runs", "permanent": true},
     {"source": "/reports", "has_query": "session", "destination": "/runs/:session", "permanent": true},
     {"source": "/probes/:probeId", "destination": "/corpus/probes/:probeId", "permanent": true}
   ]
   ```
   `next.config.js` maps this JSON to Next's redirect objects (the `has` query rule becomes
   `has: [{type:'query', key:'session', value:'(?<session>.*)'}]`). `desktop_app.py`
   implements the same three shapes: exact source, `:param` segments, and one query
   capture. Keep it tiny; don't build a general router.

### 2.2 Tests: `backend/tests/test_desktop_app.py`

Use FastAPI's `TestClient` with `REDGUARD_STATIC_DIR` pointing at a **fake export** built
in `tmp_path` (no Next build needed in unit tests):
```
tmp/index.html  tmp/404.html  tmp/lab/index.html  tmp/lab/runs/_/index.html
tmp/lab/runs/_/index.txt  tmp/_next/static/chunk.js
```
Cover:
- `/api/health` still answers JSON, so API routes win over the catch-all.
- `/` and `/lab/` serve the right `index.html`.
- `/lab/runs/abc123/` → the `_` page; `/lab/runs/abc123/index.txt` → `_/index.txt`.
- `/benchmark` → 308 to `/runs`; `/reports?session=xyz` → `/runs/xyz`.
- `/../../etc/passwd` and encoded variants → 404, never a file outside `STATIC_DIR`.
- Unknown `/nope/` → 404 with the `404.html` body.
- `/_next/static/chunk.js` has the immutable cache header.

**Done when:**
- [ ] `pytest backend/tests/test_desktop_app.py` passes, and the full suite is still green.
- [ ] Manually: `NEXT_OUTPUT=export npm run build`, then
      `cd backend && REDGUARD_STATIC_DIR=../out DATABASE_URL=file:/tmp/rg.db uvicorn desktop_app:app --port 8123`
      (with `/tmp/rg.db` being a migrated **copy**). Every page works at
      `http://127.0.0.1:8123`, including starting a scripted Lab experiment (the SSE stream)
      and opening its experiment and run pages.

---

## Phase 3: Database bootstrap

### 3.1 What gets bundled
- `seed.db`: **copy** of `backend/prisma/dev.db` + `prisma db push` → demo data plus the
  `lab_*` tables. Built in CI (Phase 5), never committed.
- `schema.sql`: the full schema as SQL, with every `CREATE TABLE` / `CREATE INDEX` /
  `CREATE UNIQUE INDEX` rewritten to `... IF NOT EXISTS`. Generated with:
  ```bash
  prisma migrate diff --from-empty --to-schema-datamodel backend/prisma/schema.prisma --script > schema.raw.sql
  ```
  then post-processed by `build.py` (regex: `CREATE TABLE "` → `CREATE TABLE IF NOT EXISTS "`,
  same for `CREATE INDEX` / `CREATE UNIQUE INDEX`).
- `schema.sha256`: hash of `schema.prisma`, stored so the app can tell which schema a DB
  has.

### 3.2 `desktop/db_bootstrap.py`

```python
def ensure_database(data_dir: Path, bundle_dir: Path) -> Path:
    """Return the user's DB path, creating/upgrading it as needed. Never touches the bundle."""
    db = data_dir / "redguard.db"
    if not db.exists():
        data_dir.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(bundle_dir / "seed.db", db)
    _apply_schema(db, (bundle_dir / "schema.sql").read_text())
    _record_schema_hash(db, (bundle_dir / "schema.sha256").read_text().strip())
    return db
```
- `_apply_schema` runs the SQL with Python's built-in `sqlite3`
  (`executescript`) inside a transaction. The `IF NOT EXISTS` makes it idempotent, and it
  creates any tables a newer version adds.
- `_record_schema_hash` writes the hash into a tiny table
  `_redguard_meta(key TEXT PRIMARY KEY, value TEXT)`. This table isn't a Prisma model and
  Prisma ignores it.
- Before applying a **different** hash to an existing DB, copy the DB to
  `redguard.db.bak-<old-hash-prefix>`. It's cheap insurance.

**Limitation (write it in the release checklist):** `IF NOT EXISTS` adds new tables and
indexes but **not new columns** on existing tables. A release that adds or changes a
column must ship an explicit migration: a file `desktop/migrations/<n>_<name>.sql` applied
once, tracked in `_redguard_meta` as `migration:<n>`. Implement the runner now, since it's
~15 lines, even though there are no migrations yet.

### 3.3 Tests: `desktop/tests/test_db_bootstrap.py`
Use a tiny fake `seed.db` and `schema.sql` in `tmp_path`:
- first call copies the seed; second call doesn't overwrite user data (insert a row
  between calls, check it survives);
- a table missing from the user DB gets created;
- running twice is harmless;
- the bundle's `seed.db` bytes are unchanged afterwards;
- a changed schema hash makes a `.bak` copy;
- migrations run once and in order.

Plus one **real** test, marked `@pytest.mark.slow`: build `schema.sql` from the real
`schema.prisma`, apply it to a copy of the committed `dev.db`, and compare
`sqlite_master` table names with what `prisma db push` produces (reuse the
`migrated_db_template` approach). This proves the SQL route and Prisma agree.

**Done when:**
- [ ] Tests above pass.
- [ ] `git status` shows `backend/prisma/dev.db` untouched, and a row count query on it
      matches before and after.

---

## Phase 4: The launcher

### 4.1 `desktop/paths.py`
```python
APP_NAME = "RedGuard"
def bundle_dir() -> Path:     # where PyInstaller unpacked our data
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
def data_dir() -> Path:  return Path(platformdirs.user_data_dir(APP_NAME, appauthor=False))
def config_dir() -> Path: return Path(platformdirs.user_config_dir(APP_NAME, appauthor=False))
def log_file() -> Path: return data_dir() / "logs" / "redguard.log"
```
In a PyInstaller **one-folder** build, `sys._MEIPASS` is the `_internal` folder. In
development (running `python -m desktop.launcher` from the repo) it falls back to the
repo root, so the same code runs unfrozen.

### 4.2 `desktop/single_instance.py`
- Lock file `<data_dir>/redguard.lock` holding `port` and `pid`.
- On start: if the lock exists **and** `http://127.0.0.1:<port>/api/health` answers, open a
  window/browser on that URL and exit. If it doesn't answer, the lock is stale:
  overwrite it.
- Use `portalocker` or OS locking (`msvcrt.locking` / `fcntl.flock`) so two quick
  double-clicks can't both win.

### 4.3 `desktop/launcher.py`: step by step

```python
def main(argv=None) -> int:
    args = parse_args(argv)                 # --selftest, --browser, --port N, --debug
    setup_logging(log_file())               # rotating file + stderr

    # 1. config
    cfg = config_dir() / ".env"
    if not cfg.exists():
        cfg.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(bundle_dir() / "env.template", cfg)
    load_dotenv(cfg, override=False)        # python-dotenv is already a backend dependency

    # 2. database
    db = ensure_database(data_dir(), bundle_dir())

    # 3. environment for the backend (set BEFORE importing backend modules;
    #    backend/database.py creates the Prisma client at import time)
    os.environ.update({
        "DATABASE_URL": f"file:{db}",
        "PRISMA_QUERY_ENGINE_BINARY": str(bundle_dir() / "prisma" / ENGINE_NAME),
        "REDGUARD_STATIC_DIR": str(bundle_dir() / "out"),
        "REDGUARD_DESKTOP": "1",
        "REDGUARD_CONFIG_FILE": str(cfg),
        "REDGUARD_DATA_DIR": str(data_dir()),
        "REDGUARD_LOG_FILE": str(log_file()),
    })
    # REDGUARD_GIT_COMMIT is baked into the bundle at build time (build_info.json)

    # 4. import paths: bundle has core/ and backend/ as top-level data folders
    sys.path[:0] = [str(bundle_dir()), str(bundle_dir() / "backend")]

    # 5. server
    port = args.port or free_port()
    server = start_uvicorn_thread("desktop_app:app", host="127.0.0.1", port=port)
    wait_for_health(port, timeout=60)       # raise → error dialog with log path

    if args.selftest:
        return run_selftest(port)           # GET /api/health, /api/lab/cases, / → exit 0/1

    # 6. window (or browser)
    url = f"http://127.0.0.1:{port}/"
    if args.browser or not open_window(url):
        webbrowser.open(url)
        wait_until_interrupted()
    server.should_exit = True
    return 0
```

Key implementation notes:
- **`free_port()`:** bind a socket to `("127.0.0.1", 0)`, read the port, close it, and
  pass it to uvicorn. The tiny race is acceptable; retry once on `EADDRINUSE`.
- **`start_uvicorn_thread`:** create `uvicorn.Config(app, host, port, log_config=None,
  lifespan="on")` and `uvicorn.Server(config)`, and run `server.run` in a daemon thread.
  Import `desktop_app` *after* step 3.
- **`open_window(url)`:** `webview.create_window("RedGuard", url, width=1400, height=900,
  min_size=(1024, 700))`, then `webview.start(gui=...)`. On Linux pass `gui="qt"`; on
  Windows let pywebview pick (EdgeChromium). Wrap in `try`: any exception → log it and
  return `False`, so the browser fallback runs. `webview.start()` blocks until the window
  closes and must run on the **main thread**, which is why uvicorn runs in a thread.
- **WebView2 missing** (rare on Windows 10): pywebview raises; the fallback opens the
  browser, and a message box says "Install Microsoft Edge WebView2 Runtime for the app
  window". Link: https://developer.microsoft.com/microsoft-edge/webview2/
- **Downloads** (the evidence-bundle JSON on the run page): pywebview needs
  `webview.settings['ALLOW_DOWNLOADS'] = True` (check the pywebview docs for the version
  you pin). Test it in Phase 5.
- **External links** (arXiv references on probe pages) should open in the system browser,
  not inside the app window. pywebview opens `target="_blank"` links externally by default
  on most backends; verify and handle if not.
- **Error dialog before the window exists:** on Windows use
  `ctypes.windll.user32.MessageBoxW`; on Linux try `zenity --error`, else print to stderr.
  Always include the log path.
- **Console window:** build the Windows exe with `console=False` in the spec so no black
  terminal appears. `--debug` should also log to a console, via a second
  `RedGuard-debug.exe` built with `console=True`, or by attaching with `AllocConsole`.

### 4.4 `--selftest`
Used by CI on every artifact and handy for support:
1. start everything with a temporary data dir (`--selftest` sets
   `REDGUARD_DATA_DIR=<tmp>`), so it never touches the real user data;
2. `GET /api/health` → `db_connected: true`;
3. `GET /api/lab/cases` → 9 cases;
4. `GET /` and `GET /lab/runs/test/` → HTML containing `<div id="__next"` (or whatever
   the export's root marker is), status 200;
5. create a scripted experiment through the API (`POST /api/lab/experiments` with
   `"scripted": true, "cases": ["RGM-001"], "repetitions": 1`) and consume
   `/api/lab/experiments/<id>/run` until `experiment_complete`. This proves Prisma
   writes, the Mode B runner and SSE all work in the frozen app;
6. print a one-line JSON summary; exit `0` on success, `1` otherwise.

**Done when:**
- [ ] `python -m desktop.launcher` (unfrozen, from the repo, after the Phase 1 export)
      opens a window on Linux and Windows, and every page works.
- [ ] `python -m desktop.launcher --selftest` exits 0.
- [ ] A second launch focuses/reuses the first instead of starting another server.
- [ ] Killing the app mid-run and relaunching works (stale lock, stale RUNNING rows are
      handled by the existing resume logic).

---

## Phase 5: Build script + PyInstaller

### 5.1 `desktop/requirements.txt`
```
pyinstaller==6.*            # pin exact version once it works
pywebview==5.*              # pin exact
platformdirs>=4
portalocker>=2              # if used for the instance lock
PySide6-Essentials==6.*; sys_platform == "linux"   # Qt WebEngine backend for pywebview
PySide6-Addons==6.*;     sys_platform == "linux"   # contains QtWebEngine
qtpy>=2;                 sys_platform == "linux"
```
Install on top of `backend/requirements.txt`. Pin **exact** versions after the first
successful build (`pip freeze > desktop/requirements.lock`) so builds are reproducible.

### 5.2 `desktop/build.py`: one command, used by CI and humans

```
python desktop/build.py [--skip-frontend] [--skip-package] [--version 3.0.0]
```
Steps, each printing a header and failing fast:
1. **Preflight:** check the Python version (3.12), that Node ≥ 20.9 and `npm` are on PATH,
   the platform, and a clean `dist/`/`build/`.
2. **Version:** read `BENCHMARK_VERSION` from `core/version.py` (single source of truth). It
   must equal `package.json`'s `version` and the git tag if one is given, otherwise abort.
3. **Frontend:** `npm ci` → `NEXT_OUTPUT=export npm run build` → verify
   `out/index.html` and `out/lab/runs/_/index.html` exist.
4. **Prisma:** `prisma generate --schema backend/prisma/schema.prisma`; get the engine path
   from `prisma py version` output (or the cache dir) and copy it to
   `build/bundle/prisma/`.
5. **Seed DB:** copy `backend/prisma/dev.db` → `build/bundle/seed.db`; run
   `prisma db push --schema backend/prisma/schema.prisma --skip-generate` with
   `DATABASE_URL=file:<abs path to build/bundle/seed.db>`. Assert the committed `dev.db`'s
   hash is unchanged afterwards.
6. **schema.sql:** `prisma migrate diff ... --script`, rewrite to `IF NOT EXISTS`, write
   `build/bundle/schema.sql` + `schema.sha256`.
7. **Config template:** copy `.env.example` → `build/bundle/env.template`, dropping
   the `DATABASE_URL` line and adding a header comment explaining where the file lives and
   that the app must be restarted after edits.
8. **Build info:** `build/bundle/build_info.json` = `{version, git_commit, built_at, platform}`.
   The launcher reads it and sets `REDGUARD_GIT_COMMIT`.
9. **Icons:** from `public/shield.svg` generate `desktop/assets/redguard.png` (256, 512) and
   `redguard.ico` (16–256). Use `resvg`/`rsvg-convert` in CI (Linux has it via apt;
   Windows via `choco install resvg`, or generate on Linux and commit the `.ico`/`.png`
   once. **Committing the generated icons is simpler; do that.**)
10. **PyInstaller:** `pyinstaller desktop/redguard.spec --noconfirm` → `dist/RedGuard/`.
11. **Selftest:** run `dist/RedGuard/RedGuard(.exe) --selftest`; fail the build if non-zero.
12. **Package:** Windows → Phase 6; Linux → Phase 7.

### 5.3 `desktop/redguard.spec` (PyInstaller)

Key parts (adapt paths):
```python
# -*- mode: python -*-
from PyInstaller.utils.hooks import collect_all, collect_submodules
import sys

datas, binaries, hiddenimports = [], [], []
for pkg in ("prisma", "langchain", "langchain_core", "langchain_community", "langchain_groq",
            "langchain_openai", "langgraph", "ddgs", "sse_starlette", "uvicorn", "webview"):
    d, b, h = collect_all(pkg); datas += d; binaries += b; hiddenimports += h

datas += [
    ("../out", "out"),                     # static UI
    ("../core", "core"),                   # Mode A + Mode B libraries, datasets, cases, fixtures
    ("../backend", "backend"),             # app.py, lab_api.py, agents/, policy.yaml, prisma/schema.prisma
    ("../build/bundle/seed.db", "."),
    ("../build/bundle/schema.sql", "."),
    ("../build/bundle/schema.sha256", "."),
    ("../build/bundle/env.template", "."),
    ("../build/bundle/build_info.json", "."),
    ("../build/bundle/prisma", "prisma"),  # query engine binary
]
hiddenimports += collect_submodules("backend.agents")  # auto-discovered plugins

a = Analysis(["launcher_entry.py"], pathex=[".."], datas=datas, binaries=binaries,
             hiddenimports=hiddenimports, excludes=["tkinter", "matplotlib", "IPython", "pytest"])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="RedGuard",
          icon="assets/redguard.ico" if sys.platform == "win32" else None,
          console=False)
coll = COLLECT(exe, a.binaries, a.datas, name="RedGuard")
```
Notes:
- **Backend and core as data folders.** The backend is imported by module name
  (`app`, `lab_api`, `database`, …) after `sys.path` tweaks, and `agent_loader.py`
  discovers agents by listing `backend/agents/*.py` **files**. So ship `backend/` and
  `core/` as real folders (data), not only as compiled modules. Exclude `backend/.venv`,
  `__pycache__`, `tests/`, `bundles/` and any `*.db` except nothing (the seed is shipped
  separately) using a filtered copy step in `build.py`.
- **Hidden imports:** PyInstaller can't see modules imported dynamically. Expect to add
  some after the first failed run. The error in the log names the missing module; add it.
- **`launcher_entry.py`:** a 3-line script `from desktop.launcher import main;
  raise SystemExit(main())`.
- **One-folder, not one-file.** One-file unpacks ~200 MB to a temp dir on **every**
  launch, which is slow and trips antivirus. The installer, AppImage and RPM all wrap
  the folder anyway.
- **Size check:** after the build, print `du -sh dist/RedGuard`. Expected 150–250 MB on
  Windows, 250–350 MB on Linux. If much bigger, look for accidentally collected packages.

**Done when:**
- [ ] `python desktop/build.py --skip-package` produces `dist/RedGuard/` on Linux, and on
      Windows (in CI or on a Windows PC).
- [ ] `dist/RedGuard/RedGuard --selftest` exits 0 on both.
- [ ] Double-clicking `dist/RedGuard/RedGuard(.exe)` opens the window; every page works;
      a scripted experiment runs; the evidence bundle download works.

---

## Phase 6: Windows installer (Inno Setup)

### 6.1 `desktop/windows/redguard.iss`
```ini
#define AppVersion GetEnv("REDGUARD_VERSION")
[Setup]
AppId={{8B1B0C3E-REPLACE-WITH-A-REAL-GUID}}
AppName=RedGuard
AppVersion={#AppVersion}
AppPublisher=RedGuard
DefaultDirName={localappdata}\Programs\RedGuard
DefaultGroupName=RedGuard
PrivilegesRequired=lowest             ; per-user install, no admin prompt
OutputDir=..\..\dist\installer
OutputBaseFilename=RedGuard-Setup-{#AppVersion}
SetupIconFile=..\assets\redguard.ico
UninstallDisplayIcon={app}\RedGuard.exe
Compression=lzma2/ultra64
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; Flags: unchecked

[Files]
Source: "..\..\dist\RedGuard\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\RedGuard"; Filename: "{app}\RedGuard.exe"
Name: "{userdesktop}\RedGuard"; Filename: "{app}\RedGuard.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\RedGuard.exe"; Description: "Launch RedGuard"; Flags: nowait postinstall skipifsilent
```
- **Generate a real GUID once** (`[guid]::NewGuid()` in PowerShell) and never change it.
  Upgrades rely on it.
- Uninstall removes the program folder but **keeps** `%LOCALAPPDATA%\RedGuard` (the
  database) and `%APPDATA%\RedGuard` (API keys). Say so on the uninstall page, or add an
  optional "also delete my data" checkbox via `[UninstallDelete]` + a custom page (later).
- **WebView2:** Windows 11 and updated Windows 10 have it. Optionally bundle the
  Evergreen bootstrapper (`MicrosoftEdgeWebview2Setup.exe`, ~2 MB) and run it silently if
  the registry key `HKLM\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}`
  is missing. Start without this; the app falls back to the browser anyway.

### 6.2 Build command
```powershell
choco install innosetup -y        # CI; locally install from jrsoftware.org
$env:REDGUARD_VERSION = "3.0.0"
iscc desktop\windows\redguard.iss
```

### 6.3 SmartScreen / code signing
Unsigned installers show "Windows protected your PC → More info → Run anyway". That's
expected for a free open-source build. Document it in the README. Signing later needs an
OV/EV code-signing certificate (or Azure Trusted Signing), then a `signtool sign` step on
both `RedGuard.exe` and the installer. Out of scope here, but leave a placeholder step in
the workflow (`if: secrets.WINDOWS_CERT != ''`).

**Done when:**
- [ ] Installer installs without admin rights; Start-menu shortcut launches the app.
- [ ] Reinstalling a newer version over an older one keeps the database and API keys.
- [ ] Uninstall removes the program and keeps user data.
- [ ] Tested on a clean Windows 10 and Windows 11 VM (or the CI selftest plus one manual
      run on a real machine).

---

## Phase 7: Linux AppImage + RPM

Both are built on **Ubuntu 22.04** in CI from the **same** `dist/RedGuard/` folder.
Building on the oldest glibc you want to support keeps the binary runnable on newer
distros; Fedora 38+ and Ubuntu 22.04+ are covered.

### 7.1 Shared files
`desktop/linux/redguard.desktop`:
```ini
[Desktop Entry]
Type=Application
Name=RedGuard
Comment=AI agent security benchmark and multi-agent lab
Exec=redguard %U
Icon=redguard
Terminal=false
Categories=Development;Security;
StartupWMClass=RedGuard
```

### 7.2 AppImage
Layout:
```
RedGuard.AppDir/
  AppRun                 → #!/bin/sh  exec "$APPDIR/usr/lib/redguard/RedGuard" "$@"
  redguard.desktop       (Exec=RedGuard)
  redguard.png           (256×256)
  usr/lib/redguard/      ← contents of dist/RedGuard/
```
Build:
```bash
wget -q https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage
chmod +x appimagetool-x86_64.AppImage
ARCH=x86_64 ./appimagetool-x86_64.AppImage --appimage-extract-and-run RedGuard.AppDir dist/RedGuard-3.0.0-x86_64.AppImage
```
(`--appimage-extract-and-run` avoids needing FUSE on the CI runner.)

User notes for the README:
- `chmod +x RedGuard-*.AppImage && ./RedGuard-*.AppImage`.
- Ubuntu 24.04+ needs `libfuse2` (`sudo apt install libfuse2t64`) for AppImages in
  general. Otherwise run it with `--appimage-extract-and-run`.
- Qt WebEngine's sandbox can fail on some kernels (unprivileged user namespaces disabled,
  e.g. Ubuntu 24.04 AppArmor). The launcher should detect a QtWebEngine start failure and
  fall back to the browser. Alternatively set `QTWEBENGINE_DISABLE_SANDBOX=1` for the
  in-app window; it only ever loads our own `127.0.0.1` page. Decide in Phase 0/5 and
  document it.

### 7.3 RPM (Fedora / RHEL) with nfpm
`nfpm` builds RPMs on Ubuntu without `rpmbuild`. `desktop/linux/nfpm.yaml`:
```yaml
name: redguard
arch: amd64
platform: linux
version: "${REDGUARD_VERSION}"
release: 1
section: devel
maintainer: "RedGuard <maintainers@example.invalid>"
description: RedGuard — AI agent security benchmark and multi-agent lab (desktop app).
license: MIT            # check the repo's actual license
homepage: https://github.com/ShivamYash742/RedGuard
contents:
  - src: ../../dist/RedGuard/
    dst: /opt/redguard/
    type: tree
  - src: ./redguard.desktop
    dst: /usr/share/applications/redguard.desktop
  - src: ../assets/redguard.png
    dst: /usr/share/icons/hicolor/256x256/apps/redguard.png
  - src: /opt/redguard/RedGuard
    dst: /usr/bin/redguard
    type: symlink
overrides:
  rpm:
    depends:
      - libxkbcommon-x11
      - nss
      - libXcomposite
      - libXdamage
      - libXrandr
      - alsa-lib
      - mesa-libgbm
```
Build:
```bash
curl -sSfL https://github.com/goreleaser/nfpm/releases/download/v2.41.0/nfpm_2.41.0_Linux_x86_64.tar.gz | tar xz nfpm
REDGUARD_VERSION=3.0.0 ./nfpm pkg --config desktop/linux/nfpm.yaml --packager rpm --target dist/
```
- The `depends` list is what Qt WebEngine usually needs from the system; verify it by
  installing the RPM in a **clean** `fedora:latest` container and running
  `redguard --selftest` (headless: the selftest never opens a window). Then check
  `ldd /opt/redguard/_internal/PySide6/Qt/lib/libQt6WebEngineCore.so.6 | grep "not found"`.
  Add any missing libs to `depends`.
- Pin the nfpm version (don't use `latest`).

**Done when:**
- [ ] AppImage runs on Ubuntu 22.04 and Fedora (latest) desktops: the window opens and
      every page works.
- [ ] `sudo dnf install ./redguard-*.rpm` works on a clean Fedora; `redguard` launches
      from the app menu and the terminal; `sudo dnf remove redguard` removes it cleanly and
      keeps `~/.local/share/redguard`.
- [ ] In a `fedora:latest` container: `dnf install -y ./redguard-*.rpm && redguard --selftest` → exit 0.

---

## Phase 8: GitHub Actions

`.github/workflows/desktop.yml`:

```yaml
name: desktop
on:
  push:
    tags: ["v*"]
  pull_request:
    paths:
      - "desktop/**"
      - "backend/desktop_app.py"
      - "next.config.js"
      - "lib/route-id.ts"
      - "lib/legacy-redirects.json"
      - "app/**/\\[*\\]/**"
      - ".github/workflows/desktop.yml"
  workflow_dispatch:

jobs:
  build:
    strategy:
      fail-fast: false
      matrix:
        include:
          - os: windows-latest
            artifact: RedGuard-Setup-*.exe
          - os: ubuntu-22.04
            artifact: "RedGuard-*.AppImage\nredguard-*.rpm"
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: "22", cache: npm }
      - uses: actions/setup-python@v5
        with: { python-version: "3.12", cache: pip }
      - name: Linux system libraries for building/testing Qt WebEngine
        if: runner.os == 'Linux'
        run: sudo apt-get update && sudo apt-get install -y libegl1 libxkbcommon-x11-0 libxcb-cursor0 libnss3 libasound2
      - run: pip install -r backend/requirements.txt -r desktop/requirements.txt
      - run: python desktop/build.py --version ${{ github.ref_type == 'tag' && github.ref_name || '0.0.0-dev' }}
      - uses: actions/upload-artifact@v4
        with:
          name: redguard-${{ runner.os }}
          path: dist/**/${{ runner.os == 'Windows' && 'RedGuard-Setup-*.exe' || '*' }}
          retention-days: 7

  rpm-on-fedora:
    needs: build
    runs-on: ubuntu-22.04
    container: fedora:latest
    steps:
      - uses: actions/download-artifact@v4
        with: { name: redguard-Linux }
      - run: dnf install -y ./**/redguard-*.rpm && redguard --selftest

  release:
    if: github.ref_type == 'tag'
    needs: [build, rpm-on-fedora]
    runs-on: ubuntu-latest
    permissions: { contents: write }
    steps:
      - uses: actions/download-artifact@v4
      - uses: softprops/action-gh-release@v2
        with:
          files: |
            **/RedGuard-Setup-*.exe
            **/RedGuard-*.AppImage
            **/redguard-*.rpm
          generate_release_notes: true
```
Notes:
- `build.py` does the tag/version consistency check, so a mistagged release fails
  early.
- Windows runners already have Chocolatey; `build.py` (or a workflow step) runs
  `choco install innosetup -y` before packaging.
- Keep Linux on `ubuntu-22.04` (not `latest`) for glibc compatibility; revisit yearly.
- Build time is roughly 10–20 minutes per OS. Caching pip/npm helps; don't cache
  PyInstaller's `build/`.
- The regular test suite doesn't run here. If a general CI workflow is added later, it
  should run `pytest` and `npm run build`; this workflow only builds and selftests the
  app.

**Done when:**
- [ ] A PR touching `desktop/**` produces downloadable artifacts for both OSes.
- [ ] Pushing tag `v3.0.1` creates a GitHub Release with the `.exe`, `.AppImage` and `.rpm`.

---

## Phase 9: Settings page (API keys) + docs

### 9.1 API keys in the desktop app
Users configure provider keys (NVIDIA, Groq, Google, Ollama URL) in
`<config>/.env`, created on first run from the bundled template.
- `app/settings/page.tsx`: on load, `fetch('/api/desktop/info')`. If it answers
  (desktop only; 404 in the web build), show a row:
  **API keys file**: `<path>`, with an **Open** button (`POST /api/desktop/open-config`)
  and the hint "Restart RedGuard after editing."
- Follow the page's existing components and styles; no new comments.
- Later (out of scope): an in-app form that writes the keys. Reading and writing secrets
  over HTTP needs more care than a file the OS protects.

### 9.2 Docs
- **README → "Desktop app"** section: download links (Releases page), per-OS install
  steps, the SmartScreen note, AppImage `chmod +x` and `libfuse2`, RPM `dnf install`,
  where data, logs and the API-keys file live, how to reset (delete the data folder), and
  how to build locally (`pip install -r backend/requirements.txt -r desktop/requirements.txt
  && python desktop/build.py`).
- **CLAUDE.md**, under Conventions:
  - Pages must stay client components that work as a static export.
  - Runtime-ID pages read IDs via `lib/route-id.ts`.
  - New dynamic routes need the server-wrapper + `generateStaticParams` pattern, plus an
    entry in `RUNTIME_ID_PREFIXES` if the ID is runtime-only.
  - Old-URL redirects live in `lib/legacy-redirects.json`.
  - A schema change that alters a column needs a `desktop/migrations/*.sql` file.
- **AGENTS.md** Setup: one line pointing at the desktop build.

---

## Testing matrix

| Check | How | Where |
|---|---|---|
| Unit: static serving, fallbacks, redirects, traversal | `backend/tests/test_desktop_app.py` | local + CI |
| Unit: DB bootstrap, migrations, never touches seed | `desktop/tests/test_db_bootstrap.py` | local + CI |
| Unit: `idFromPath` | small TS test or a Python test of the exported HTML | local |
| Existing suite still green | `cd backend && pytest ../core/tests tests` | local |
| Web build unchanged | `npm run build`, `npm run dev`, click every page | local |
| Docker unchanged | `docker compose config` (and `up` if Docker available) | local |
| Frozen app smoke | `RedGuard --selftest` | CI, every artifact |
| RPM install on Fedora | container job | CI |
| Full UI walk-through | Playwright against `desktop_app` (unfrozen) or the frozen app with `--browser --port 8123`: Overview, Corpus, a family, a probe, Runs, a session, Models, Settings (API keys row), Lab, launch a scripted experiment, experiment page, run page (timeline, evidence download), Compare | local, before each release |
| Manual window test | Windows 10, Windows 11, Ubuntu 22.04/24.04, Fedora latest | before each release |
| Upgrade test | install vN, run an experiment, install vN+1 → the experiment is still there | before each release |

---

## Risks and fallbacks

| # | Risk | Likelihood | Fallback |
|---|---|---|---|
| 1 | Client-side navigation to runtime-ID pages breaks under static export | Medium | Query-string routes for those 3 pages (`/lab/runs/?id=…`). Decide in Phase 0. |
| 2 | PyInstaller misses dynamically imported modules (langchain, prisma, agents) | High on the first build | Add `hiddenimports`/`collect_all`; ship `backend/` as a data folder. Iterate with `--debug`. |
| 3 | Prisma engine not found in the frozen app | Medium | Set `PRISMA_QUERY_ENGINE_BINARY`; check `prisma py version` output; Phase 0.2 proves it. |
| 4 | Qt WebEngine fails to start on some Linux setups (sandbox, GPU) | Medium | Automatic browser fallback; optional `QTWEBENGINE_DISABLE_SANDBOX=1`; `--browser` flag. |
| 5 | Windows SmartScreen / antivirus flags the unsigned exe | High | Document "More info → Run anyway"; one-folder build (fewer AV hits than one-file); code signing later. |
| 6 | App size too large | Low | Exclude unused packages; check `du` in `build.py`; Linux size is mostly Qt. |
| 7 | A schema change adds a column, and existing user DBs lack it | Low now, certain eventually | `desktop/migrations/*.sql` runner (Phase 3); release checklist item. |
| 8 | Port conflicts | Low | Free port chosen at every launch. |
| 9 | Mode A agents that expect a local service (e.g. `CUSTOM_AGENT_URL`) | Low | Unchanged behaviour; configured through the same `.env`. |
| 10 | pywebview API changes between versions | Low | Pin exact versions in `desktop/requirements.lock`. |

---

## Release checklist

1. Bump `BENCHMARK_VERSION` in `core/version.py` and sync the other places CLAUDE.md
   lists (`package.json`, README badges, UI literals).
2. If `schema.prisma` changed a **column** (not just added a table), add
   `desktop/migrations/<n>_<name>.sql` and test the upgrade path.
3. Run the full test suite and a local `python desktop/build.py`; walk through the UI.
4. Merge to `main`, then `git tag v<version> && git push origin v<version>`.
5. Wait for the `desktop` workflow; download each artifact from the Release and smoke-test
   it on at least one Windows and one Linux machine.
6. Edit the auto-generated release notes: highlights, known issues, the SmartScreen note.

---

## Troubleshooting guide

| Symptom | Likely cause | Fix |
|---|---|---|
| Window never appears; log says `No module named X` | Missing PyInstaller hidden import | Add `X` to `hiddenimports`/`collect_all` in the spec; rebuild. |
| Log: `Could not find query engine` / `BinaryNotFoundError` | Prisma engine not bundled or wrong name | Check `build/bundle/prisma/`; check `PRISMA_QUERY_ENGINE_BINARY` in the log's env dump. |
| Blank white window, pages work in a browser | WebView2 missing (Windows) or QtWebEngine failure (Linux) | Install WebView2, or start with `--browser`; check the log for the Qt error. |
| `/lab/runs/<id>` shows "not found" but the run exists | Route-ID fallback or `useRouteId` issue | Check `RUNTIME_ID_PREFIXES`; the network tab should show `_/index.html` served. |
| `TableNotFoundError` for `lab_*` | `schema.sql` not applied | Delete the data folder to reseed, or check `db_bootstrap` logs. |
| Agents fail with auth errors | API keys missing | Settings → API keys file → edit → restart. |
| AppImage won't start on Ubuntu 24.04 | libfuse2 missing | `sudo apt install libfuse2t64` or `--appimage-extract-and-run`. |
| RPM install: missing library | Qt runtime dependency not listed | Add it to `nfpm.yaml` `depends`; rebuild. |

Logs: Windows `%LOCALAPPDATA%\RedGuard\logs\redguard.log`, Linux
`~/.local/share/redguard/logs/redguard.log`.

---

## Effort estimate

For one developer who knows the codebase:

| Phase | Effort |
|---|---|
| 0 Spike | 0.5 day |
| 1 Static export + page splits | 1 day |
| 2 `desktop_app.py` + tests | 1 day |
| 3 DB bootstrap + tests | 0.5 day |
| 4 Launcher | 1 day |
| 5 Build script + PyInstaller (most iteration happens here) | 1.5–2 days |
| 6 Windows installer | 0.5 day |
| 7 AppImage + RPM | 1 day |
| 8 GitHub Actions | 1 day |
| 9 Settings + docs | 0.5 day |
| **Total** | **≈ 8–9 working days** |

Suggested order if doing it in small PRs:
1. PR 1: Phase 0 findings + Phase 1 (static export, web still works).
2. PR 2: Phases 2–3 (backend desktop entry, DB bootstrap) with tests.
3. PR 3: Phases 4–5 (launcher, build script, PyInstaller) with local builds working.
4. PR 4: Phases 6–8 (installers + CI).
5. PR 5: Phase 9 (settings + docs), then tag the first release.

---

## Out of scope / later

- **Code signing** (Windows certificate; optionally signing the RPM with a GPG key).
- **Auto-update** (e.g. check the GitHub Releases API on launch and offer a download).
- **macOS** build (`.dmg`): the same architecture works (pywebview uses WKWebView), but it
  needs a macOS runner and notarization.
- **Flatpak / Flathub**, **.deb** packages, an RPM repository (COPR) for `dnf update`.
- An in-app **API-key form** instead of editing the `.env` file.
- **System tray** icon with "Open / Quit" for the browser-fallback mode.
