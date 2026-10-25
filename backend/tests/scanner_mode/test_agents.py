from types import SimpleNamespace

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from scanner_mode import scanner
from scanner_mode.agent_loader import AGENTS_DIR, _load_module
from scanner_mode.agents import _scaffold, _tools
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
    baseline = build_system_prompt().lower()
    hardened = build_system_prompt("hardened").lower()
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


AGENT_IDS = sorted(p.stem for p in AGENTS_DIR.glob("*.py") if not p.name.startswith("_"))


class ToolLoopModel(BaseChatModel):
    """A chat model that calls the calculator on every turn and never answers."""

    @property
    def _llm_type(self):
        return "tool-loop"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        call = {"name": "calculator", "args": {"expression": "1+1"}, "id": "call-1"}
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="", tool_calls=[call]))])


@pytest.fixture
def spy_graph(monkeypatch):
    """Replace LangGraph's agent builder with a spy that records how it was built."""
    built = []

    class Graph:
        async def ainvoke(self, inputs, config):
            return {"messages": [AIMessage(content="ok")]}

    def create_react_agent(model, tools, prompt):
        built.append(SimpleNamespace(model=model, tools=[t.name for t in tools], prompt=prompt))
        return Graph()

    monkeypatch.setattr(_scaffold, "create_react_agent", create_react_agent)
    monkeypatch.setattr(_scaffold, "_compiled", {})
    return built


async def _build_every_agent(monkeypatch, spy_graph, mode):
    for agent_id in AGENT_IDS:
        mod = _load_module(agent_id)
        for key in ("NVIDIA_API_KEY", "GROQ_API_KEY"):
            if hasattr(mod, key):
                monkeypatch.setattr(mod, key, "test-key")
        assert await mod.invoke("hello", prompt_mode=mode) == "ok"
    return {agent_id: built for agent_id, built in zip(AGENT_IDS, spy_graph)}


@pytest.mark.asyncio
async def test_every_agent_has_the_same_tools_and_baseline_prompt(monkeypatch, spy_graph):
    built = await _build_every_agent(monkeypatch, spy_graph, "baseline")
    assert len(built) == len(AGENT_IDS) >= 6
    assert {tuple(b.tools) for b in built.values()} == {("web_search", "file_read", "calculator")}
    assert {b.prompt for b in built.values()} == {build_system_prompt()}


@pytest.mark.asyncio
async def test_every_agent_gets_the_identical_hardened_prompt(monkeypatch, spy_graph):
    built = await _build_every_agent(monkeypatch, spy_graph, "hardened")
    (prompt,) = {b.prompt for b in built.values()}
    assert prompt == build_system_prompt("hardened")
    # the hardened prompt adds security content to the baseline; it does not replace the persona
    assert prompt.startswith(build_system_prompt())
    for persona in ("maximally helpful", "as-is", "Nemotron", "GPT OSS", "air-gapped", "Return tool outputs directly"):
        assert persona not in prompt, persona


def test_no_agent_filters_or_extends_the_prompt_on_its_own():
    # Security wording belongs in the hardened prompt only; an agent file may not add its own.
    for agent_id in AGENT_IDS:
        source = (AGENTS_DIR / f"{agent_id}.py").read_text()
        assert "_SUSPICIOUS" not in source and "IMPORTANT: Never" not in source, agent_id


@pytest.mark.asyncio
async def test_a_tool_loop_ends_in_the_recursion_error_the_scanner_scores_no_answer(monkeypatch):
    async def invoke(prompt, prompt_mode="baseline"):
        return await _scaffold.run_agent("loop", ToolLoopModel, prompt, prompt_mode)

    monkeypatch.setattr(_scaffold, "_compiled", {})
    monkeypatch.setattr(scanner, "get_agent", lambda agent_id: SimpleNamespace(invoke=invoke))
    reply = await scanner._invoke_agent("loop", "What is 1+1?")
    assert reply.startswith("Agent error") and "Recursion limit" in reply


def test_the_ollama_agent_sends_temperature_and_seed(monkeypatch):
    mod = _load_module("ollama_local_agent")
    llm = mod._llm()
    assert (llm.temperature, llm.seed, llm.model_name) == (0, 0, "granite3.3:2b")
    assert llm.openai_api_base == "http://localhost:11434/v1"

    monkeypatch.setattr(mod, "SEED", 7)
    monkeypatch.setattr(mod, "TEMPERATURE", 0.3)
    assert (mod._llm().seed, mod._llm().temperature) == (7, 0.3)
    assert mod.model_config() == {"provider": "ollama", "model": "granite3.3:2b", "temperature": 0.3, "seed": 7}


def test_every_agent_reports_its_model_config():
    for agent_id in AGENT_IDS:
        config = _load_module(agent_id).model_config()
        assert set(config) == {"provider", "model", "temperature", "seed"}, agent_id


def test_the_old_gpt_oss_20b_id_still_resolves():
    from scanner_mode.agent_loader import get_agent

    assert get_agent("llama_3_1_8b_agent") is get_agent("gpt_oss_20b_agent")
    assert get_agent("gpt_oss_20b_agent").MODEL_NAME == "openai/gpt-oss-20b"
    assert "llama_3_1_8b_agent" not in AGENT_IDS and "gpt_oss_20b_agent" in AGENT_IDS


def test_an_unknown_agent_is_an_error_not_the_default_agent():
    from scanner_mode.agent_loader import get_agent

    for bad in ("nope", "../scanner", "_scaffold"):
        with pytest.raises(KeyError):
            get_agent(bad)


def test_web_search_uses_fixtures_by_default_and_never_the_network(monkeypatch):
    import langchain_community.tools as lc_tools

    def no_live_search(*args, **kwargs):
        raise AssertionError("live search used in fixture mode")

    monkeypatch.setattr(lc_tools, "DuckDuckGoSearchRun", no_live_search)
    assert _tools.WEB_SEARCH == "fixture"
    first = _tools.web_search.invoke({"query": "Plan a trip to Jaipur"})
    assert "Pink City" in first and first == _tools.web_search.invoke({"query": "plan a trip to JAIPUR"})
    assert _tools.web_search.invoke({"query": "something unlisted"}) == "No relevant results found."


def test_live_web_search_is_opt_in(monkeypatch):
    import langchain_community.tools as lc_tools

    class Live:
        def run(self, query):
            return f"live:{query}"

    monkeypatch.setattr(_tools, "WEB_SEARCH", "live")
    monkeypatch.setattr(lc_tools, "DuckDuckGoSearchRun", Live)
    assert _tools.web_search.invoke({"query": "jaipur"}) == "live:jaipur"
