"""Tests for core/lab_mode/model_client.py — action parsing, the repair retry, and
the HTTP call itself against `httpx.MockTransport` (§15: "mocked httpx: valid
action, malformed JSON -> action_parse_failed, repair retry").

Nothing here touches the network.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import httpx
import pytest

from core.lab_mode.model_client import (
    ACTION_KINDS,
    ActionParseError,
    ActionAttempt,
    ModelClient,
    ModelConfig,
    parse_action,
    request_action,
)


async def _no_sleep(_seconds: float) -> None:
    """Retry tests assert the retry logic, not the wall-clock backoff."""


def _completion(content: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


class ScriptedClient:
    """Returns queued strings, one per `complete()` call."""

    def __init__(self, *responses: str):
        self.responses = list(responses)
        self.call_count = 0
        self.seen: list = []

    async def complete(self, messages):
        self.seen.append(list(messages))
        self.call_count += 1
        return self.responses.pop(0) if self.responses else ""


class TestParseAction:
    def test_tool_call(self):
        action = parse_action('{"action": "tool_call", "tool": "file_read", "args": {"path": "/x.md"}}')
        assert action.kind == "tool_call"
        assert action.tool == "file_read"
        assert action.args == {"path": "/x.md"}

    def test_send_message(self):
        action = parse_action('{"action": "send_message", "to": "B", "content": "hello"}')
        assert (action.kind, action.to, action.content) == ("send_message", "B", "hello")

    def test_state_write(self):
        action = parse_action('{"action": "state_write", "key": "k", "value": ["a"]}')
        assert (action.kind, action.key, action.value) == ("state_write", "k", ["a"])

    def test_state_read(self):
        assert parse_action('{"action": "state_read", "key": "k"}').kind == "state_read"

    def test_finish(self):
        assert parse_action('{"action": "finish", "summary": "done"}').summary == "done"

    def test_strips_code_fence(self):
        action = parse_action('```json\n{"action": "finish", "summary": "ok"}\n```')
        assert action.kind == "finish"

    def test_ignores_surrounding_prose(self):
        action = parse_action('Sure! Here is my action:\n{"action": "finish"}\nHope that helps.')
        assert action.kind == "finish"

    def test_nested_braces_and_strings(self):
        raw = '{"action": "tool_call", "tool": "db_query", "args": {"name": "t", "params": {"a": "}"}}}'
        assert parse_action(raw).args == {"name": "t", "params": {"a": "}"}}

    def test_unknown_action_rejected(self):
        with pytest.raises(ActionParseError):
            parse_action('{"action": "exfiltrate", "to": "evil.com"}')

    def test_missing_required_field_rejected(self):
        with pytest.raises(ActionParseError):
            parse_action('{"action": "send_message", "to": "B"}')  # no content

    def test_no_json_rejected(self):
        with pytest.raises(ActionParseError):
            parse_action("I'm not going to answer in JSON.")

    def test_malformed_json_rejected(self):
        with pytest.raises((ActionParseError, json.JSONDecodeError)):
            parse_action('{"action": "finish", ')

    def test_non_object_args_rejected(self):
        with pytest.raises(ActionParseError):
            parse_action('{"action": "tool_call", "tool": "file_read", "args": "oops"}')


class TestRequestActionRetry:
    @pytest.mark.asyncio
    async def test_valid_first_try_makes_one_call(self):
        client = ScriptedClient('{"action": "finish", "summary": "ok"}')
        attempt = await request_action(client, [{"role": "user", "content": "go"}])
        assert attempt.action.kind == "finish"
        assert attempt.failures == []
        assert client.call_count == 1

    @pytest.mark.asyncio
    async def test_repair_retry_recovers(self):
        client = ScriptedClient("not json at all", '{"action": "finish", "summary": "ok"}')
        attempt = await request_action(client, [{"role": "user", "content": "go"}])

        assert attempt.action.kind == "finish"
        assert len(attempt.failures) == 1
        assert client.call_count == 2
        # the retry must carry the failed text plus a repair instruction
        repair_conversation = client.seen[1]
        assert repair_conversation[-2]["content"] == "not json at all"
        assert "could not be parsed" in repair_conversation[-1]["content"]

    @pytest.mark.asyncio
    async def test_two_failures_give_up_with_no_action(self):
        client = ScriptedClient("nope", "still nope")
        attempt = await request_action(client, [{"role": "user", "content": "go"}])

        assert attempt.action is None
        assert len(attempt.failures) == 2
        assert client.call_count == 2  # retries exactly once, never more

    @pytest.mark.asyncio
    async def test_empty_response_is_not_echoed_back_as_an_assistant_turn(self):
        """Some providers (Groq) reject an assistant message with empty
        content outright with a 400, turning a recoverable parse failure into
        a dead run.
        """
        client = ScriptedClient("", '{"action": "finish", "summary": "ok"}')
        attempt = await request_action(client, [{"role": "user", "content": "go"}])

        assert attempt.action.kind == "finish"
        repair_conversation = client.seen[1]
        assert all(m["content"].strip() for m in repair_conversation)
        assert not any(m["role"] == "assistant" for m in repair_conversation)

    @pytest.mark.asyncio
    async def test_failures_carry_reasons(self):
        client = ScriptedClient('{"action": "teleport"}', '{"action": "teleport"}')
        attempt = await request_action(client, [])
        assert all("unknown action" in reason for _, reason in attempt.failures)


class TestModelClientHTTP:
    @pytest.mark.asyncio
    async def test_posts_openai_shape_and_returns_content(self):
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["url"] = str(request.url)
            captured["headers"] = request.headers
            captured["payload"] = json.loads(request.content)
            return _completion('{"action": "finish"}')

        config = ModelConfig(model="test-model", base_url="http://example.invalid/v1", api_key="secret")
        client = ModelClient(config, transport=httpx.MockTransport(handler))

        text = await client.complete([{"role": "user", "content": "hi"}])

        assert text == '{"action": "finish"}'
        assert captured["url"] == "http://example.invalid/v1/chat/completions"
        assert captured["headers"]["authorization"] == "Bearer secret"
        assert captured["payload"]["model"] == "test-model"
        assert captured["payload"]["temperature"] == 0.0
        assert captured["payload"]["messages"] == [{"role": "user", "content": "hi"}]
        assert client.call_count == 1

    @pytest.mark.asyncio
    async def test_no_auth_header_without_key(self):
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["headers"] = request.headers
            return _completion("{}")

        client = ModelClient(
            ModelConfig(model="m", base_url="http://example.invalid/v1"),
            transport=httpx.MockTransport(handler),
        )
        await client.complete([])
        assert "authorization" not in captured["headers"]

    @pytest.mark.asyncio
    async def test_seed_included_only_when_set(self):
        payloads = []

        def handler(request: httpx.Request) -> httpx.Response:
            payloads.append(json.loads(request.content))
            return _completion("{}")

        transport = httpx.MockTransport(handler)
        await ModelClient(ModelConfig(model="m", base_url="http://x.invalid/v1"), transport=transport).complete([])
        await ModelClient(ModelConfig(model="m", base_url="http://x.invalid/v1", seed=7), transport=transport).complete([])

        assert "seed" not in payloads[0]
        assert payloads[1]["seed"] == 7

    @pytest.mark.asyncio
    async def test_falls_back_to_reasoning_when_content_is_empty(self):
        """Reasoning models (gpt-oss, nemotron) return an empty `content` and
        put the answer — action JSON included — in `reasoning`. Reading only
        `content` would score them as 100% parse failures.
        """
        transport = httpx.MockTransport(lambda request: httpx.Response(200, json={
            "choices": [{"message": {
                "content": "",
                "reasoning": 'Thinking... {"action": "finish", "summary": "ok"}',
            }}]
        }))
        client = ModelClient(ModelConfig(model="m", base_url="http://x.invalid/v1"), transport=transport)

        text = await client.complete([])
        assert parse_action(text).kind == "finish"

    @pytest.mark.asyncio
    async def test_content_wins_over_reasoning_when_both_present(self):
        transport = httpx.MockTransport(lambda request: httpx.Response(200, json={
            "choices": [{"message": {"content": "the answer", "reasoning": "the thinking"}}]
        }))
        client = ModelClient(ModelConfig(model="m", base_url="http://x.invalid/v1"), transport=transport)
        assert await client.complete([]) == "the answer"

    @pytest.mark.asyncio
    async def test_empty_choices_returns_empty_string(self):
        transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"choices": []}))
        client = ModelClient(ModelConfig(model="m", base_url="http://x.invalid/v1"), transport=transport)
        assert await client.complete([]) == ""

    @pytest.mark.asyncio
    async def test_http_error_propagates(self):
        """A 500 is retried first, so retries are disabled here to assert the
        giving-up path rather than sit through the backoff."""
        transport = httpx.MockTransport(lambda request: httpx.Response(500, json={"error": "boom"}))
        client = ModelClient(
            ModelConfig(model="m", base_url="http://x.invalid/v1"),
            transport=transport, max_rate_limit_retries=0,
        )
        with pytest.raises(httpx.HTTPStatusError):
            await client.complete([])

    @pytest.mark.asyncio
    async def test_transient_5xx_is_retried_then_succeeds(self):
        """A sweep is thousands of calls over hours, and hosted inference
        returns "503 Service temporarily overloaded" routinely. Without this
        one blip invalidates a run and silently shrinks a denominator — §21.8
        contamination arriving over the network instead of via the agents.
        """
        attempts = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            attempts["n"] += 1
            if attempts["n"] < 3:
                return httpx.Response(503, json={"error": {"message": "Service temporarily overloaded"}})
            return _completion('{"action": "finish", "summary": "ok"}')

        client = ModelClient(
            ModelConfig(model="m", base_url="http://x.invalid/v1"),
            transport=httpx.MockTransport(handler),
        )
        with patch("core.lab_mode.model_client.asyncio.sleep", new=_no_sleep):
            text = await client.complete([])

        assert parse_action(text).kind == "finish"
        assert attempts["n"] == 3
        assert client.transient_retries == 2

    @pytest.mark.asyncio
    @pytest.mark.parametrize("status", [408, 500, 502, 503, 504, 529])
    async def test_every_transient_status_is_retried(self, status):
        attempts = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            attempts["n"] += 1
            if attempts["n"] == 1:
                return httpx.Response(status, json={"error": "transient"})
            return _completion("{}")

        client = ModelClient(
            ModelConfig(model="m", base_url="http://x.invalid/v1"),
            transport=httpx.MockTransport(handler),
        )
        with patch("core.lab_mode.model_client.asyncio.sleep", new=_no_sleep):
            await client.complete([])
        assert attempts["n"] == 2

    @pytest.mark.asyncio
    async def test_client_error_is_not_retried(self):
        """A 4xx other than 408/429 means the request is wrong. Retrying it
        just burns the rate limit and delays the real error."""
        attempts = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            attempts["n"] += 1
            return httpx.Response(401, json={"error": {"message": "invalid api key"}})

        client = ModelClient(
            ModelConfig(model="m", base_url="http://x.invalid/v1"),
            transport=httpx.MockTransport(handler),
        )
        with pytest.raises(httpx.HTTPStatusError, match="invalid api key"):
            await client.complete([])
        assert attempts["n"] == 1

    @pytest.mark.asyncio
    async def test_transient_retries_give_up_and_raise(self):
        transport = httpx.MockTransport(lambda request: httpx.Response(503, text="overloaded"))
        client = ModelClient(
            ModelConfig(model="m", base_url="http://x.invalid/v1"),
            transport=transport, max_rate_limit_retries=2,
        )
        with patch("core.lab_mode.model_client.asyncio.sleep", new=_no_sleep):
            with pytest.raises(httpx.HTTPStatusError, match="503"):
                await client.complete([])
        assert client.transient_retries == 2

    @pytest.mark.asyncio
    async def test_falls_back_to_reasoning_content_for_nvidia(self):
        """NVIDIA's nemotron names the field `reasoning_content`; gpt-oss
        names it `reasoning`. Both must be read, or one provider's models
        score as 100% parse failures."""
        transport = httpx.MockTransport(lambda request: httpx.Response(200, json={
            "choices": [{"message": {
                "content": "",
                "reasoning_content": '{"action": "finish", "summary": "ok"}',
            }}]
        }))
        client = ModelClient(ModelConfig(model="m", base_url="http://x.invalid/v1"), transport=transport)
        assert parse_action(await client.complete([])).kind == "finish"

    @pytest.mark.asyncio
    async def test_content_wins_over_reasoning_content(self):
        """A model that answers in `content` must never have its private
        reasoning mistaken for the action."""
        transport = httpx.MockTransport(lambda request: httpx.Response(200, json={
            "choices": [{"message": {
                "content": '{"action": "finish", "summary": "real"}',
                "reasoning_content": '{"action": "tool_call", "tool": "db_query", "args": {}}',
            }}]
        }))
        client = ModelClient(ModelConfig(model="m", base_url="http://x.invalid/v1"), transport=transport)
        assert parse_action(await client.complete([])).summary == "real"

    @pytest.mark.asyncio
    async def test_error_carries_the_provider_message(self):
        transport = httpx.MockTransport(
            lambda request: httpx.Response(401, json={"error": {"message": "invalid api key"}})
        )
        client = ModelClient(ModelConfig(model="m", base_url="http://x.invalid/v1"), transport=transport)
        with pytest.raises(httpx.HTTPStatusError, match="invalid api key"):
            await client.complete([])

    @pytest.mark.asyncio
    async def test_tool_use_failed_is_recovered_as_model_output(self):
        """Groq answers 400 `tool_use_failed` when the model emits a *native*
        tool call and no tools were declared. That is the model breaking the
        action protocol, not a transport failure — the rejected text must come
        back so it lands on the parse-failure path instead of killing the run.
        """
        failed = '{"name": "tool.file_read", "arguments": {"path": "/x.md"}}'
        transport = httpx.MockTransport(lambda request: httpx.Response(400, json={
            "error": {
                "message": "Tool choice is none, but model called a tool",
                "code": "tool_use_failed",
                "failed_generation": failed,
            }
        }))
        client = ModelClient(ModelConfig(model="m", base_url="http://x.invalid/v1"), transport=transport)

        assert await client.complete([]) == failed

    @pytest.mark.asyncio
    async def test_recovered_tool_use_failure_drives_the_repair_retry(self):
        responses = [
            httpx.Response(400, json={"error": {
                "code": "tool_use_failed",
                "failed_generation": '{"name": "tool.file_read", "arguments": {}}',
            }}),
            _completion('{"action": "finish", "summary": "ok"}'),
        ]
        transport = httpx.MockTransport(lambda request: responses.pop(0))
        client = ModelClient(ModelConfig(model="m", base_url="http://x.invalid/v1"), transport=transport)

        attempt = await request_action(client, [{"role": "user", "content": "go"}])

        assert attempt.action.kind == "finish"
        assert len(attempt.failures) == 1  # counted against the model, not the harness


class TestRateLimitBackoff:
    """A sweep is ~2,500 calls against rate-limited endpoints (§11); without
    backoff it dies part way through.
    """

    @pytest.mark.asyncio
    async def test_retries_429_then_succeeds(self):
        responses = [
            httpx.Response(429, headers={"retry-after": "0"}, json={"error": {"code": "rate_limit_exceeded"}}),
            _completion('{"action": "finish"}'),
        ]
        transport = httpx.MockTransport(lambda request: responses.pop(0))
        client = ModelClient(ModelConfig(model="m", base_url="http://x.invalid/v1"), transport=transport)

        assert await client.complete([]) == '{"action": "finish"}'
        assert client.rate_limit_waits == 1

    @pytest.mark.asyncio
    async def test_gives_up_after_max_retries(self):
        transport = httpx.MockTransport(
            lambda request: httpx.Response(429, headers={"retry-after": "0"}, json={"error": {"message": "slow down"}})
        )
        client = ModelClient(
            ModelConfig(model="m", base_url="http://x.invalid/v1"),
            transport=transport,
            max_rate_limit_retries=2,
        )
        with pytest.raises(httpx.HTTPStatusError, match="slow down"):
            await client.complete([])
        assert client.rate_limit_waits == 2

    def test_retry_delay_prefers_the_header(self):
        from core.lab_mode.model_client import _retry_delay

        response = httpx.Response(429, headers={"retry-after": "2.5"})
        assert _retry_delay(response, attempt=0) == 2.5

    def test_retry_delay_parses_the_providers_suggested_wait(self):
        from core.lab_mode.model_client import _retry_delay

        response = httpx.Response(429, json={"error": {"message": "Please try again in 3.554999999s."}})
        assert _retry_delay(response, attempt=0) == pytest.approx(3.805, abs=0.01)

    def test_retry_delay_falls_back_to_backoff_and_is_capped(self):
        from core.lab_mode.model_client import _retry_delay

        response = httpx.Response(429, json={"error": {"message": "too many requests"}})
        assert _retry_delay(response, attempt=2) == 4.0
        assert _retry_delay(response, attempt=20) == 60.0


class TestModelConfig:
    def test_to_dict_never_leaks_the_api_key(self):
        """This dict goes into evidence bundles and experiment rows."""
        config = ModelConfig(model="m", api_key="super-secret")
        assert "super-secret" not in json.dumps(config.to_dict())
        assert "api_key" not in config.to_dict()

    def test_from_env_rejects_unknown_provider(self):
        with pytest.raises(ValueError):
            ModelConfig.from_env(provider="not-a-provider")

    def test_from_env_ollama_builds_v1_base_url(self, monkeypatch):
        monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
        config = ModelConfig.from_env(provider="ollama", model="llama3.1:latest")
        assert config.base_url == "http://localhost:11434/v1"
        assert config.api_key == ""

    def test_from_env_reads_provider_key(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "gk-test")
        config = ModelConfig.from_env(provider="groq", model="openai/gpt-oss-120b")
        assert config.api_key == "gk-test"
        assert config.base_url == "https://api.groq.com/openai/v1"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))


class TestTokenBudget:
    """Regression for a measurement-validity bug, not a crash.

    At max_tokens=512 nemotron-3-super-120b was cut off mid-reasoning and the
    truncated thinking came back as `content`, which parses as a failure. The
    §21.9 suitability gate then scored a capable model at 16.7% and would
    have reported it unsuitable — the gate was measuring this setting rather
    than the model.
    """

    def test_default_budget_has_room_for_reasoning(self):
        # ~700 tokens of observed reasoning plus the action, with margin.
        assert ModelConfig(model="m", base_url="http://x.invalid/v1").max_tokens >= 2048

    @pytest.mark.asyncio
    async def test_budget_is_sent_to_the_provider(self):
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["payload"] = json.loads(request.content)
            return _completion("{}")

        config = ModelConfig(model="m", base_url="http://x.invalid/v1", max_tokens=1234)
        await ModelClient(config, transport=httpx.MockTransport(handler)).complete([])
        assert captured["payload"]["max_tokens"] == 1234

    @pytest.mark.asyncio
    @pytest.mark.parametrize("provider,json_mode", [("ollama", True), ("nvidia", False), ("groq", False)])
    async def test_json_mode_is_requested_from_ollama_only(self, provider, json_mode):
        """Small local models answer in prose without it; hosted providers
        are left as measured."""
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["payload"] = json.loads(request.content)
            return _completion("{}")

        config = ModelConfig(model="m", provider=provider, base_url="http://x.invalid/v1")
        await ModelClient(config, transport=httpx.MockTransport(handler)).complete([])
        assert ("response_format" in captured["payload"]) is json_mode
        if json_mode:
            # granite3.3:2b put the tool's name in `action` under plain JSON
            # mode; the schema allows only the six action kinds there.
            schema = captured["payload"]["response_format"]["json_schema"]["schema"]
            assert set(schema["properties"]["action"]["enum"]) == set(ACTION_KINDS)
            assert "db_query" in schema["properties"]["tool"]["enum"]

    @pytest.mark.asyncio
    async def test_truncated_reasoning_is_not_silently_accepted_as_an_action(self):
        """A length-truncated response is prose, and prose must register as a
        parse failure rather than be coerced into something."""
        truncated = "We need to continue. We have already done a web_search for the vendor list. Actually"
        transport = httpx.MockTransport(lambda request: httpx.Response(200, json={
            "choices": [{"finish_reason": "length", "message": {"content": truncated}}]
        }))
        client = ModelClient(ModelConfig(model="m", base_url="http://x.invalid/v1"), transport=transport)

        with pytest.raises(ActionParseError):
            parse_action(await client.complete([]))


class TestTransportErrorsAreRetried:
    """Regression: only HTTP status codes were retried. A timeout or dropped
    connection raised straight out of `complete()`, ended the run as a
    harness error, and — through a second bug in the aggregation — was then
    scored as an attack that failed."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("exc", [httpx.ReadTimeout, httpx.ConnectError, httpx.RemoteProtocolError])
    async def test_transport_error_is_retried(self, exc):
        attempts = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            attempts["n"] += 1
            if attempts["n"] == 1:
                raise exc("transient", request=request)
            return _completion('{"action": "finish", "summary": "ok"}')

        client = ModelClient(
            ModelConfig(model="m", base_url="http://x.invalid/v1"),
            transport=httpx.MockTransport(handler),
        )
        with patch("core.lab_mode.model_client.asyncio.sleep", new=_no_sleep):
            text = await client.complete([])

        assert parse_action(text).kind == "finish"
        assert attempts["n"] == 2
        assert client.transient_retries == 1

    @pytest.mark.asyncio
    async def test_persistent_transport_error_still_raises(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("down", request=request)

        client = ModelClient(
            ModelConfig(model="m", base_url="http://x.invalid/v1"),
            transport=httpx.MockTransport(handler),
            max_rate_limit_retries=2,
        )
        with patch("core.lab_mode.model_client.asyncio.sleep", new=_no_sleep):
            with pytest.raises(httpx.ReadTimeout):
                await client.complete([])
        assert client.transient_retries == 2


def test_report_action_parses():
    action = parse_action('{"action": "report", "content": "suspicious"}')
    assert action.kind == "report" and action.content == "suspicious"


def test_report_without_content_is_a_parse_failure():
    with pytest.raises(ValueError):
        parse_action('{"action": "report"}')
