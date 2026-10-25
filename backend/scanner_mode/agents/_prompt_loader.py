"""
RedGuard Prompt Loader
──────────────────────
Single source of truth for all agent system prompts.

Loads backend/scanner_mode/agents/system_prompts.json. Two modes, each the same
for every agent so that models are compared on equal terms:

  baseline (default) — one neutral prompt; it names no attacks.
  hardened           — assembled from:
  1. Header (the baseline sentence plus a security line)
  2. SCENARIO AWARENESS section (all 12 scenarios)
  3. ATTACK FAMILY DEFENCES section (all 8 families)
  4. TOOL USE PRINCIPLES

Usage:
    from scanner_mode.agents._prompt_loader import build_system_prompt
    build_system_prompt()              # baseline
    build_system_prompt("hardened")

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


def build_system_prompt(mode: str = "baseline") -> str:
    """
    Return the system prompt for a mode. It is the same for every agent: a
    prompt that differed by agent would confound the comparison between models.

    Raises:
        ValueError: If mode is not one of PROMPT_MODES.
    """
    if mode not in PROMPT_MODES:
        raise ValueError(f"Unknown prompt mode {mode!r}; expected one of {PROMPT_MODES}")
    raw = _load_raw()
    if mode == "baseline":
        return raw["baseline"]
    shared = raw["shared"]
    return "\n".join([
        shared["header"],
        "\n" + _build_scenario_block(shared),
        _build_attack_block(shared),
        _build_tool_block(shared["tool_principles"]),
    ])


if __name__ == "__main__":
    for mode in PROMPT_MODES:
        print(f"\n{'=' * 60}\n{mode.upper()}\n{'=' * 60}\n{build_system_prompt(mode)}")
