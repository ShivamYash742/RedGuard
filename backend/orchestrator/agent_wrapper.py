"""
LangGraph agent wrapper with CEE tool interception and event emission.

Creates LangGraph ReAct agents whose tool calls are routed through the
ToolGateway (which serves results from the CEEState) and whose every
action emits a TraceEvent via the EventCollector.

This is the boundary between the LangGraph execution model and the
RedGuard observation/evaluation infrastructure.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from langchain_core.tools import tool as langchain_tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from orchestrator.tool_gateway import ToolGateway
from orchestrator.topology import AgentConfig
from tracing.collector import EventCollector

EventCallback = Callable[[Dict[str, Any]], None]


@dataclass
class WrappedAgent:
    """An agent backed by CEE tools and connected to event tracing."""

    agent_id: str
    role: str
    config: AgentConfig
    _agent_instance: Any  # LangGraph compiled graph

    async def invoke(self, prompt: str) -> str:
        """Send a prompt to the agent and return its final text response."""
        result = await self._agent_instance.ainvoke(
            {"messages": [{"role": "user", "content": prompt}]},
            config={"recursion_limit": 12},
        )
        return _extract_text(result)


def _extract_text(result: Any) -> str:
    """Extract the final assistant text from a LangGraph ainvoke result."""
    messages = result.get("messages") if isinstance(result, dict) else None
    if not messages:
        return str(result)
    last = messages[-1]
    content = getattr(last, "content", "")
    if isinstance(content, list):
        return "\n".join(
            str(item.get("text", item)) if isinstance(item, dict) else str(item)
            for item in content
        ).strip()
    return str(content).strip()


def create_wrapped_agent(
    config: AgentConfig,
    model_id: str,
    api_key: str,
    api_base: str,
    gateway: ToolGateway,
    emit_event: EventCallback,
    temperature: float = 0.0,
    mock_mode: bool = False,
) -> WrappedAgent:
    """
    Build a WrappedAgent with CEE-backed tools.

    Parameters
    ----------
    config       : AgentConfig defining this agent's role, tools, and permissions
    model_id     : LLM model identifier (e.g. "gpt-4o-mini")
    api_key      : OpenAI-compatible API key
    api_base     : OpenAI-compatible API base URL
    gateway      : ToolGateway instance backed by the experiment's CEEState
    emit_event   : EventCallback for the run's EventCollector
    temperature  : LLM temperature (use 0 for determinism)
    mock_mode    : If True, creates a stub agent that returns canned responses
                   without calling external APIs (for testing).
    """
    agent_id = config.agent_id

    # ── CEE-backed tool closures ───────────────────────────────────────────────
    # Each closure captures agent_id and gateway, routing calls through
    # the authorization layer and into the CEEState.

    @langchain_tool
    def file_read(path: str) -> str:
        """Read a file from the research environment by its path."""
        return gateway.call_tool(
            agent_id=agent_id,
            tool_name="file_read",
            arguments={"path": path},
            agent_allowed_tools=config.allowed_tools,
            agent_allowed_file_paths=config.allowed_file_paths,
            agent_denied_file_paths=config.denied_file_paths,
            agent_allowed_db_keys=config.allowed_db_keys,
            agent_denied_db_keys=config.denied_db_keys,
        )

    @langchain_tool
    def web_search(query: str) -> str:
        """Search the web for information relevant to the research task."""
        return gateway.call_tool(
            agent_id=agent_id,
            tool_name="web_search",
            arguments={"query": query},
            agent_allowed_tools=config.allowed_tools,
            agent_allowed_file_paths=config.allowed_file_paths,
            agent_denied_file_paths=config.denied_file_paths,
            agent_allowed_db_keys=config.allowed_db_keys,
            agent_denied_db_keys=config.denied_db_keys,
        )

    @langchain_tool
    def db_query(key: str) -> str:
        """Query the research database for a record by its key."""
        return gateway.call_tool(
            agent_id=agent_id,
            tool_name="db_query",
            arguments={"key": key},
            agent_allowed_tools=config.allowed_tools,
            agent_allowed_file_paths=config.allowed_file_paths,
            agent_denied_file_paths=config.denied_file_paths,
            agent_allowed_db_keys=config.allowed_db_keys,
            agent_denied_db_keys=config.denied_db_keys,
        )

    @langchain_tool
    def state_write(key: str, value: str) -> str:
        """Write a value to the shared research state under a given key."""
        return gateway.call_tool(
            agent_id=agent_id,
            tool_name="state_write",
            arguments={"key": key, "value": value},
            agent_allowed_tools=config.allowed_tools,
            agent_allowed_file_paths=config.allowed_file_paths,
            agent_denied_file_paths=config.denied_file_paths,
            agent_allowed_db_keys=config.allowed_db_keys,
            agent_denied_db_keys=config.denied_db_keys,
        )

    # Build tool list from agent's allowlist
    tool_map = {
        "file_read": file_read,
        "web_search": web_search,
        "db_query": db_query,
        "state_write": state_write,
    }
    agent_tools = [tool_map[t] for t in config.allowed_tools if t in tool_map]

    # ── Agent construction ────────────────────────────────────────────────────

    if mock_mode:
        # Stub that returns a predictable response for tests (no LLM call)
        agent_instance = _MockAgentGraph(agent_id=agent_id, tools=agent_tools)
    else:
        llm = ChatOpenAI(
            model=model_id,
            openai_api_key=api_key,
            base_url=api_base,
            temperature=temperature,
            max_retries=1,
            timeout=60.0,
        )
        agent_instance = create_react_agent(
            model=llm,
            tools=agent_tools,
            prompt=config.system_prompt,
        )

    emit_event(
        {
            "agent_id": agent_id,
            "event_type": "agent_created",
            "content_tag": "system",
            "metadata": {
                "role": config.role,
                "model": model_id if not mock_mode else "mock",
                "tools": config.allowed_tools,
                "mock_mode": mock_mode,
            },
        }
    )

    return WrappedAgent(
        agent_id=agent_id,
        role=config.role,
        config=config,
        _agent_instance=agent_instance,
    )


class _MockAgentGraph:
    """
    Stub agent graph for unit/integration tests.

    Calls tools with representative arguments so that tool events are still
    emitted, but does not make external LLM API calls.
    """

    def __init__(self, agent_id: str, tools: list) -> None:
        self._agent_id = agent_id
        self._tools = tools

    async def ainvoke(self, inputs: Dict[str, Any], config: Dict = None) -> Dict[str, Any]:
        from langchain_core.messages import AIMessage

        prompt = ""
        for msg in inputs.get("messages", []):
            if isinstance(msg, dict):
                prompt = msg.get("content", "")

        # Invoke first available tool with a harmless argument to produce events
        for tool_fn in self._tools:
            try:
                if tool_fn.name == "web_search":
                    tool_fn.invoke({"query": "research query"})
                elif tool_fn.name == "file_read":
                    tool_fn.invoke({"path": "data/report.txt"})
                elif tool_fn.name == "db_query":
                    tool_fn.invoke({"key": "config:pipeline"})
                break
            except Exception:
                pass

        response = (
            f"[MOCK {self._agent_id}] Received task. "
            "Conducted research, validated findings, and produced summary. "
            "No anomalous instructions detected."
        )
        return {"messages": [AIMessage(content=response)]}
