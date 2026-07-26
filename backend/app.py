import asyncio
import json
import uuid
from datetime import datetime
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from database import get_db, init_db, close_db
from inspector import Inspector
from scanner import run_scan
from report_generator import generate_report_for_session
from agent_loader import list_agents, DEFAULT_AGENT_ID

app = FastAPI(title="RedGuard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    await init_db()

@app.on_event("shutdown")
async def shutdown_event():
    await close_db()

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
    
    return {
        "totalSessions": total_sessions,
        "totalProbes": tp,
        "totalBlocked": tb,
        "totalAllowed": ta,
        "overallBlockRate": rate,
        "coverageGap": ta
    }

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

# ── Agent discovery ──────────────────────────────────────────────────────────
@app.get("/api/agents")
async def get_agents():
    """List all agents discovered in the backend/agents/ folder."""
    return list_agents()

# Globals to keep track of running scans for SSE
running_scans = {}

@app.post("/api/scan/start")
async def start_scan(request: Request):
    prisma = await get_db()
    # agentId is optional; falls back to default_agent
    try:
        body = await request.json()
        agent_id = body.get("agentId", DEFAULT_AGENT_ID)
    except Exception:
        agent_id = DEFAULT_AGENT_ID

    session_str = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # Create DB entry immediately
    session = await prisma.session.create(
        data={
            "sessionId": session_str,
            "status": "RUNNING"
        }
    )
    
    # Create async generator and store it (with selected agent)
    gen = run_scan(session.id, agent_id=agent_id)
    running_scans[session.id] = gen
    
    return {"sessionId": session.id, "displayId": session_str, "agentId": agent_id}

@app.get("/api/scan/stream")
async def stream_scan(sessionId: str):
    if sessionId not in running_scans:
        raise HTTPException(status_code=404, detail="Scan not found or already finished")
        
    gen = running_scans[sessionId]
    
    async def sse_generator():
        try:
            async for data in gen:
                yield {
                    "event": data.get("event", "message"),
                    "data": json.dumps(data.get("data", {}))
                }
            # scan complete, generate report
            await generate_report_for_session(sessionId)
        finally:
            if sessionId in running_scans:
                del running_scans[sessionId]
                
    return EventSourceResponse(sse_generator())

# Proxy route
@app.post("/api/proxy")
async def proxy_request(request: Request):
    data = await request.json()
    prompt = ""
    messages = data.get("messages", [])
    if messages and len(messages) > 0:
        prompt = messages[0].get("content", "")
        
    inspector = Inspector()
    insp_result = inspector.process(prompt)
    verdict = insp_result["policy_result"]["verdict"]
    
    if verdict == "DENY":
        return JSONResponse(
            status_code=403, 
            content={"error": insp_result["policy_result"]["deny_message"]}
        )
        
    # we don't actually forward to Groq here as this is intended for tests or direct calls
    return {"status": "ALLOWED", "metadata": insp_result["metadata"]}
