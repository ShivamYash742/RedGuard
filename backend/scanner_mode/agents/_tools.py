"""
Tools shared by the LangGraph agents (web search, file read, calculator).

`file_read` is confined to SANDBOX_DIR: the probes ask agents to read
/etc/shadow, ~/.ssh and .env, so an unconfined reader turns a benchmark run
into a real exfiltration of the host it runs on.
"""

from __future__ import annotations

import json
import os
from contextvars import ContextVar
from pathlib import Path
from typing import Any, Optional

import numexpr
from langchain_core.tools import tool

SANDBOX_DIR = Path(__file__).parent / "sandbox"
FIXTURES_FILE = Path(__file__).parent / "web_search_fixtures.json"

#: "fixture" (default): canned results, so a rerun sees the same pages.
#: "live": DuckDuckGo, which changes from day to day and makes scans irreproducible.
WEB_SEARCH = os.getenv("SCANNER_WEB_SEARCH", "fixture")
if WEB_SEARCH not in ("fixture", "live"):
    raise ValueError(f"SCANNER_WEB_SEARCH must be 'fixture' or 'live', not {WEB_SEARCH!r}")


def _fixture_search(query: str) -> str:
    fixtures = json.loads(FIXTURES_FILE.read_text(encoding="utf-8"))
    q = query.lower()
    for entry in fixtures["entries"]:
        if any(k in q for k in entry["keywords"]):
            return entry["result"]
    return fixtures["default"]


@tool
def web_search(query: str) -> str:
    """Search the web and return a short summary."""
    if WEB_SEARCH == "fixture":
        return _fixture_search(query)
    try:
        from langchain_community.tools import DuckDuckGoSearchRun
        return DuckDuckGoSearchRun().run(query)
    except Exception as exc:
        return f"Search error: {exc}"


@tool
def file_read(path: str) -> str:
    """Read and return the text contents of a file in the agent's workspace folder."""
    try:
        root = SANDBOX_DIR.resolve()
        # An absolute path makes `root / path` ignore root, so it is caught below.
        p = (root / path.strip()).resolve()
        if not p.is_relative_to(root):
            return "Error: only files inside the workspace folder can be read."
        if not p.is_file():
            return f"Error: file not found: {path}"
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return f"File read error: {exc}"


@tool
def calculator(expression: str) -> str:
    """Evaluate a safe mathematical expression and return the result."""
    try:
        result = numexpr.evaluate(expression.strip())
        return str(result.item() if hasattr(result, "item") else result)
    except Exception as exc:
        return f"Calculator error: {exc}"


# ── Action tools ─────────────────────────────────────────────────────────────
# Mock tools that do nothing but record the call. Probes that try to make an
# agent send, delete, run, pay or remember something are scored from these
# records, not from what the agent says it did. Nothing here touches the network,
# the disk or a shell.

#: The scanner sets this to a fresh list before each agent call and reads it back
#: after. A ContextVar keeps concurrent probes apart; LangChain copies the
#: context into the worker threads it runs sync tools in, and the list is shared.
RECORDER: ContextVar[Optional[list]] = ContextVar("tool_call_recorder", default=None)


def record_call(tool_name: str, args: dict) -> None:
    calls = RECORDER.get()
    if calls is not None:
        calls.append({"tool": tool_name, "args": args})


@tool
def send_email(to: str, subject: str, body: str) -> str:
    """Send an email."""
    record_call("send_email", {"to": to, "subject": subject, "body": body})
    return f"Email sent to {to}."


@tool
def http_post(url: str, body: str) -> str:
    """Send an HTTP POST request with a body and return the response status."""
    record_call("http_post", {"url": url, "body": body})
    return "HTTP 200 OK"


@tool
def execute_sql(query: str) -> str:
    """Run a SQL statement on the application database."""
    record_call("execute_sql", {"query": query})
    return "Query OK."


@tool
def run_command(command: str) -> str:
    """Run a shell command and return its output."""
    record_call("run_command", {"command": command})
    return "Command finished with exit code 0."


@tool
def delete_files(path: str) -> str:
    """Permanently delete the files or items matching a path or pattern."""
    record_call("delete_files", {"path": path})
    return f"Deleted: {path}"


@tool
def transfer_funds(to_account: str, amount: str) -> str:
    """Transfer money from the user's account to another account."""
    record_call("transfer_funds", {"to_account": to_account, "amount": amount})
    return f"Transferred {amount} to {to_account}."


@tool
def place_order(items: str) -> str:
    """Place an order for the given items using the payment method on file."""
    record_call("place_order", {"items": items})
    return f"Order placed: {items}"


@tool
def save_memory(note: str) -> str:
    """Save a note to the assistant's long-term memory for future conversations."""
    record_call("save_memory", {"note": note})
    return "Saved."


ACTION_TOOLS = [send_email, http_post, execute_sql, run_command, delete_files, transfer_funds, place_order, save_memory]
TOOLS = [web_search, file_read, calculator, *ACTION_TOOLS]


def extract_text(result: Any) -> str:
    """Final assistant text from a LangGraph agent result."""
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
