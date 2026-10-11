"""
RedGuard Lab Model Client
==========================

The **only** network-touching module in `core/lab_mode/` (§5.4, §19 of
MULTI_AGENT_LAB_PLAN.md): a thin `httpx` call to an OpenAI-compatible chat
completions endpoint, plus strict parsing of the JSON action the model is
required to emit, plus one repair retry.

No LangChain, no LangGraph. The loop is the harness's (`runner.py`); the
framework adds nothing here and its version churn is a reproducibility
liability. Being a single, small file makes this the natural mock point —
every runner test drives a fake `complete()` and exercises the real parsing.

Providers are one `(base_url, api_key, model)` triple, read from the same env
vars the existing Mode A agents use, so no new configuration surface:

    ollama  OLLAMA_BASE_URL   (default http://localhost:11434)   no key
    nvidia  NVIDIA_API_KEY    https://integrate.api.nvidia.com/v1
    groq    GROQ_API_KEY      https://api.groq.com/openai/v1
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import httpx

from .tools import TOOLS

# ─────────────────────────────────────────────────────────────────────────────
# The action protocol (§5.4)
# ─────────────────────────────────────────────────────────────────────────────

TOOL_CALL = "tool_call"
SEND_MESSAGE = "send_message"
STATE_WRITE = "state_write"
STATE_READ = "state_read"
FINISH = "finish"
#: Flag suspicious content to the harness (not to any agent). See runner.py.
REPORT = "report"

#: Every action kind the harness will execute. `state_read` is not in §5.4's
#: illustrative list but is in §8's event vocabulary and is required by the
#: memory-poisoning cases (RGM-006/007: "write to kv that a later agent
#: reads") — without it those cases cannot be expressed at all.
ACTION_KINDS = frozenset({TOOL_CALL, SEND_MESSAGE, STATE_WRITE, STATE_READ, REPORT, FINISH})

#: Required fields per action kind, validated before the harness executes it.
_REQUIRED_FIELDS: Dict[str, Tuple[str, ...]] = {
    TOOL_CALL: ("tool",),
    SEND_MESSAGE: ("to", "content"),
    STATE_WRITE: ("key", "value"),
    STATE_READ: ("key",),
    REPORT: ("content",),
    FINISH: (),
}

#: The action protocol as a JSON schema, for providers that can constrain
#: decoding to it. Required fields per kind stay in `parse_action`.
ACTION_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": sorted(ACTION_KINDS)},
        "tool": {"type": "string", "enum": sorted(TOOLS)},
        "args": {"type": "object"},
        "to": {"type": "string"},
        "content": {"type": "string"},
        "key": {"type": "string"},
        "value": {"type": "string"},
        "summary": {"type": "string"},
    },
    "required": ["action"],
}


class ActionParseError(ValueError):
    """The model's response was not a usable action."""


@dataclass(frozen=True)
class Action:
    kind: str
    tool: Optional[str] = None
    args: Dict[str, Any] = field(default_factory=dict)
    to: Optional[str] = None
    content: Optional[str] = None
    key: Optional[str] = None
    value: Any = None
    summary: Optional[str] = None
    raw: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.kind,
            "tool": self.tool,
            "args": self.args,
            "to": self.to,
            "content": self.content,
            "key": self.key,
            "value": self.value,
            "summary": self.summary,
        }


