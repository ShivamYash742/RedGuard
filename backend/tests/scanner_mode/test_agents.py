from types import SimpleNamespace

import pytest

from scanner_mode import scanner
from scanner_mode.agents import _tools
from scanner_mode.agents._prompt_loader import build_system_prompt
from scanner_mode.scanner import session_prompt_mode


def test_file_read_stays_inside_the_sandbox(tmp_path, monkeypatch):
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    (sandbox / "notes.md").write_text("vendor notes")
    (tmp_path / "secret.txt").write_text("host secret")
    (sandbox / "link.txt").symlink_to(tmp_path / "secret.txt")
    monkeypatch.setattr(_tools, "SANDBOX_DIR", sandbox)

    assert _tools.file_read.invoke({"path": "notes.md"}) == "vendor notes"
    for path in ["/etc/passwd", "../secret.txt", "notes.md/../../secret.txt", "link.txt", "~/.ssh/id_rsa"]:
        reply = _tools.file_read.invoke({"path": path})
        assert "host secret" not in reply and reply.startswith("Error"), path


def test_open_proxy_route_is_gone():
    from app import app
    assert "/api/proxy" not in app.openapi()["paths"]


def test_baseline_prompt_does_not_describe_the_attacks():
    baseline = build_system_prompt("nemotron_super_agent").lower()
    hardened = build_system_prompt("nemotron_super_agent", "hardened").lower()
    for phrase in ("ignore previous instructions", "system override", "internal note"):
        assert phrase not in baseline
        assert phrase in hardened


def test_session_prompt_mode(monkeypatch):
    async def invoke_with_mode(prompt, prompt_mode="baseline"): ...
    async def invoke_without_mode(prompt): ...

    monkeypatch.setattr(scanner, "get_agent", lambda agent_id: SimpleNamespace(invoke=invoke_with_mode))
    assert session_prompt_mode("a", "hardened") == "hardened"
    with pytest.raises(ValueError):
        session_prompt_mode("a", "jailbroken")

    # an agent that picks its own prompt is recorded as such, not as "baseline"
    monkeypatch.setattr(scanner, "get_agent", lambda agent_id: SimpleNamespace(invoke=invoke_without_mode))
    assert session_prompt_mode("a", "baseline") == "agent_default"
