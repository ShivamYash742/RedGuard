"""
RedGuard Agent — Example Custom Agent
──────────────────────────────────────
Template for an agent backed by an OpenAI-compatible endpoint of your own.

To create your own agent:
  1. Copy this file to backend/scanner_mode/agents/my_agent.py
  2. Set AGENT_NAME, AGENT_DESCRIPTION, and the endpoint / model / key
  3. Keep the run_agent() call: it supplies the shared prompt, tools and step
     limit, which is what makes your agent comparable with the others
  4. The invoke(prompt) coroutine is the only required interface; accept an
     optional prompt_mode ("baseline" / "hardened") to support both scan modes

Environment variables (optional):
  CUSTOM_AGENT_URL   = "http://localhost:5000/v1/chat/completions"
  CUSTOM_AGENT_MODEL = "custom-model"
  CUSTOM_AGENT_KEY   = ""  (leave empty if no auth needed)
"""

from __future__ import annotations

import os

from langchain_openai import ChatOpenAI
from scanner_mode.agents._scaffold import run_agent

AGENT_NAME = "Custom Template Agent"
AGENT_DESCRIPTION = (
    "Template for an OpenAI-compatible endpoint of your own. "
    "Runs in the shared scaffold: the same prompt, tools and step limit as every other agent. "
    "Same tools as every agent: web search, file read, calculator and mock action tools."
)

LLM_ENDPOINT: str = os.getenv("CUSTOM_AGENT_URL", "http://localhost:5000/v1/chat/completions")
LLM_MODEL: str    = os.getenv("CUSTOM_AGENT_MODEL", "custom-model")
LLM_KEY: str      = os.getenv("CUSTOM_AGENT_KEY", "")


def model_config() -> dict:
    return {"provider": "custom", "model": LLM_MODEL, "temperature": 0, "seed": None}


def _llm():
    # The client wants the API root (".../v1"), not the full chat-completions URL.
    base = LLM_ENDPOINT.removesuffix("/chat/completions").rstrip("/")
    return ChatOpenAI(model=LLM_MODEL, api_key=LLM_KEY or "none", base_url=base,
                      temperature=0, max_retries=2, timeout=60.0)


async def invoke(prompt: str, prompt_mode: str = "baseline") -> str:
    """Send a prompt to the configured endpoint and return its text response."""
    return await run_agent("example_custom_agent", _llm, prompt, prompt_mode)
