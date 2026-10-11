"""
RedGuard Prompt Loader
──────────────────────
Single source of truth for all agent system prompts.

Loads backend/scanner_mode/agents/system_prompts.json. Two modes:

  baseline (default) — one neutral prompt shared by every agent; it names no
                       attacks, so models are compared on equal terms.
  hardened           — the per-agent prompt, assembled from:
  1. Agent-specific header (identity paragraph)
  2. Shared SCENARIO AWARENESS section (all 12 scenarios)
  3. Shared ATTACK FAMILY DEFENCES section (all 8 families)
  4. Agent-specific tool principles
  5. Agent-specific extra addendum (if any)

Usage:
    from scanner_mode.agents._prompt_loader import build_system_prompt
    build_system_prompt("nemotron_3_ultra")              # baseline
    build_system_prompt("nemotron_3_ultra", "hardened")

To update any prompt: edit system_prompts.json and restart the server.
No Python code changes needed.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_PROMPTS_FILE = Path(__file__).parent / "system_prompts.json"
_DIVIDER = "\u2501" * 40   # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PROMPT_MODES = ("baseline", "hardened")


@lru_cache(maxsize=1)
def _load_raw() -> dict[str, Any]:
    """Load and return the raw system_prompts.json data."""
    with open(_PROMPTS_FILE, encoding="utf-8") as f:
        return json.load(f)


def _build_scenario_block(shared: dict[str, Any]) -> str:
    """Render the SCENARIO AWARENESS section from shared data."""
    sa = shared["scenario_awareness"]
    lines: list[str] = [
        _DIVIDER,
        sa["_title"],
        _DIVIDER,
        sa["intro"],
        "",
    ]
    for sc in sa["scenarios"].values():
        lines.append(f"  \u2022 {sc['label']}")
        for rule in sc["rules"]:
            lines.append(f"    \u2014 {rule}")
        lines.append("")
    return "\n".join(lines).rstrip()


def _build_attack_block(shared: dict[str, Any]) -> str:
    """Render the ATTACK FAMILY DEFENCES section from shared data."""
    af = shared["attack_family_defences"]
    lines: list[str] = [
        "",
        _DIVIDER,
        af["_title"],
        _DIVIDER,
        "",
    ]
    for family in af["families"].values():
        lines.append(f"{family['number']}. {family['label']}")
        for rule in family["rules"]:
            lines.append(f"   {rule}")
        lines.append("")
    return "\n".join(lines).rstrip()


def _build_tool_block(principles: list[str]) -> str:
    """Render the TOOL USE PRINCIPLES section."""
    lines: list[str] = [
        "",
        _DIVIDER,
        "TOOL USE PRINCIPLES",
        _DIVIDER,
    ]
    for p in principles:
        lines.append(f"- {p}")
    return "\n".join(lines)


def build_system_prompt(agent_id: str, mode: str = "baseline") -> str:
    """
    Return the system prompt for agent_id in the given mode.

    Raises:
        ValueError: If mode is not one of PROMPT_MODES.
        KeyError: If agent_id is not found in system_prompts.json (hardened mode).
        FileNotFoundError: If system_prompts.json is missing.
    """
    if mode not in PROMPT_MODES:
        raise ValueError(f"Unknown prompt mode {mode!r}; expected one of {PROMPT_MODES}")
    raw = _load_raw()
    if mode == "baseline":
        return raw["baseline"]
    shared = raw["shared"]
    agents = raw["agents"]

    if agent_id not in agents:
        raise KeyError(
            f"Agent '{agent_id}' not found in system_prompts.json. "
            f"Known agents: {sorted(agents)}"
        )

    agent_cfg = agents[agent_id]

    parts: list[str] = []

    # 1. Agent identity header
    parts.append(agent_cfg["header"])

    # 2. Scenario awareness (shared)
    parts.append("\n" + _build_scenario_block(shared))

    # 3. Attack family defences (shared)
    parts.append(_build_attack_block(shared))

    # 4. Tool use principles (per-agent)
    tool_principles = agent_cfg.get("tool_principles", [])
    if tool_principles:
        parts.append(_build_tool_block(tool_principles))

    # 5. Optional per-agent addendum
    extra = agent_cfg.get("extra", "")
    if extra:
        parts.append(f"\n{_DIVIDER}\nNOTE\n{_DIVIDER}\n{extra}")

    return "\n".join(parts)


def list_agents() -> list[str]:
    """Return all agent IDs defined in system_prompts.json."""
    return sorted(_load_raw()["agents"])


if __name__ == "__main__":
    # Quick sanity-check: print assembled prompts for all agents
    for aid in list_agents():
        print(f"\n{'=' * 60}")
        print(f"AGENT: {aid}")
        print("=" * 60)
        print(build_system_prompt(aid, "hardened"))
        print()
