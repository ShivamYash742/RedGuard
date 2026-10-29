"""Guard for the local API, shared by both modes.

A web page open in the same browser can send this API "simple" cross-origin
requests (a text/plain POST, a bodyless POST, a GET that streams a scan), and
CORS only stops it reading the answer, not the side effect. Two checks run
before every route of both routers:

* Origin: a request that carries an Origin header must come from CORS_ORIGINS.
  Browsers always send Origin on cross-origin POST/PUT/DELETE; curl and the UI's
  own same-origin GETs send none and pass.
* Content type: a request with a body must declare application/json, which a
  cross-origin page cannot send without a CORS preflight.

Both UI origins are allowed by default because the Next.js rewrite forwards the
browser's Origin to the backend untouched.
"""

import os

from fastapi import HTTPException, Request

CORS_ORIGINS = [
    o.strip()
    for o in os.environ.get("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
    if o.strip()
]


def guard_request(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin is not None and origin not in CORS_ORIGINS:
        raise HTTPException(status_code=403, detail=f"Origin {origin!r} is not in CORS_ORIGINS")

    has_body = request.headers.get("content-length", "0") != "0" or "transfer-encoding" in request.headers
    if request.method in ("POST", "PUT", "PATCH") and has_body:
        if request.headers.get("content-type", "").split(";")[0].strip().lower() != "application/json":
            raise HTTPException(status_code=415, detail="Content-Type must be application/json")


async def json_object(request: Request) -> dict:
    """The request body as a JSON object. Invalid JSON, an empty body or a non-object (a string, a list)
    is the caller's mistake: 400, not an exception out of the handler."""
    try:
        body = await request.json()
    except ValueError:  # JSONDecodeError and UnicodeDecodeError
        raise HTTPException(status_code=400, detail="body must be valid JSON")
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="body must be a JSON object")
    return body
