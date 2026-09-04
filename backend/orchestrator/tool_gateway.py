"""
Per-agent tool authorization gateway.

Checks agent permissions before delegating to CEE tool implementations.
Every call — authorized or denied — results in at least one trace event.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List

from cee.state import CEEState
from cee import tools as cee_tools

EventCallback = Callable[[Dict[str, Any]], None]


class ToolGateway:
    """
    Enforces per-agent tool authorization before calling CEE tools.

    The gateway is the single point of contact between agents and the CEE.
    Agents never interact with CEEState directly.
    """

    _KNOWN_TOOLS = frozenset({"file_read", "web_search", "db_query", "state_write"})

    def __init__(self, state: CEEState, emit_event: EventCallback) -> None:
        self._state = state
        self._emit = emit_event

    def call_tool(
        self,
        agent_id: str,
        tool_name: str,
        arguments: Dict[str, Any],
        agent_allowed_tools: List[str],
        agent_allowed_file_paths: List[str],
        agent_denied_file_paths: List[str],
        agent_allowed_db_keys: List[str],
        agent_denied_db_keys: List[str],
    ) -> str:
        """
        Execute a tool call through the authorization gateway.

        Returns the tool result string.
        Emits at minimum one trace event (tool_denied if not authorized,
        or the full tool_requested / tool_authorized / tool_executed sequence).
        """

        # 1. Agent-level tool allowlist check
        if tool_name not in agent_allowed_tools:
            self._emit(
                {
                    "agent_id": agent_id,
                    "event_type": "tool_denied",
                    "tool": tool_name,
                    "arguments": arguments,
                    "authorized": False,
                    "risk": "high",
                    "content_tag": "system",
                    "metadata": {"reason": "tool_not_in_agent_allowlist"},
                }
            )
            return (
                f"Tool '{tool_name}' is not in the authorized tool list for agent {agent_id}."
            )

        # 2. Known tool dispatch
        if tool_name == "file_read":
            return cee_tools.cee_file_read(
                state=self._state,
                agent_id=agent_id,
                path=arguments.get("path", ""),
                allowed_paths=agent_allowed_file_paths,
                denied_paths=agent_denied_file_paths,
                emit_event=self._emit,
            )

        if tool_name == "web_search":
            return cee_tools.cee_web_search(
                state=self._state,
                agent_id=agent_id,
                query=arguments.get("query", ""),
                emit_event=self._emit,
            )

        if tool_name == "db_query":
            return cee_tools.cee_db_query(
                state=self._state,
                agent_id=agent_id,
                key=arguments.get("key", ""),
                allowed_keys=agent_allowed_db_keys,
                denied_keys=agent_denied_db_keys,
                emit_event=self._emit,
            )

        if tool_name == "state_write":
            return cee_tools.cee_state_write(
                state=self._state,
                agent_id=agent_id,
                key=arguments.get("key", ""),
                value=arguments.get("value", ""),
                emit_event=self._emit,
            )

        # 3. Unrecognized tool (defense-in-depth)
        self._emit(
            {
                "agent_id": agent_id,
                "event_type": "tool_denied",
                "tool": tool_name,
                "arguments": arguments,
                "authorized": False,
                "risk": "medium",
                "content_tag": "system",
                "metadata": {"reason": "unknown_tool"},
            }
        )
        return f"Unknown tool: '{tool_name}'."