_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def _extract_json_object(text: str) -> str:
    """Pull the JSON object out of a model response.

    Strict about the *action* (schema validation below is unforgiving);
    tolerant only about the transport wrapper — code fences and surrounding
    prose. A model that emits a correct action inside a ```json fence has not
    made a research-relevant error, and counting it as a parse failure would
    inflate the very rate §21.9 says biases every downstream metric.
    """
    fenced = _FENCE_RE.search(text)
    candidate = fenced.group(1) if fenced else text

    start = candidate.find("{")
    if start == -1:
        raise ActionParseError("no JSON object in response")

    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(candidate)):
        char = candidate[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return candidate[start:index + 1]
    raise ActionParseError("unbalanced JSON object in response")


def parse_action(text: str) -> Action:
    """Parse and validate one action. Raises `ActionParseError` on anything
    the harness cannot execute — unknown kind, missing required field, or
    malformed JSON.
    """
    payload = json.loads(_extract_json_object(text)) if text else None
    if not isinstance(payload, dict):
        raise ActionParseError("response is not a JSON object")

    kind = payload.get("action")
    if kind not in ACTION_KINDS:
        raise ActionParseError(f"unknown action {kind!r}; expected one of {sorted(ACTION_KINDS)}")

    for required in _REQUIRED_FIELDS[kind]:
        if payload.get(required) is None:
            raise ActionParseError(f"action {kind!r} is missing required field {required!r}")

    args = payload.get("args") or {}
    if not isinstance(args, dict):
        raise ActionParseError("'args' must be an object")

    return Action(
        kind=kind,
        tool=payload.get("tool"),
        args=args,
        to=payload.get("to"),
        content=payload.get("content"),
        key=payload.get("key"),
        value=payload.get("value"),
        summary=payload.get("summary"),
        raw=text,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Client
# ─────────────────────────────────────────────────────────────────────────────

#: Upstream statuses worth retrying. 5xx and 408 are the provider failing or
#: timing out, not the request being wrong — retrying is correct. 4xx other
#: than 408/429 means the request itself is bad, and retrying just wastes the
#: rate limit.
_TRANSIENT_STATUS = frozenset({408, 500, 502, 503, 504, 529})

_PROVIDERS: Dict[str, Tuple[str, str]] = {
    # provider -> (default base url, env var holding the api key)
    "ollama": ("http://localhost:11434/v1", ""),
    "nvidia": ("https://integrate.api.nvidia.com/v1", "NVIDIA_API_KEY"),
    "groq": ("https://api.groq.com/openai/v1", "GROQ_API_KEY"),
}


@dataclass(frozen=True)
class ModelConfig:
    """Captured verbatim into every experiment row and evidence bundle —
    provider, model id and parameters are part of the reproducibility record
    (§17), since temperature 0 reduces but does not remove nondeterminism.
    """

    model: str
    provider: str = "ollama"
    base_url: str = "http://localhost:11434/v1"
    api_key: str = ""
    temperature: float = 0.0
    #: Generous because reasoning models spend most of it thinking before
    #: they emit the action. nemotron-3-super-120b produced ~700 tokens of
    #: reasoning per turn; at the previous 512 it was cut off mid-thought and
    #: the truncated reasoning came back as `content`, which parses as a
    #: failure. That made the §21.9 suitability gate measure *this setting*
    #: rather than the model — it scored a capable model at 16.7% and would
    #: have reported it unsuitable. Measured: 512 -> truncation, 3000 -> clean
    #: JSON with finish_reason=stop on every successful call.
    max_tokens: int = 2048
    timeout: float = 120.0
    seed: Optional[int] = None

    @classmethod
    def from_env(cls, provider: str = "ollama", model: Optional[str] = None, **overrides) -> "ModelConfig":
        if provider not in _PROVIDERS:
            raise ValueError(f"Unknown provider {provider!r}; known: {sorted(_PROVIDERS)}")
        default_base, key_var = _PROVIDERS[provider]
        base_url = default_base
        if provider == "ollama":
            base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/") + "/v1"
        return cls(
            model=model or os.getenv("LAB_MODEL", "granite3.3:2b"),
            provider=provider,
            base_url=base_url,
            api_key=os.getenv(key_var, "") if key_var else "",
            **overrides,
        )

    def to_dict(self) -> Dict[str, Any]:
        """API keys are never included — this goes into evidence bundles."""
        return {
            "model": self.model,
            "provider": self.provider,
            "base_url": self.base_url,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "seed": self.seed,
        }


_RETRY_AFTER_RE = re.compile(r"try again in ([0-9.]+)s")


def _retry_delay(response: httpx.Response, attempt: int) -> float:
    """How long to wait before retrying a rate-limited call.

    Prefers the provider's own instruction (`Retry-After`, else the delay it
    names in the message) over a guess, so a sweep backs off exactly as long
    as it must and no longer — §11 budgets ~2,500 calls per sweep against
    rate-limited endpoints, so this is the difference between a sweep that
    finishes and one that dies half way through.
    """
    header = response.headers.get("retry-after")
    if header:
        try:
            return min(float(header), 60.0)
        except ValueError:
            pass
    match = _RETRY_AFTER_RE.search(response.text or "")
    if match:
        return min(float(match.group(1)) + 0.25, 60.0)
    return min(2.0 ** attempt, 60.0)


def _recover_failed_generation(response: httpx.Response) -> Optional[str]:
    """Some providers reject the model's own output instead of returning it.

    Groq intercepts any JSON that looks like a *native* tool call and answers
    `400 tool_use_failed` when the request declared no tools — which is always,
    since this harness runs its own action protocol. The rejected text comes
    back in `failed_generation`.

    That is a model failing to follow the action protocol, not a harness
    failure, so it belongs on the `action_parse_failed` path (one parse
    failure, one repair retry, and a contribution to the §21.9 suitability
    rate) rather than killing the run. Returns None for genuine transport
    errors — auth, rate limits, unknown model — which must still raise.
    """
    try:
        body = response.json()
    except ValueError:
        return None
    error = body.get("error") if isinstance(body, dict) else None
    if not isinstance(error, dict):  # providers also return a plain string here
        return None
    if error.get("code") != "tool_use_failed":
        return None
    return error.get("failed_generation") or ""


class ModelClient:
    """One `complete()` call = one LLM call. `transport` is injectable so
    tests drive `httpx.MockTransport` instead of the network.
    """

    def __init__(
        self,
        config: ModelConfig,
        transport: Optional[httpx.AsyncBaseTransport] = None,
        # Six, not four, because it was measured: NVIDIA's hosted endpoint
        # returned 503 on 3 of 10 probe calls, in bursts rather than evenly.
        # Four retries leaves roughly one hard failure per 400 calls at that
        # rate; a full sweep is ~2,700.
        max_rate_limit_retries: int = 6,
    ):
        self.config = config
        self._transport = transport
        self.max_rate_limit_retries = max_rate_limit_retries
        self.call_count = 0
        self.rate_limit_waits = 0
        self.transient_retries = 0

    @property
    def endpoint(self) -> str:
        return f"{self.config.base_url.rstrip('/')}/chat/completions"

    async def complete(self, messages: Sequence[Dict[str, str]]) -> str:
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"

        payload: Dict[str, Any] = {
            "model": self.config.model,
            "messages": list(messages),
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        if self.config.seed is not None:
            payload["seed"] = self.config.seed
        # Ollama constrains decoding to the action protocol's shape. Plain
        # JSON mode was not enough: granite3.3:2b then answered with valid
        # JSON naming the tool as the action (`{"action": "db_query", ...}`)
        # on 12 of 14 steps, and the repair retry repeated it. The schema
        # fixes the vocabulary only; which action and tool to use is still
        # the model's choice, and `parse_action` still checks required
        # fields, so a malformed action is a parse failure as before (§21.9).
        if self.config.provider == "ollama":
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "action", "schema": ACTION_SCHEMA},
            }

        self.call_count += 1
        async with httpx.AsyncClient(timeout=self.config.timeout, transport=self._transport) as client:
            for attempt in range(self.max_rate_limit_retries + 1):
                # Timeouts and dropped connections are the same provider
                # failure as a 503, just surfaced by the transport instead of
                # a status code. Unretried, one slow reasoning turn ended the
                # run as a harness error.
                try:
                    response = await client.post(self.endpoint, json=payload, headers=headers)
                except httpx.TransportError:
                    if attempt >= self.max_rate_limit_retries:
                        raise
                    self.transient_retries += 1
                    await asyncio.sleep(min(2.0 ** attempt, 60.0))
                    continue

                if response.status_code == 429 and attempt < self.max_rate_limit_retries:
                    self.rate_limit_waits += 1
                    await asyncio.sleep(_retry_delay(response, attempt))
                    continue

                # Transient upstream failures ("503 Service temporarily
                # overloaded" is routine on hosted inference) must not end a
                # run. A full sweep is thousands of calls over hours, so a
                # single blip would otherwise invalidate a run and silently
                # shrink a denominator — the §21.8 contamination problem
                # arriving through the network instead of through the agents.
                if response.status_code in _TRANSIENT_STATUS and attempt < self.max_rate_limit_retries:
                    self.transient_retries += 1
                    await asyncio.sleep(_retry_delay(response, attempt))
                    continue

                if response.status_code >= 400:
                    recovered = _recover_failed_generation(response)
                    if recovered is not None:
                        return recovered.strip()
                    # A bare "400 Bad Request" is useless when it lands in a
                    # run's `harness_error` days later — carry the provider's
                    # own message.
                    raise httpx.HTTPStatusError(
                        f"{response.status_code} from {self.config.provider}: {response.text[:500]}",
                        request=response.request,
                        response=response,
                    )
                break

            data = response.json()

        choices = data.get("choices") or []
        if not choices:
            return ""
        message = choices[0].get("message") or {}
        # Reasoning-style models (gpt-oss, nemotron) routinely return an empty
        # `content` and put everything, including the action JSON, in a separate
        # `reasoning` field. Reading only `content` would score those models as
        # 100% parse failures when they had in fact answered.
        # Reasoning models differ on the field name: gpt-oss uses `reasoning`,
        # NVIDIA's nemotron uses `reasoning_content`. Both are only consulted
        # when `content` is empty — when a model answers properly in `content`
        # its private reasoning must never be mistaken for the action.
        return (
            (message.get("content") or "")
            or (message.get("reasoning") or "")
            or (message.get("reasoning_content") or "")
        ).strip()


@dataclass(frozen=True)
class ActionAttempt:
    """What one turn's worth of model interaction produced.

    `failures` holds the raw text of every response that would not parse, so
    the runner can emit one `action_parse_failed` per failure and report the
    parse-failure rate per experiment (§21.9 — above ~10% the model is
    unsuitable for the harness rather than merely scoring badly).
    """

    action: Optional[Action]
    failures: List[Tuple[str, str]] = field(default_factory=list)  # (raw_text, reason)
    #: Wall time of each model call in order, so the live view can say how
    #: long an agent was thinking: one per failure, then the action's.
    latencies_ms: List[int] = field(default_factory=list)


REPAIR_INSTRUCTION = (
    "Your previous response could not be parsed: {reason}. "
    "Reply with ONLY a single JSON object and no other text, matching one of the "
    "action forms you were given."
)


async def request_action(client: Any, messages: Sequence[Dict[str, str]]) -> ActionAttempt:
    """One turn: call the model, parse strictly, and on failure retry exactly
    once with a repair instruction appended (§5.4). `client` only needs an
    async `complete(messages) -> str`.
    """
    failures: List[Tuple[str, str]] = []
    latencies: List[int] = []
    conversation = list(messages)

    for attempt in range(2):
        started = time.monotonic()
        text = await client.complete(conversation)
        latencies.append(round((time.monotonic() - started) * 1000))
        try:
            return ActionAttempt(action=parse_action(text), failures=failures, latencies_ms=latencies)
        except (ActionParseError, json.JSONDecodeError) as exc:
            reason = str(exc)
            failures.append((text, reason))
            if attempt == 0:
                # An empty assistant turn is rejected outright by some
                # providers (Groq returns 400), so only echo the bad response
                # back when there is something to echo.
                echo = [{"role": "assistant", "content": text}] if text.strip() else []
                conversation = conversation + echo + [
                    {"role": "user", "content": REPAIR_INSTRUCTION.format(reason=reason)},
                ]

    return ActionAttempt(action=None, failures=failures, latencies_ms=latencies)
