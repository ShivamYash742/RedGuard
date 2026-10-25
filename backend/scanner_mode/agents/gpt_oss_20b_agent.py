"""
RedGuard Agent — GPT OSS 20B (via Groq)
─────────────────────────────────────────
Powered by Groq: openai/gpt-oss-20b.

Runs in the shared scaffold (_scaffold.py): same prompt, tools and step limit as every other agent.
"""

from __future__ import annotations

import os

from langchain_groq import ChatGroq
from scanner_mode.agents._scaffold import run_agent

AGENT_NAME = "GPT OSS 20B"
AGENT_DESCRIPTION = (
    "GPT OSS 20B — OpenAI's compact open-weight reasoning model (Apache 2.0) via Groq's ultra-fast LPU inference. "
    "Neutral system prompt by default; the hardened prompt is opt-in per scan. "
    "Tools: web search, file read, calculator."
)

GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
MODEL_NAME: str = "openai/gpt-oss-20b"


def model_config() -> dict:
    """What this agent sends the model, recorded on every session. The hosted APIs are
    called without a seed, so their runs are not guaranteed to repeat."""
    return {"provider": "groq", "model": MODEL_NAME, "temperature": 0, "seed": None}


def _llm():
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not set in .env")
    return ChatGroq(model=MODEL_NAME, api_key=GROQ_API_KEY, temperature=0, max_retries=2, timeout=60.0)


async def invoke(prompt: str, prompt_mode: str = "baseline") -> str:
    """Send a prompt to the agent and return its text response."""
    return await run_agent("gpt_oss_20b_agent", _llm, prompt, prompt_mode)
