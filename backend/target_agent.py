"""Target ReAct agent behind Lobster Trap proxy (Phase 1)."""

from __future__ import annotations

import os
import socket
import sys
from pathlib import Path
from typing import Any

import numexpr
from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_groq import ChatGroq
from langgraph.prebuilt import create_react_agent

from schema import generate_session_id


LOBSTERTRAP_HOST = "localhost"
LOBSTERTRAP_PORT = 8080
LOBSTERTRAP_BASE_URL = "http://localhost:8080"
_SEARCH_TOOL = DuckDuckGoSearchRun()


def _check_proxy(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


@tool
def web_search(query: str) -> str:
    """Search the web for information."""
    try:
        return _SEARCH_TOOL.run(query)
    except Exception as exc:  # noqa: BLE001
        return f"Error searching web: {exc}"


@tool
def file_read(path: str) -> str:
    """Read contents of a file."""
    try:
        file_path = Path(path.strip()).expanduser().resolve()
        if not file_path.exists():
            return f"Error: file not found: {file_path}"
        if not file_path.is_file():
            return f"Error: path is not a file: {file_path}"
        return file_path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001
        return f"Error reading file: {exc}"


@tool
def calculator(expression: str) -> str:
    """Evaluate a mathematical expression."""
    try:
        result = numexpr.evaluate(expression.strip())
        return str(result.item() if hasattr(result, "item") else result)
    except Exception as exc:  # noqa: BLE001
        return f"Error evaluating expression: {exc}"


def build_tools() -> list[Any]:
    return [web_search, file_read, calculator]


def _extract_text(result: Any) -> str:
    messages = result.get("messages") if isinstance(result, dict) else None
    if not messages:
        return str(result)
    last = messages[-1]
    content = getattr(last, "content", "")
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
            else:
                parts.append(str(item))
        return "\n".join([p for p in parts if p]).strip()
    return str(content).strip()


def main() -> int:
    load_dotenv()

    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        print("GROQ_API_KEY not set in .env", file=sys.stderr)
        return 1

    if not _check_proxy(LOBSTERTRAP_HOST, LOBSTERTRAP_PORT):
        print("lt proxy not detected on :8080, run ./lt serve first", file=sys.stderr)
        return 1

    session_id = generate_session_id()
    model_name = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

    llm = ChatGroq(
        model=model_name,
        api_key=api_key,
        base_url=LOBSTERTRAP_BASE_URL,
        temperature=0,
    )

    tools = build_tools()
    if not tools:
        print("No tools available, exiting.", file=sys.stderr)
        return 1

    agent = create_react_agent(model=llm, tools=tools)

    print(f"Session: {session_id}")
    print("READY")

    while True:
        try:
            user_input = input("target> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0

        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit"}:
            return 0

        retries = 0
        while retries < 3:
            try:
                response = agent.invoke({"messages": [{"role": "user", "content": user_input}]})
                print(_extract_text(response))
                break
            except Exception as exc:  # noqa: BLE001
                if "Connection refused" in str(exc) or "Max retries exceeded" in str(exc):
                    retries += 1
                    print(
                        f"Proxy connection issue (attempt {retries}/3): {exc}",
                        file=sys.stderr,
                    )
                    if retries >= 3:
                        print("Request failed after 3 retries.", file=sys.stderr)
                        break
                    continue
                print(f"Agent error: {exc}", file=sys.stderr)
                break


if __name__ == "__main__":
    raise SystemExit(main())
