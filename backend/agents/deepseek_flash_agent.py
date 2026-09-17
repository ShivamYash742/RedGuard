"""
RedGuard Agent — DeepSeek V4 Flash
───────────────────────────────────
Powered by NVIDIA NIM: deepseek-ai/deepseek-v4-flash.

System prompt is loaded from agents/system_prompts.json via _prompt_loader.
Edit that file to update the prompt — no Python changes needed.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import numexpr
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from agents._prompt_loader import build_system_prompt

AGENT_NAME = "DeepSeek V4 Flash"
AGENT_DESCRIPTION = (
    "DeepSeek V4 Flash — fast reasoning and code-execution model via NVIDIA NIM. "
    "Hardened system prompt covers all 12 RedGuard scenarios with code-context emphasis. "
    "Tools: web search, file read, calculator."
)

NVIDIA_API_KEY: str = os.getenv("NVIDIA_API_KEY", "")
MODEL_NAME: str = "deepseek-ai/deepseek-v4-flash-0731"

# ── Tools (lazy-instantiated) ─────────────────────────────────────────────────

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
    """Evaluate a safe mathematical expression and return the result."""
    try:
        result = numexpr.evaluate(expression.strip())
        return str(result.item() if hasattr(result, "item") else result)
    except Exception as exc:
        return f"Calculator error: {exc}"


TOOLS = [web_search, file_read, calculator]

# ── System Prompt (loaded from system_prompts.json) ──────────────────────────
SYSTEM_PROMPT = build_system_prompt("deepseek_flash_agent")

_agent_instance = None


def _get_agent():
    global _agent_instance
    if _agent_instance is None:
        if not NVIDIA_API_KEY:
            raise RuntimeError("NVIDIA_API_KEY is not set in .env")
        llm = ChatOpenAI(
            model=MODEL_NAME,
            openai_api_key=NVIDIA_API_KEY,
            base_url="https://integrate.api.nvidia.com/v1",
            temperature=0,
            max_retries=2,
            timeout=60.0,
        )
        _agent_instance = create_react_agent(
            model=llm,
            tools=TOOLS,
            prompt=SYSTEM_PROMPT,
        )
    return _agent_instance


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
    """Send a prompt to DeepSeek V4 Flash agent and return text response."""
    agent = _get_agent()
    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": prompt}]},
        config={"recursion_limit": 5},
    )
    return _extract_text(result)
