"""
RedGuard Agent — GPT OSS 120B (via Groq)
─────────────────────────────────────────
Powered by Groq: openai/gpt-oss-120b.

System prompt is loaded from agents/system_prompts.json via _prompt_loader.
Edit that file to update the prompt — no Python changes needed.
"""

from __future__ import annotations

import os
from typing import Any

from langchain_groq import ChatGroq
from langgraph.prebuilt import create_react_agent
from agents._prompt_loader import build_system_prompt
from agents._tools import TOOLS, extract_text

AGENT_NAME = "GPT OSS 120B"
AGENT_DESCRIPTION = (
    "GPT OSS 120B — OpenAI's open-weight 117B MoE reasoning model (Apache 2.0) via Groq's ultra-fast LPU inference. "
    "Neutral system prompt by default; the hardened prompt is opt-in per scan. "
    "Tools: web search, file read, calculator."
)

GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
MODEL_NAME: str = "openai/gpt-oss-120b"

# One compiled agent per prompt mode ("baseline" / "hardened").
_agents: dict[str, Any] = {}


def _get_agent(prompt_mode: str):
    if prompt_mode not in _agents:
        if not GROQ_API_KEY:
            raise RuntimeError("GROQ_API_KEY is not set in .env")
        llm = ChatGroq(
            model=MODEL_NAME,
            api_key=GROQ_API_KEY,
            temperature=0,
            max_retries=2,
            timeout=60.0,
        )
        _agents[prompt_mode] = create_react_agent(
            model=llm,
            tools=TOOLS,
            prompt=build_system_prompt("gpt_oss_120b_agent", prompt_mode),
        )
    return _agents[prompt_mode]


async def invoke(prompt: str, prompt_mode: str = "baseline") -> str:
    """Send a prompt to GPT OSS 120B agent and return text response."""
    agent = _get_agent(prompt_mode)
    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": prompt}]},
        config={"recursion_limit": 15},
    )
    return extract_text(result)
