"""
RedGuard Agent — Ollama (Local / Offline)
─────────────────────────────────────────
Runs a local Granite model on your own machine through Ollama's OpenAI-compatible
endpoint. No API key, no internet.

Runs in the shared scaffold (_scaffold.py): the same prompt, tools and step limit
as every hosted agent, with temperature 0 and a fixed seed so a rerun repeats.

Prerequisites:
  1. Install Ollama: https://ollama.com/download
  2. Pull a model:   ollama pull granite3.3:2b
  3. Start Ollama:   ollama serve   (runs on http://localhost:11434)

Environment variables (optional):
  OLLAMA_BASE_URL="http://localhost:11434"  (default)
  OLLAMA_MODEL="granite3.3:2b"               (default)
  SCANNER_TEMPERATURE=0                      (default)
  SCANNER_SEED=0                             (default)
"""

from __future__ import annotations

import os

from langchain_openai import ChatOpenAI
from scanner_mode.agents._scaffold import run_agent

AGENT_NAME = "Ollama Local Agent"
AGENT_DESCRIPTION = (
    "100% offline agent running Granite 3.3 (2B) on your own hardware via Ollama. "
    "No API key, no internet, no data leaves your machine. "
    "Neutral system prompt by default; the hardened prompt is opt-in per scan. "
    "Same tools as every agent: web search, file read, calculator and mock action tools."
)

OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "granite3.3:2b")
TEMPERATURE: float = float(os.getenv("SCANNER_TEMPERATURE", "0"))
SEED: int = int(os.getenv("SCANNER_SEED", "0"))


def model_config() -> dict:
    return {"provider": "ollama", "model": OLLAMA_MODEL, "temperature": TEMPERATURE, "seed": SEED}


def _llm():
    return ChatOpenAI(
        model=OLLAMA_MODEL,
        api_key="ollama",  # required by the client, ignored by Ollama
        base_url=f"{OLLAMA_BASE_URL.rstrip('/')}/v1",
        temperature=TEMPERATURE,
        seed=SEED,
        max_retries=2,
        timeout=60.0,
    )


async def invoke(prompt: str, prompt_mode: str = "baseline") -> str:
    """Send a prompt to the agent and return its text response."""
    return await run_agent("ollama_local_agent", _llm, prompt, prompt_mode)
