"""
RedGuard Agent Loader
──────────────────────
Auto-discovers every *.py file in the agents/ folder (except __init__.py
and files starting with _) and exposes them as selectable scan targets.

Each agent module must define:
  AGENT_NAME        (str)   – display name
  AGENT_DESCRIPTION (str)   – one-line description
  invoke(prompt)    (async) – returns the agent's text response
"""

from __future__ import annotations

import importlib
import importlib.util
import re
import sys
from pathlib import Path
from typing import Any

AGENTS_DIR = Path(__file__).parent / "agents"
DEFAULT_AGENT_ID = "nemotron_3_ultra"

#: Old agent ids that stored sessions still carry -> the agent they now run as.
#: GPT OSS 20B used to live in llama_3_1_8b_agent.py.
AGENT_ALIASES = {"llama_3_1_8b_agent": "gpt_oss_20b_agent"}


def _load_module(agent_id: str):
    """Import an agent module by its stem name (filename without .py)."""
    agent_id = AGENT_ALIASES.get(agent_id, agent_id)
    # agentId arrives in a URL: only a bare module name, never a path or a private module.
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", agent_id) or not (AGENTS_DIR / f"{agent_id}.py").is_file():
        raise KeyError(f"Unknown agent: {agent_id!r}")
    cache_key = f"scanner_mode.agents.{agent_id}"

    # Return cached module if already loaded — prevents re-executing module body
    # which would reset _agent_instance singletons in every agent.
    if cache_key in sys.modules:
        return sys.modules[cache_key]

    spec = importlib.util.spec_from_file_location(
        cache_key,
        AGENTS_DIR / f"{agent_id}.py",
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load agent: {agent_id}")
    mod = importlib.util.module_from_spec(spec)
    # Register in sys.modules BEFORE exec so circular imports resolve correctly,
    # but evict on failure so the next call retries instead of returning a
    # permanently broken/empty module (which caused the
    # "has no attribute 'invoke'" error when ddgs wasn't installed).
    sys.modules[cache_key] = mod
    try:
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
    except Exception:
        sys.modules.pop(cache_key, None)  # evict broken module from cache
        raise
    return mod


def list_agents() -> list[dict[str, str]]:
    """Return metadata for every agent discovered in the agents/ folder."""
    agents = []
    for path in sorted(AGENTS_DIR.glob("*.py")):
        if path.name.startswith("_"):
            continue
        agent_id = path.stem
        try:
            mod = _load_module(agent_id)
            agents.append(
                {
                    "id": agent_id,
                    "name": getattr(mod, "AGENT_NAME", agent_id),
                    "description": getattr(mod, "AGENT_DESCRIPTION", ""),
                    "is_default": agent_id == DEFAULT_AGENT_ID,
                    "models": getattr(mod, "AVAILABLE_MODELS", []),
                }
            )
        except Exception as exc:
            # Don't crash the whole server if one agent is broken
            agents.append(
                {
                    "id": agent_id,
                    "name": agent_id,
                    "description": f"⚠ Failed to load: {exc}",
                    "is_default": agent_id == DEFAULT_AGENT_ID,
                }
            )
    return agents


def get_agent(agent_id: str):
    """Load and return an agent module by ID (old ids resolve through AGENT_ALIASES).
    Raises KeyError for an unknown id and the import error for a broken agent:
    silently running a different agent would put its results under this id."""
    return _load_module(agent_id)
