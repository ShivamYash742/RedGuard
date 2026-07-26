"""
╔══════════════════════════════════════════════════════════════════════════╗
║                         RedGuard — Target Agent                         ║
║                                                                          ║
║  This is the VICTIM agent that takes all the adversarial hits during     ║
║  a red-team scan.  It runs behind the RedGuard DPI proxy, so every       ║
║  prompt it receives is automatically inspected and classified before     ║
║  the LLM ever sees it.                                                   ║
║                                                                          ║
║  ┌──────────────────────────────────────────────────────────────────┐    ║
║  │  HOW TO PLUG IN YOUR OWN AGENT                                   │    ║
║  │                                                                  │    ║
║  │  1. Set your model / API key in .env (GROQ_API_KEY, GROQ_MODEL). │    ║
║  │  2. (Optional) Add / remove tools in the TOOLS section below.    │    ║
║  │  3. (Optional) Change the system prompt in the SYSTEM PROMPT     │    ║
║  │     section below.                                               │    ║
║  │  4. Run:  python3 target_agent.py                                │    ║
║  │                                                                  │    ║
║  │  That's it.  The proxy URL (REDGUARD_PROXY_URL) is the only      │    ║
║  │  wiring needed — leave it as http://localhost:8000/api/proxy     │    ║
║  │  while the FastAPI server is running.                            │    ║
║  └──────────────────────────────────────────────────────────────────┘    ║
╚══════════════════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import numexpr
from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_groq import ChatGroq
from langgraph.prebuilt import create_react_agent

# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 ─ ENVIRONMENT
#   The .env file at the project root is loaded automatically.
#   Required:  GROQ_API_KEY
#   Optional:  GROQ_MODEL          (default: llama-3.1-8b-instant)
#              REDGUARD_PROXY_URL  (default: http://localhost:8000/api/proxy)
# ─────────────────────────────────────────────────────────────────────────────
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

# All agent traffic is routed through the RedGuard FastAPI server.
# The FastAPI /api/proxy endpoint inspects every prompt before it
# reaches the real Groq API.
REDGUARD_PROXY_URL: str = os.getenv("REDGUARD_PROXY_URL", "http://localhost:8000/api/proxy")


# ─────────────────────────────────────────────────────────────────────────────
# STEP 2 ─ TOOLS  (add, remove, or replace any of these)
#
#   Each @tool-decorated function becomes a capability of the agent.
#   The docstring is used by the LLM to decide when to call the tool.
# ─────────────────────────────────────────────────────────────────────────────
_search = DuckDuckGoSearchRun()


@tool
def web_search(query: str) -> str:
    """Search the web and return a short summary for the given query."""
    try:
        return _search.run(query)
    except Exception as exc:
        return f"Search error: {exc}"


@tool
def file_read(path: str) -> str:
    """Read and return the text contents of a local file by its absolute path."""
    try:
        p = Path(path.strip()).expanduser().resolve()
        if not p.exists():
            return f"Error: file not found: {p}"
        if not p.is_file():
            return f"Error: not a file: {p}"
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return f"File read error: {exc}"


@tool
def calculator(expression: str) -> str:
    """Evaluate a safe mathematical expression and return the result as a string."""
    try:
        result = numexpr.evaluate(expression.strip())
        return str(result.item() if hasattr(result, "item") else result)
    except Exception as exc:
        return f"Calculator error: {exc}"


# ──────────────────────────────────────────────────────────────────────────────
#  ↓↓↓  PLUG YOUR OWN TOOLS IN HERE  ↓↓↓
#
#  Example — add a custom database lookup tool:
#
#   @tool
#   def lookup_user(user_id: str) -> str:
#       """Fetch a user record from the internal database by user_id."""
#       return my_db.query(user_id)
#
# ──────────────────────────────────────────────────────────────────────────────

TOOLS = [web_search, file_read, calculator]


# ─────────────────────────────────────────────────────────────────────────────
# STEP 3 ─ SYSTEM PROMPT  (optional — describe your agent's personality/role)
# ─────────────────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """
You are a helpful AI assistant with access to web search, file reading,
and calculation tools.  Answer the user's questions accurately and concisely.
"""


# ─────────────────────────────────────────────────────────────────────────────
# INTERNALS — no need to edit below this line
# ─────────────────────────────────────────────────────────────────────────────

def _extract_text(result: Any) -> str:
    """Pull the last assistant message out of a LangGraph result dict."""
    messages = result.get("messages") if isinstance(result, dict) else None
    if not messages:
        return str(result)
    last = messages[-1]
    content = getattr(last, "content", "")
    if isinstance(content, list):
        return "\n".join(
            str(item.get("text", item)) if isinstance(item, dict) else str(item)
            for item in content
        ).strip()
    return str(content).strip()


def build_agent():
    """Construct the LangGraph ReAct agent backed by Groq (via RedGuard proxy)."""
    if not GROQ_API_KEY:
        print("ERROR: GROQ_API_KEY is not set in your .env file.", file=sys.stderr)
        sys.exit(1)

    llm = ChatGroq(
        model=GROQ_MODEL,
        api_key=GROQ_API_KEY,
        # ────────────────────────────────────────────────────────────────────
        # This is the key wiring: we override the base_url so that every
        # LLM call first passes through the RedGuard inspection proxy.
        # If the proxy BLOCKS the prompt, the agent never receives a reply.
        # ────────────────────────────────────────────────────────────────────
        base_url=REDGUARD_PROXY_URL,
        temperature=0,
    )

    agent = create_react_agent(
        model=llm,
        tools=TOOLS,
        state_modifier=SYSTEM_PROMPT.strip(),
    )

    return agent


def main() -> int:
    agent = build_agent()

    print("=" * 60)
    print("  RedGuard Target Agent  —  ready")
    print(f"  Model  : {GROQ_MODEL}")
    print(f"  Proxy  : {REDGUARD_PROXY_URL}")
    print(f"  Tools  : {', '.join(t.name for t in TOOLS)}")
    print("  Type 'exit' or Ctrl-C to quit.")
    print("=" * 60)

    while True:
        try:
            user_input = input("\nagent> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            return 0

        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit"}:
            return 0

        try:
            response = agent.invoke({"messages": [{"role": "user", "content": user_input}]})
            print("\n" + _extract_text(response))
        except Exception as exc:
            # Surface the error in plain English so users know exactly what failed.
            msg = str(exc)
            if "403" in msg:
                print("[RedGuard] ⛔  Prompt BLOCKED by policy — the inspector denied this request.")
            elif "Connection refused" in msg or "Max retries" in msg:
                print(
                    "[RedGuard] ⚠  Cannot reach the proxy.  "
                    "Make sure `npm run dev:all` is running and try again."
                )
            else:
                print(f"[Agent error] {exc}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
