"""
RedGuard Example — Bring Your Own Agent
────────────────────────────────────────
Copy this file, rename it (e.g. my_company_agent.py), drop it into this
folder, and it will appear automatically in the UI agent selector.

Required:
  AGENT_NAME        – display name shown in the UI
  AGENT_DESCRIPTION – one-line description shown in the UI
  invoke(prompt)    – async function that receives a prompt string and
                      returns the agent's response as a plain string

That's all you need. The RedGuard inspector runs before invoke() is called,
so you can focus on your agent logic without worrying about security.
"""

from __future__ import annotations

import os

# ── Metadata ─────────────────────────────────────────────────────────────────
AGENT_NAME = "Example Custom Agent"
AGENT_DESCRIPTION = (
    "A minimal stub agent. Replace the invoke() body with your own logic."
)

# ── Standard interface ────────────────────────────────────────────────────────
async def invoke(prompt: str) -> str:
    """
    Replace this with your actual agent call.

    Examples:
      - Call OpenAI / Anthropic / Cohere APIs
      - Invoke a LangChain chain or LangGraph agent
      - Hit an internal service endpoint
      - Call a locally running Ollama model

    Just return the agent's final text response as a string.
    """
    # ──────────────────────────────────────────────────────────────────────────
    # YOUR AGENT CODE GOES HERE
    # ──────────────────────────────────────────────────────────────────────────
    return f"[ExampleAgent] received prompt ({len(prompt)} chars) — replace this stub with your agent."
