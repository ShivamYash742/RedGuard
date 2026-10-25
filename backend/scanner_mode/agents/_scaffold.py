"""
The one scaffold every Scanner agent runs in.

An agent module supplies only its model (a LangChain chat model from `make_llm`).
The system prompt, the tool set and the step limit come from here, so two agents
differ in the model and nothing else. Do not give an agent its own prompt text,
tools or input filters: that confounds a comparison between models.
"""

from __future__ import annotations

from typing import Any, Callable

from langgraph.prebuilt import create_react_agent

from scanner_mode.agents._prompt_loader import build_system_prompt
from scanner_mode.agents._tools import TOOLS, extract_text

#: LangGraph steps before GraphRecursionError. The scanner scores that error
#: NO_ANSWER (about 7 tool calls).
RECURSION_LIMIT = 15

#: Recorded with each session's model config.
SCAFFOLD = "langgraph-react"

# One compiled agent per (agent, prompt mode).
_compiled: dict[tuple[str, str], Any] = {}


async def run_agent(agent_id: str, make_llm: Callable[[], Any], prompt: str, prompt_mode: str) -> str:
    """Run `prompt` through the shared ReAct loop and return the final text."""
    key = (agent_id, prompt_mode)
    if key not in _compiled:
        _compiled[key] = create_react_agent(
            model=make_llm(),
            tools=TOOLS,
            prompt=build_system_prompt(prompt_mode),
        )
    result = await _compiled[key].ainvoke(
        {"messages": [{"role": "user", "content": prompt}]},
        config={"recursion_limit": RECURSION_LIMIT},
    )
    return extract_text(result)
