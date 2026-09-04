"""
CEE tool implementations.

These functions intercept agent tool calls and serve results from the in-memory
CEEState instead of real filesystems, the web, or real databases.

No real I/O is performed. No subprocess. No pathlib reads from the host.
Every call emits observable trace events via the EventCallback.
"""
from __future__ import annotations

import json
from typing import Any, Callable, Dict, List

from .state import CEEState

# Callback type: receives an event dict and records it in the collector
EventCallback = Callable[[Dict[str, Any]], None]


def cee_file_read(
    state: CEEState,
    agent_id: str,
    path: str,
    allowed_paths: List[str],
    denied_paths: List[str],
    emit_event: EventCallback,
) -> str:
    """
    Read a file from the CEE mock filesystem.

    Authorization logic:
    - If path starts with any denied_path prefix → DENY
    - If allowed_paths is non-empty and path does not start with any → DENY
    - Otherwise → ALLOW

    Emits: tool_requested, (tool_authorized | tool_denied), tool_executed
    Returns: file content string or denial/not-found message.
    """
    # 1. Emit request
    emit_event(
        {
            "agent_id": agent_id,
            "event_type": "tool_requested",
            "tool": "file_read",
            "arguments": {"path": path},
            "content_tag": "external_content",
        }
    )

    # 2. Authorization check
    is_denied = any(path.startswith(dp) for dp in denied_paths)
    is_allowed = not allowed_paths or any(path.startswith(ap) for ap in allowed_paths)

    if is_denied or not is_allowed:
        emit_event(
            {
                "agent_id": agent_id,
                "event_type": "tool_denied",
                "tool": "file_read",
                "arguments": {"path": path},
                "authorized": False,
                "risk": "high",
                "content_tag": "system",
            }
        )
        return f"Access denied: '{path}' is not accessible to agent {agent_id}."

    # 3. Authorized
    emit_event(
        {
            "agent_id": agent_id,
            "event_type": "tool_authorized",
            "tool": "file_read",
            "arguments": {"path": path},
            "authorized": True,
            "content_tag": "system",
        }
    )

    # 4. Read from CEE state
    content = state.filesystem.get(path)
    if content is None:
        result = f"File not found in CEE: {path}"
        risk = "none"
    else:
        result = content
        risk = "none"

    emit_event(
        {
            "agent_id": agent_id,
            "event_type": "tool_executed",
            "tool": "file_read",
            "arguments": {"path": path},
            "result": result[:500],
            "authorized": True,
            "risk": risk,
            "content_tag": "external_content",
        }
    )

    return result


def cee_web_search(
    state: CEEState,
    agent_id: str,
    query: str,
    emit_event: EventCallback,
) -> str:
    """
    Search CEE mock web results.

    Matching: case-insensitive substring match between query and result keys.
    Returns up to 5 matched results joined by separator.

    Emits: tool_requested, tool_authorized, tool_executed
    """
    emit_event(
        {
            "agent_id": agent_id,
            "event_type": "tool_requested",
            "tool": "web_search",
            "arguments": {"query": query},
            "content_tag": "external_content",
        }
    )

    emit_event(
        {
            "agent_id": agent_id,
            "event_type": "tool_authorized",
            "tool": "web_search",
            "arguments": {"query": query},
            "authorized": True,
            "content_tag": "system",
        }
    )

    # Keyword matching against CEE web_results
    results: List[str] = []
    query_lower = query.lower()
    for keyword, entries in state.web_results.items():
        if keyword.lower() in query_lower or query_lower in keyword.lower():
            results.extend(entries)

    if not results:
        result_text = "No results found."
    else:
        result_text = "\n\n---\n\n".join(results[:5])

    emit_event(
        {
            "agent_id": agent_id,
            "event_type": "tool_executed",
            "tool": "web_search",
            "arguments": {"query": query},
            "result": result_text[:500],
            "authorized": True,
            "risk": "none",
            "content_tag": "external_content",
        }
    )

    return result_text


def cee_db_query(
    state: CEEState,
    agent_id: str,
    key: str,
    allowed_keys: List[str],
    denied_keys: List[str],
    emit_event: EventCallback,
) -> str:
    """
    Query the CEE mock key-value database.

    Emits: tool_requested, (tool_authorized | tool_denied), tool_executed
    """
    emit_event(
        {
            "agent_id": agent_id,
            "event_type": "tool_requested",
            "tool": "db_query",
            "arguments": {"key": key},
            "content_tag": "external_content",
        }
    )

    is_denied = any(key.startswith(dk) for dk in denied_keys)
    is_allowed = not allowed_keys or any(key.startswith(ak) for ak in allowed_keys)

    if is_denied or not is_allowed:
        emit_event(
            {
                "agent_id": agent_id,
                "event_type": "tool_denied",
                "tool": "db_query",
                "arguments": {"key": key},
                "authorized": False,
                "risk": "high",
                "content_tag": "system",
            }
        )
        return f"Access denied: key '{key}' is not accessible to agent {agent_id}."

    emit_event(
        {
            "agent_id": agent_id,
            "event_type": "tool_authorized",
            "tool": "db_query",
            "arguments": {"key": key},
            "authorized": True,
            "content_tag": "system",
        }
    )

    value = state.database.get(key)
    if value is None:
        result = f"No record found for key: {key}"
    else:
        result = json.dumps(value) if not isinstance(value, str) else value

    emit_event(
        {
            "agent_id": agent_id,
            "event_type": "tool_executed",
            "tool": "db_query",
            "arguments": {"key": key},
            "result": result[:500],
            "authorized": True,
            "risk": "none",
            "content_tag": "external_content",
        }
    )

    return result


def cee_state_write(
    state: CEEState,
    agent_id: str,
    key: str,
    value: Any,
    emit_event: EventCallback,
) -> str:
    """
    Write a value to the shared CEE key-value store.

    Always authorized (shared state for state-poisoning experiments).
    Always observable: emits a state_write event.
    """
    old_value = state.database.get(key)

    emit_event(
        {
            "agent_id": agent_id,
            "event_type": "state_write",
            "tool": "state_write",
            "arguments": {"key": key, "value": str(value)[:200]},
            "result": f"old_value={str(old_value)[:100]}",
            "authorized": True,
            "risk": "low",
            "content_tag": "derived",
        }
    )

    state.database[key] = value
    return f"Stored key='{key}' in shared CEE state."
