"""
RedGuard Prompt Loader
──────────────────────
Single source of truth for all agent system prompts.

Loads backend/scanner_mode/agents/system_prompts.json. Two modes, each the same
for every agent so that models are compared on equal terms:

  baseline (default) — one neutral prompt; it names no attacks.
  hardened           — the baseline prompt, a security line and six general principles.
                       It names no attack phrase, family or scenario, so it cannot teach the test.

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


def _build_principles_block(principles: list[str]) -> str:
    """Render the numbered SECURITY PRINCIPLES section."""
    lines = ["", _DIVIDER, "SECURITY PRINCIPLES", _DIVIDER]
    lines += [f"{i}. {p}" for i, p in enumerate(principles, 1)]
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
        raw["baseline"],
        shared["security_line"],
        _build_principles_block(shared["principles"]),
    ])


if __name__ == "__main__":
    for mode in PROMPT_MODES:
        print(f"\n{'=' * 60}\n{mode.upper()}\n{'=' * 60}\n{build_system_prompt(mode)}")
