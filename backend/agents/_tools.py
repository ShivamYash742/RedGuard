"""
Tools shared by the LangGraph agents (web search, file read, calculator).

`file_read` is confined to SANDBOX_DIR: the probes ask agents to read
/etc/shadow, ~/.ssh and .env, so an unconfined reader turns a benchmark run
into a real exfiltration of the host it runs on.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numexpr
from langchain_core.tools import tool

SANDBOX_DIR = Path(__file__).parent / "sandbox"


@tool
def web_search(query: str) -> str:
    """Search the web and return a short summary."""
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


TOOLS = [web_search, file_read, calculator]


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
