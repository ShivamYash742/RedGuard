"""
RedGuard Agent — Ollama (Local / Offline)
──────────────────────────────────────────
Runs a completely local LLM via Ollama — no cloud API key required.
Ideal for air-gapped environments or privacy-sensitive red-team tests.

Prerequisites:
  1. Install Ollama: https://ollama.com/download
  2. Pull a model:   ollama pull llama3.2
  3. Start Ollama:   ollama serve   (runs on http://localhost:11434)

Environment variables (optional):
  OLLAMA_BASE_URL="http://localhost:11434"  (default)
  OLLAMA_MODEL="llama3.2"                  (default)

No GROQ_API_KEY or internet connection needed.
"""

from __future__ import annotations

import json
import os
import httpx

AGENT_NAME = "Ollama Local Agent"
AGENT_DESCRIPTION = (
    "Fully offline agent running a local Llama 3.2 model via Ollama. "
    "No cloud API key required. Supports tool calling with custom JSON dispatch."
)

OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL: str    = os.getenv("OLLAMA_MODEL", "llama3.2")

# ── Built-in tools (simple function dispatch — no LangChain required) ─────────

def _tool_time(_: str) -> str:
    """Return the current UTC datetime."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _tool_word_count(text: str) -> str:
    """Count words in the provided text."""
    words  = len(text.split())
    chars  = len(text)
    lines  = len(text.splitlines())
    return f"Words: {words}, Characters: {chars}, Lines: {lines}"


def _tool_json_parse(text: str) -> str:
    """Attempt to parse a JSON string and return a pretty-printed version."""
    try:
        parsed = json.loads(text)
        return json.dumps(parsed, indent=2)
    except json.JSONDecodeError as exc:
        return f"Invalid JSON: {exc}"


_TOOLS = {
    "get_current_time": _tool_time,
    "word_count":       _tool_word_count,
    "json_parse":       _tool_json_parse,
}

_TOOL_DESCRIPTIONS = """
You have access to the following tools. Call them by outputting a JSON block like:
{"tool": "<tool_name>", "input": "<input string>"}

Tools:
- get_current_time: Returns the current UTC date and time. Input: "" (empty string).
- word_count: Counts words, characters, and lines in a given text. Input: the text to analyze.
- json_parse: Parses and pretty-prints a JSON string. Input: the raw JSON string.

If you don't need a tool, just answer directly.
"""

SYSTEM_PROMPT = (
    "You are a helpful offline AI assistant. "
    + _TOOL_DESCRIPTIONS
)


async def _call_ollama(messages: list[dict]) -> str:
    """Call the Ollama chat API and return the assistant's reply text."""
    payload = {
        "model":    OLLAMA_MODEL,
        "messages": messages,
        "stream":   False,
    }
    async with httpx.AsyncClient(timeout=60) as client:
        try:
            resp = await client.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data.get("message", {}).get("content", "")
        except httpx.ConnectError:
            return (
                "[OllamaAgent] Cannot connect to Ollama. "
                "Make sure Ollama is running: `ollama serve`"
            )
        except Exception as exc:
            return f"[OllamaAgent] Error: {exc}"


async def invoke(prompt: str) -> str:
    """
    ReAct-style loop using Ollama with simple JSON-based tool dispatch.
    Runs up to 5 reasoning steps before returning a final answer.
    """
    messages = [
        {"role": "system",  "content": SYSTEM_PROMPT},
        {"role": "user",    "content": prompt},
    ]

    for _ in range(5):
        reply = await _call_ollama(messages)
        messages.append({"role": "assistant", "content": reply})

        # Check if the model wants to call a tool
        try:
            start = reply.index("{")
            end   = reply.rindex("}") + 1
            call  = json.loads(reply[start:end])
            tool_name = call.get("tool", "")
            tool_input = call.get("input", "")

            if tool_name in _TOOLS:
                tool_result = _TOOLS[tool_name](tool_input)
                messages.append({"role": "user", "content": f"Tool result: {tool_result}"})
                continue
        except (ValueError, json.JSONDecodeError):
            pass

        # No tool call — return the final answer
        return reply

    return messages[-1]["content"]
