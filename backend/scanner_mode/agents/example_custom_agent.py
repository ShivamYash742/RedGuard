"""
RedGuard Agent — Example Custom Agent
──────────────────────────────────────
Hardened reference template for custom agents.

System prompt is loaded from agents/system_prompts.json via _prompt_loader.
Edit that file to update the prompt — no Python changes needed.

To create your own agent:
  1. Copy this file to backend/scanner_mode/agents/my_agent.py
  2. Set AGENT_NAME, AGENT_DESCRIPTION, and LLM_ENDPOINT / API_KEY
  3. Add an entry for your agent_id in agents/system_prompts.json
  4. The invoke(prompt) coroutine is the only required interface; accept an
     optional prompt_mode ("baseline" / "hardened") to support both scan modes

Environment variables (optional):
  CUSTOM_AGENT_URL   = "http://localhost:5000/v1/chat/completions"
  CUSTOM_AGENT_MODEL = "custom-model"
  CUSTOM_AGENT_KEY   = ""  (leave empty if no auth needed)
"""

from __future__ import annotations

import json
import os
import httpx
from scanner_mode.agents._prompt_loader import build_system_prompt

AGENT_NAME = "Custom Template Agent"
AGENT_DESCRIPTION = (
    "Hardened reference implementation for custom agents. "
    "Uses a simple httpx LLM call — no LangChain required. "
    "System prompt loaded from system_prompts.json — covers all 12 RedGuard scenarios "
    "and all 8 attack families. Copy and adapt for your own deployment."
)

LLM_ENDPOINT: str = os.getenv("CUSTOM_AGENT_URL", "http://localhost:5000/v1/chat/completions")
LLM_MODEL: str    = os.getenv("CUSTOM_AGENT_MODEL", "custom-model")
LLM_KEY: str      = os.getenv("CUSTOM_AGENT_KEY", "")

async def invoke(prompt: str, prompt_mode: str = "baseline") -> str:
    """
    Send a prompt to the configured LLM endpoint and return the text response.
    Falls back to a safe error message if the endpoint is unavailable.
    """
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if LLM_KEY:
        headers["Authorization"] = f"Bearer {LLM_KEY}"

    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": build_system_prompt("example_custom_agent", prompt_mode)},
            {"role": "user",   "content": prompt},
        ],
        "temperature": 0,
        "max_tokens": 1024,
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            resp = await client.post(LLM_ENDPOINT, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            choices = data.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "").strip()
            return str(data)
        except httpx.ConnectError:
            return (
                "[CustomAgent] Cannot connect to LLM endpoint. "
                f"Set CUSTOM_AGENT_URL to a running endpoint (currently: {LLM_ENDPOINT})"
            )
        except Exception as exc:
            return f"[CustomAgent] Error: {exc}"
