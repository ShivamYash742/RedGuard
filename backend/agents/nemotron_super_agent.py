"""
RedGuard Agent — Nemotron 3 Super (120B)
──────────────────────────────────────────
Powered by NVIDIA NIM: nvidia/nemotron-3-super-120b-a12b.

System prompt is loaded from agents/system_prompts.json via _prompt_loader.
Edit that file to update the prompt — no Python changes needed.
"""

from __future__ import annotations

import os
from typing import Any

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from agents._prompt_loader import build_system_prompt
from agents._tools import TOOLS, extract_text

AGENT_NAME = "Nemotron-3 Super (120B)"
AGENT_DESCRIPTION = (
    "NVIDIA Nemotron 3 Super 120B — high-performance reasoning model via NVIDIA NIM. "
    "Neutral system prompt by default; the hardened prompt is opt-in per scan. "
    "Tools: web search, file read, calculator."
)

NVIDIA_API_KEY: str = os.getenv("NVIDIA_API_KEY", "")
MODEL_NAME: str = "nvidia/nemotron-3-super-120b-a12b"

# One compiled agent per prompt mode ("baseline" / "hardened").
_agents: dict[str, Any] = {}


def _get_agent(prompt_mode: str):
    if prompt_mode not in _agents:
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
        _agents[prompt_mode] = create_react_agent(
            model=llm,
            tools=TOOLS,
            prompt=build_system_prompt("nemotron_super_agent", prompt_mode),
        )
    return _agents[prompt_mode]


async def invoke(prompt: str, prompt_mode: str = "baseline") -> str:
    """Send a prompt to Nemotron-3 Super (120B) agent and return text response."""
    agent = _get_agent(prompt_mode)
    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": prompt}]},
        config={"recursion_limit": 15},
    )
    return extract_text(result)
