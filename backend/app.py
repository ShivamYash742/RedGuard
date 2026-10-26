"""
RedGuard API — the shared FastAPI app.

Each mode owns its routes: Scanner mode in `scanner_mode/api.py`, Lab mode in
`lab_mode/api.py`. This file only connects the database, sets CORS, and
mounts both routers.
"""

import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Make the core/ library importable from backend/
_PARENT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _PARENT_DIR not in sys.path:
    sys.path.insert(0, _PARENT_DIR)

from database import close_db, get_db, init_db
from request_guard import CORS_ORIGINS
from lab_mode.api import router as lab_router, shutdown_jobs
from scanner_mode.api import router as scanner_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle — connect DB on startup, disconnect on shutdown."""
    await init_db()
    yield
    await shutdown_jobs()
    await close_db()

app = FastAPI(title="RedGuard API", lifespan=lifespan)

# The UI reaches the API through the Next.js rewrite (same origin), so CORS
# only matters for direct browser calls; anything else is refused. The routers
# also reject foreign origins (request_guard.py), since CORS alone does not
# stop a cross-site request from taking effect.
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(scanner_router)
app.include_router(lab_router)


@app.get("/api/health")
async def health_check():
    prisma = await get_db()
    db_connected = prisma.is_connected()
    return {"status": "ok", "db_connected": db_connected}
