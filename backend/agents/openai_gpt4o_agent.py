"""
RedGuard Agent — OpenAI GPT-4o
───────────────────────────────
Demonstrates swapping in OpenAI as the LLM provider instead of Groq.
Uses the standard openai Python SDK with a ReAct loop via LangGraph.

Requirements (add to requirements.txt if not present):
  openai>=1.0.0

Environment variables needed in .env:
  OPENAI_API_KEY="sk-..."
  OPENAI_MODEL="gpt-4o"  (optional, defaults to gpt-4o-mini for cost savings)
"""

from __future__ import annotations

import os
from typing import Any

AGENT_NAME = "OpenAI GPT-4o Agent"
AGENT_DESCRIPTION = (
    "LangGraph ReAct agent powered by OpenAI GPT-4o with web search, "
    "calculator, and memory tools. Uses the OpenAI API instead of Groq."
)

OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL: str   = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# ── Lazy import so the file loads even without openai installed ───────────────
def _build_agent():
    try:
        from langchain_openai import ChatOpenAI
    except ImportError:
        raise RuntimeError(
            "openai / langchain-openai is not installed. "
            "Run: pip install openai langchain-openai"
        )

    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set in .env")

    from langchain_core.tools import tool
    from langchain_community.tools import DuckDuckGoSearchRun
    from langgraph.prebuilt import create_react_agent
    import numexpr

    _search = DuckDuckGoSearchRun()
    _memory: dict[str, str] = {}          # simple in-process key-value memory

    @tool
    def web_search(query: str) -> str:
        """Search the web and return a concise summary."""
        try:
            return _search.run(query)
        except Exception as exc:
            return f"Search error: {exc}"

    @tool
    def calculator(expression: str) -> str:
        """Evaluate a safe mathematical expression."""
        try:
            result = numexpr.evaluate(expression.strip())
            return str(result.item() if hasattr(result, "item") else result)
        except Exception as exc:
            return f"Calculator error: {exc}"

    @tool
    def remember(key_value: str) -> str:
        """Store a fact for later. Format: 'key=value'. E.g. remember('user_goal=write a report')."""
        if "=" not in key_value:
            return "Format must be key=value"
        k, v = key_value.split("=", 1)
        _memory[k.strip()] = v.strip()
        return f"Remembered: {k.strip()}"

    @tool
    def recall(key: str) -> str:
        """Retrieve a previously stored fact by key."""
        return _memory.get(key.strip(), f"Nothing stored under '{key.strip()}'")

    llm = ChatOpenAI(
        model=OPENAI_MODEL,
        api_key=OPENAI_API_KEY,
        temperature=0,
    )

    return create_react_agent(
        model=llm,
        tools=[web_search, calculator, remember, recall],
        state_modifier=(
            "You are a helpful AI assistant powered by GPT-4o. "
            "You can search the web, do maths, and remember facts across a conversation."
        ),
    )


_agent_instance = None

def _extract_text(result: Any) -> str:
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


async def invoke(prompt: str) -> str:
    """Send a prompt to the GPT-4o ReAct agent and return its response."""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = _build_agent()

    result = _agent_instance.invoke({"messages": [{"role": "user", "content": prompt}]})
    return _extract_text(result)
