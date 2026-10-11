import asyncio
import json
import os
import sys
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

# Make redguard library importable from backend/
_PARENT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _PARENT_DIR not in sys.path:
    sys.path.insert(0, _PARENT_DIR)
from core.datasets.loader import load_all_datasets
from core.version import BENCHMARK_VERSION

from database import get_db, init_db, close_db
from scanner import init_scan_session, run_family_scan, finalize_scan, session_prompt_mode
from leaderboard import leaderboard_rows
from report_generator import generate_report_for_session
from agent_loader import list_agents, get_agent, DEFAULT_AGENT_ID
from lab_api import router as lab_router, shutdown_jobs


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle — connect DB on startup, disconnect on shutdown."""
    await init_db()
    yield
    await shutdown_jobs()
    await close_db()

app = FastAPI(title="RedGuard API", lifespan=lifespan)

# The UI reaches the API through the Next.js rewrite (same origin), so CORS
# only matters for direct browser calls; anything else is refused.
CORS_ORIGINS = [o.strip() for o in os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mode B (multi-agent lab). Additive: every /api/lab/* route lives in
# lab_api.py and no existing route is touched (MULTI_AGENT_LAB_PLAN.md §18).
app.include_router(lab_router)


@app.get("/api/health")
async def health_check():
    prisma = await get_db()
    db_connected = prisma.is_connected()
    return {"status": "ok", "db_connected": db_connected}

@app.get("/api/stats")
async def get_stats():
    prisma = await get_db()
    total_sessions = await prisma.session.count()
    
    sessions = await prisma.session.find_many()
    tp = sum(s.totalProbes or 0 for s in sessions)
    tb = sum(s.blocked or 0 for s in sessions)
    ta = sum(s.allowed or 0 for s in sessions)
    
    rate = (tb / tp) if tp > 0 else 0.0
    
    # Count actual unique probes in benchmark (builtin datasets + active custom probes)
    builtin_count = len(load_all_datasets(validate=False))
    custom_count = await prisma.customprobe.count(where={"active": True})
    total_active_probes = builtin_count + custom_count
    
    return {
        "totalSessions": total_sessions,
        "totalProbes": total_active_probes,
        "totalEvaluationsFired": tp,
        "totalBlocked": tb,
        "totalAllowed": ta,
        "overallBlockRate": rate,
        "coverageGap": ta
    }

@app.get("/api/leaderboard")
async def get_leaderboard():
    """Measured results per (agent, prompt mode); legacy runs are excluded."""
    prisma = await get_db()
    sessions = await prisma.session.find_many(include={"events": True})
    return leaderboard_rows(sessions)

@app.get("/api/sessions")
async def list_sessions():
    prisma = await get_db()
    sessions = await prisma.session.find_many(
        order={"startedAt": "desc"}
    )
    # convert datetime to string
    res = []
    for s in sessions:
        d = s.model_dump()
        d['startedAt'] = d['startedAt'].isoformat() if d['startedAt'] else None
        d['finishedAt'] = d['finishedAt'].isoformat() if d['finishedAt'] else None
        res.append(d)
    return res

@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    prisma = await get_db()
    session = await prisma.session.find_unique(
        where={"sessionId": session_id},
        include={"events": True}
    )
    if not session:
        # Fallback to check by db id
        session = await prisma.session.find_unique(
            where={"id": session_id},
            include={"events": True}
        )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    d = session.model_dump()
    d['startedAt'] = d['startedAt'].isoformat() if d['startedAt'] else None
    d['finishedAt'] = d['finishedAt'].isoformat() if d['finishedAt'] else None
    for ev in d.get('events', []):
        ev['timestamp'] = ev['timestamp'].isoformat() if ev['timestamp'] else None
        if isinstance(ev.get('regexMetadata'), str):
            try: ev['regexMetadata'] = json.loads(ev['regexMetadata'])
            except: pass
        if isinstance(ev.get('classifierResult'), str):
            try: ev['classifierResult'] = json.loads(ev['classifierResult'])
            except: pass
    return d

@app.get("/api/events")
async def get_events(category: str = None, status: str = None, sessionId: str = None):
    prisma = await get_db()
    where_clause = {}
    if category:
        where_clause["category"] = category
    if status:
        where_clause["status"] = status
    if sessionId:
        where_clause["sessionId"] = sessionId
        
    events = await prisma.probeevent.find_many(
        where=where_clause,
        order={"timestamp": "desc"}
    )
    res = []
    for ev in events:
        d = ev.model_dump()
        d['timestamp'] = d['timestamp'].isoformat() if d['timestamp'] else None
        if isinstance(d.get('regexMetadata'), str):
            try: d['regexMetadata'] = json.loads(d['regexMetadata'])
            except: pass
        if isinstance(d.get('classifierResult'), str):
            try: d['classifierResult'] = json.loads(d['classifierResult'])
            except: pass
        res.append(d)
    return res

@app.get("/api/reports/{session_id}")
async def get_report(session_id: str):
    prisma = await get_db()
    report = await prisma.report.find_unique(
        where={"sessionId": session_id}
    )
    if not report:
        # check by actual session id string instead of db id if needed
        session = await prisma.session.find_unique(where={"sessionId": session_id})
        if session:
            report = await prisma.report.find_unique(where={"sessionId": session.id})
    
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
        
    d = report.model_dump()
    d['generatedAt'] = d['generatedAt'].isoformat() if d['generatedAt'] else None
    if isinstance(d.get('reportJson'), str):
        try: d['reportJson'] = json.loads(d['reportJson'])
        except: pass
    return d

@app.get("/api/policy")
async def get_policy():
    try:
        with open("policy.yaml", "r") as f:
            yaml_content = f.read()
            return {"yaml": yaml_content}
    except Exception as e:
        return {"error": str(e)}

@app.put("/api/policy")
async def update_policy(request: Request):
    data = await request.json()
    yaml_content = data.get("yaml", "")
    with open("policy.yaml", "w") as f:
        f.write(yaml_content)
    return {"status": "success"}

# ── Custom Probes ────────────────────────────────────────────────────────────
@app.get("/api/probes")
async def get_probes():
    prisma = await get_db()
    probes = await prisma.customprobe.find_many(order={"createdAt": "desc"})
    res = []
    for p in probes:
        d = p.model_dump()
        d['createdAt'] = d['createdAt'].isoformat() if d['createdAt'] else None
        d['updatedAt'] = d['updatedAt'].isoformat() if d['updatedAt'] else None
        res.append(d)
    return res


@app.get("/api/probes/count")
async def get_probe_count():
    """Return total count of built-in + active custom probes."""
    prisma = await get_db()
    builtin_count = len(load_all_datasets(validate=False))
    custom_count = await prisma.customprobe.count(where={"active": True})
    return {"builtin": builtin_count, "custom": custom_count, "total": builtin_count + custom_count}

@app.post("/api/probes")
async def create_probe(request: Request):
    prisma = await get_db()
    data = await request.json()
    if "category" not in data or "promptText" not in data:
        raise HTTPException(status_code=400, detail="Missing category or promptText")
        
    probe = await prisma.customprobe.create(
        data={
            "category": data["category"],
            "promptText": data["promptText"],
            "active": data.get("active", True)
        }
    )
    return probe.model_dump()

@app.delete("/api/probes/{probe_id}")
async def delete_probe(probe_id: str):
    prisma = await get_db()
    try:
        await prisma.customprobe.delete(where={"id": probe_id})
        return {"status": "deleted"}
    except Exception:
        raise HTTPException(status_code=404, detail="Probe not found")

@app.put("/api/probes/{probe_id}/toggle")
async def toggle_probe(probe_id: str):
    prisma = await get_db()
    probe = await prisma.customprobe.find_unique(where={"id": probe_id})
    if not probe:
        raise HTTPException(status_code=404, detail="Probe not found")
        
    updated = await prisma.customprobe.update(
        where={"id": probe_id},
        data={"active": not probe.active}
    )
    return updated.model_dump()

# ── Agent discovery ──────────────────────────────────────────────────────────
@app.get("/api/agents")
async def get_agents():
    """List all agents discovered in the backend/agents/ folder."""
    return list_agents()

@app.post("/api/scan/start")
async def start_scan(request: Request):
    prisma = await get_db()
    model_name = None
    requested_mode = "baseline"
    try:
        body = await request.json()
        agent_id = body.get("agentId", DEFAULT_AGENT_ID)
        model_name = body.get("model")
        requested_mode = body.get("promptMode", "baseline")
    except Exception:
        agent_id = DEFAULT_AGENT_ID

    mod = get_agent(agent_id)
    agent_name = getattr(mod, "AGENT_NAME", agent_id)
    try:
        prompt_mode = session_prompt_mode(agent_id, requested_mode)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    session_str = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    session = await prisma.session.create(
        data={
            "sessionId": session_str,
            "agentId": agent_id,
            "agentName": agent_name,
            "status": "RUNNING",
            "benchmarkVersion": BENCHMARK_VERSION,
            "promptMode": prompt_mode,
        }
    )

    
    init_data = await init_scan_session(session.id)
    
    return {
        "sessionId": session.id,
        "displayId": session_str,
        "agentId": agent_id,
        "model": model_name,
        "promptMode": prompt_mode,
        "total_probes": init_data["total_probes"],
        "families": init_data["families"],
        "controls": init_data["controls"]
    }

@app.get("/api/scan/family")
async def scan_family(sessionId: str, agentId: str, category: str, model: str = None):
    if not all([sessionId, agentId, category]):
        raise HTTPException(status_code=400, detail="Missing required parameters")
        
    gen = run_family_scan(sessionId, agentId, category, model_name=model)
    
    async def sse_generator():
        async for data in gen:
            yield {
                "event": data.get("event", "message"),
                "data": json.dumps(data.get("data", {}))
            }
            
    # `no-transform` stops the Next.js proxy gzipping the stream, which would
    # hold every event until the family finishes (same fix as the Lab stream).
    return EventSourceResponse(sse_generator(), headers={"Cache-Control": "no-store, no-transform"})


@app.post("/api/scan/finalize")
async def finalize_scan_route(request: Request):
    body = await request.json()
    session_id = body.get("sessionId")
    
    if not session_id:
        raise HTTPException(status_code=400, detail="Missing sessionId")
        
    results = await finalize_scan(session_id)
    await generate_report_for_session(session_id)
    return results

@app.post("/api/scan/cancel")
async def cancel_scan_route(request: Request):
    body = await request.json()
    session_id = body.get("sessionId")
    if not session_id:
        raise HTTPException(status_code=400, detail="Missing sessionId")
    
    prisma = await get_db()
    # Delete cascade or delete manually
    await prisma.probeevent.delete_many(where={"sessionId": session_id})
    await prisma.report.delete_many(where={"sessionId": session_id})
    await prisma.policysnapshot.delete_many(where={"sessionId": session_id})
    await prisma.session.delete(where={"id": session_id})
    
    return {"status": "cancelled and deleted"}
