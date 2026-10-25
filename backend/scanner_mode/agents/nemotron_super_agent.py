"""
RedGuard Agent — Nemotron 3 Super (120B)
──────────────────────────────────────────
Powered by NVIDIA NIM: nvidia/nemotron-3-super-120b-a12b.

Runs in the shared scaffold (_scaffold.py): same prompt, tools and step limit as every other agent.
"""

from __future__ import annotations

import os

from langchain_openai import ChatOpenAI
from scanner_mode.agents._scaffold import run_agent

AGENT_NAME = "Nemotron-3 Super (120B)"
AGENT_DESCRIPTION = (
    "NVIDIA Nemotron 3 Super 120B — high-performance reasoning model via NVIDIA NIM. "
    "Neutral system prompt by default; the hardened prompt is opt-in per scan. "
    "Tools: web search, file read, calculator."
)

NVIDIA_API_KEY: str = os.getenv("NVIDIA_API_KEY", "")
MODEL_NAME: str = "nvidia/nemotron-3-super-120b-a12b"


def _llm():
    if not NVIDIA_API_KEY:
        raise RuntimeError("NVIDIA_API_KEY is not set in .env")
    return ChatOpenAI(
        model=MODEL_NAME,
        openai_api_key=NVIDIA_API_KEY,
        base_url="https://integrate.api.nvidia.com/v1",
        temperature=0,
        max_retries=2,
        timeout=60.0,
    )


async def invoke(prompt: str, prompt_mode: str = "baseline") -> str:
    """Send a prompt to the agent and return its text response."""
    return await run_agent("nemotron_super_agent", _llm, prompt, prompt_mode)
