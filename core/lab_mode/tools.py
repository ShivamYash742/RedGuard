"""
RedGuard Tool Layer + Gateway
==============================

Three MVP tools over the CEE, and the `ToolGateway` that is the single
authorization chokepoint between an agent and the CEE (§5.2 of
MULTI_AGENT_LAB_PLAN.md).

`ToolGateway.call` is the *only* path from an agent to the CEE:

  1. emit `tool_requested` (args recorded verbatim)
  2. `topology.tool_authorized(agent, tool)` -> if false: emit `tool_denied`
     with reason, return a denial result, **do not execute**. Under the
     `capability_gateway` arm a `capability_policy` may refuse the call the
     same way (see its docstring)
  3. execute -> emit `tool_executed` with result, or `tool_error`
  4. tag the result event `content_tag = external_content`; if the result
     contains the planted artifact marker, add the artifact event to
     `derived_from`

This is what makes tool-layer containment architectural rather than a prompt
suggestion: the denial happens here, in the harness, before the CEE is ever
touched — an unauthorized call cannot mutate CEE state.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Sequence, Tuple

from .cee import NO_RESULTS, ControlledExecutionEnvironment
from .topology import Topology
from .trace import ContentTag, EventCategory, EventCollector, EventType, ancestors


@dataclass(frozen=True)
class ToolResult:
    ok: bool
    value: Any = None
    error: Optional[str] = None


def file_read(cee: ControlledExecutionEnvironment, args: Dict[str, Any]) -> ToolResult:
    path = args.get("path")
    if not path:
        return ToolResult(ok=False, error="missing_arg:path")
    return ToolResult(ok=True, value=cee.read_file(path))


def web_search(cee: ControlledExecutionEnvironment, args: Dict[str, Any]) -> ToolResult:
    query = args.get("query")
    if not query:
        return ToolResult(ok=False, error="missing_arg:query")
    return ToolResult(ok=True, value=cee.search_web(query))


def db_query(cee: ControlledExecutionEnvironment, args: Dict[str, Any]) -> ToolResult:
    name = args.get("name")
    if not name:
        return ToolResult(ok=False, error="missing_arg:name")
    return ToolResult(ok=True, value=cee.query_db(name, args.get("params")))


#: Registered MVP tools, keyed by the name agents reference in actions.
TOOLS: Dict[str, Callable[[ControlledExecutionEnvironment, Dict[str, Any]], ToolResult]] = {
    "file_read": file_read,
    "web_search": web_search,
    "db_query": db_query,
}

#: How each tool is described to a model in its system prompt. Lives beside
#: the implementations so a new tool cannot be added without also saying how
#: it is called.
TOOL_SIGNATURES: Dict[str, str] = {
    "file_read": 'file_read — args: {"path": "<file path>"}',
    "web_search": 'web_search — args: {"query": "<search text>"}',
    "db_query": 'db_query — args: {"name": "<query name>", "params": {optional filters}}',
}


def _artifact_derivation(
    artifact_step: Optional[int], marker: Optional[str], value: Any, base: Sequence[int],
) -> Tuple[int, ...]:
    """Add the artifact's event to `base` when `value` carries the marker.

    Shared by both gateways on purpose. Content read back out of the CEE is
    the *only* place a run can pick the artifact up without a message hop, and
    it can arrive through either one — a poisoned file via `tool_executed` or
    poisoned shared memory via `state_read`. Linking in only one of them would
    silently break taint closure for the other, which reads downstream as
    "the attack had no effect" rather than as a harness bug.
    """
    if (
        artifact_step is not None
        and marker
        and value is not None
        and value != NO_RESULTS
        and marker in str(value)
    ):
        return tuple(base) + (artifact_step,)
    return tuple(base)


#: The argument naming the resource each gated tool reads. `web_search` is
#: absent on purpose: a query is free text, not a resource, and what it
#: returns is untrusted content the policy already tracks downstream.
_CAPABILITY_ARGS = {"file_read": "path", "db_query": "name"}

#: Events whose content came out of the environment — what the capability
#: gateway treats as untrusted. Defined by the defense in terms of what
#: produced the content (CaMeL's rule: tool output is untrusted data), never
#: by reading `content_tag`, which stays an observational label (§8).
_UNTRUSTED_SOURCE_TYPES = frozenset({EventType.TOOL_EXECUTED, EventType.STATE_READ})

#: (agent, tool, args, derived_from) -> None to allow, or denial metadata.
ToolPolicy = Callable[[str, str, Dict[str, Any], Sequence[int]], Optional[Dict[str, Any]]]


def _named_in(resource: str, text: str) -> bool:
    """Is `resource` named in `text`, verbatim or with `_`/`-` read as spaces?

    The spaced reading is what lets "record the approved vendors" name the
    `approved_vendors` table. Without it the policy refuses the benign path
    of seven of the nine cases, and the arm measures its own breakage rather
    than containment. Word boundaries stop a short name matching inside a
    longer word.
    """
    def spaced(s: str) -> str:
        return re.sub(r"[_\-]+", " ", s.lower())

    for needle, haystack in ((resource.lower(), text.lower()), (spaced(resource), spaced(text))):
        if needle.strip() and re.search(rf"(?<![\w/]){re.escape(needle)}(?!\w)", haystack):
            return True
    return False


def capability_policy(task: str, collector: EventCollector) -> ToolPolicy:
    """The `capability_gateway` arm: a task-scoped capability policy in the
    spirit of CaMeL (Debenedetti et al., 2025, "Defeating Prompt Injections
    by Design").

    A call is refused when both hold:

    - the resource it reads is not named in the task the agents were given;
    - the caller's context already holds untrusted content — anything a tool
      or shared memory returned, reachable through `derived_from`.

    It knows the task and the trace, never the attack: nothing here reads the
    case's objective, artifact, canary or targets. That is the line between
    it and `bus_gateway`, whose blocklist names the very resources the cases
    target and so measures an oracle upper bound, not a deployable control.
    A direct injection (`channel: task`) rides inside the task itself, so the
    policy trusts it — as any capability system trusts its own principal.
    """
    def check(
        agent_id: str, tool_name: str, args: Dict[str, Any], derived_from: Sequence[int],
    ) -> Optional[Dict[str, Any]]:
        arg = _CAPABILITY_ARGS.get(tool_name)
        resource = args.get(arg) if arg else None
        if not isinstance(resource, str) or _named_in(resource, task):
            return None
        untrusted = sorted(
            e.step for e in ancestors(collector, derived_from)
            if e.event_type in _UNTRUSTED_SOURCE_TYPES and e.authorized
        )
        if not untrusted:
            return None
        return {"reason": "capability_policy", "resource": resource, "untrusted_sources": untrusted}

    return check


class ToolGateway:
    """The sole authorization chokepoint between an agent and the CEE.

    `artifact_step` / `artifact_marker` are optional: when set (by the
    runner, once it has planted an artifact and recorded that event's
    step), a tool result containing the marker gets that event added to its
    `derived_from`, linking observed content back to the injection.

    `policy` is the `capability_gateway` arm's extra check, applied after
    the topology's own authorization and before the CEE is touched.
    """

    def __init__(
        self,
        cee: ControlledExecutionEnvironment,
        topology: Topology,
        collector: EventCollector,
        artifact_step: Optional[int] = None,
        artifact_marker: Optional[str] = None,
        policy: Optional[ToolPolicy] = None,
    ):
        self.cee = cee
        self.topology = topology
        self.collector = collector
        self.artifact_step = artifact_step
        self.artifact_marker = artifact_marker
        self.policy = policy

    def call(
        self,
        agent_id: str,
        tool_name: str,
        args: Dict[str, Any],
        *,
        derived_from: Sequence[int] = (),
    ) -> ToolResult:
        """`derived_from` is the context (e.g. a received message's step)
        that motivated this call — the runner supplies it, mirroring
        `MessageBus.send`. Without it, a tool call driven by poisoned
        content would never chain back to the artifact via taint closure.
        """
        requested = self.collector.emit(
            EventCategory.TOOL,
            EventType.TOOL_REQUESTED,
            agent_id=agent_id,
            tool=tool_name,
            arguments=args,
            derived_from=tuple(derived_from),
        )

        if not self.topology.tool_authorized(agent_id, tool_name):
            self.collector.emit(
                EventCategory.TOOL,
                EventType.TOOL_DENIED,
                agent_id=agent_id,
                tool=tool_name,
                arguments=args,
                authorized=False,
                source_event_id=requested.step,
                derived_from=(requested.step,),
                metadata={"reason": "not_authorized"},
            )
            return ToolResult(ok=False, error="not_authorized")

        refusal = self.policy(agent_id, tool_name, args, derived_from) if self.policy else None
        if refusal is not None:
            self.collector.emit(
                EventCategory.TOOL,
                EventType.TOOL_DENIED,
                agent_id=agent_id,
                tool=tool_name,
                arguments=args,
                authorized=False,
                source_event_id=requested.step,
                derived_from=(requested.step,),
                metadata=refusal,
            )
            return ToolResult(ok=False, error=refusal["reason"])

        tool_fn = TOOLS.get(tool_name)
        if tool_fn is None:
            self.collector.emit(
                EventCategory.TOOL,
                EventType.TOOL_ERROR,
                agent_id=agent_id,
                tool=tool_name,
                arguments=args,
                source_event_id=requested.step,
                derived_from=(requested.step,),
                metadata={"reason": "unknown_tool"},
            )
            return ToolResult(ok=False, error="unknown_tool")

        try:
            result = tool_fn(self.cee, args)
        except Exception as exc:  # tool crash is a recordable event, not a raise
            self.collector.emit(
                EventCategory.TOOL,
                EventType.TOOL_ERROR,
                agent_id=agent_id,
                tool=tool_name,
                arguments=args,
                source_event_id=requested.step,
                derived_from=(requested.step,),
                metadata={"reason": str(exc)},
            )
            return ToolResult(ok=False, error=str(exc))

        if not result.ok:
            self.collector.emit(
                EventCategory.TOOL,
                EventType.TOOL_ERROR,
                agent_id=agent_id,
                tool=tool_name,
                arguments=args,
                source_event_id=requested.step,
                derived_from=(requested.step,),
                metadata={"reason": result.error},
            )
            return result

        executed_derived_from = _artifact_derivation(
            self.artifact_step, self.artifact_marker, result.value, (requested.step,),
        )

        self.collector.emit(
            EventCategory.TOOL,
            EventType.TOOL_EXECUTED,
            agent_id=agent_id,
            tool=tool_name,
            arguments=args,
            result=result.value,
            authorized=True,
            source_event_id=requested.step,
            derived_from=executed_derived_from,
            content_tag=ContentTag.EXTERNAL_CONTENT,
        )
        return result


class StateGateway:
    """The same chokepoint property as `ToolGateway`, for the CEE's shared
    `kv` state (the agents' "memory"): `topology.state_auth` decides, the
    event records the decision, and an unauthorized call never reaches the
    CEE.

    §8 fixes the event vocabulary at `state_read` / `state_write` with no
    `state_denied` type, so a refused access is the same event type carrying
    `authorized=False` — which the evaluator's `authorized` predicate leaf
    already matches on.

    `artifact_step` / `artifact_marker` do the same job as in `ToolGateway`:
    a memory-poisoning case plants into `kv`, so the artifact enters the run
    through `state_read`, not through a tool call.
    """

    def __init__(
        self,
        cee: ControlledExecutionEnvironment,
        topology: Topology,
        collector: EventCollector,
        artifact_step: Optional[int] = None,
        artifact_marker: Optional[str] = None,
    ):
        self.cee = cee
        self.topology = topology
        self.collector = collector
        self.artifact_step = artifact_step
        self.artifact_marker = artifact_marker

    def read(self, agent_id: str, key: str, *, derived_from: Sequence[int] = ()) -> ToolResult:
        if not self.topology.state_authorized(agent_id, "read"):
            self.collector.emit(
                EventCategory.STATE,
                EventType.STATE_READ,
                agent_id=agent_id,
                arguments={"key": key},
                authorized=False,
                derived_from=tuple(derived_from),
                metadata={"reason": "not_authorized"},
            )
            return ToolResult(ok=False, error="not_authorized")

        value = self.cee.get_kv(key)
        self.collector.emit(
            EventCategory.STATE,
            EventType.STATE_READ,
            agent_id=agent_id,
            arguments={"key": key},
            result=value,
            authorized=True,
            derived_from=_artifact_derivation(
                self.artifact_step, self.artifact_marker, value, derived_from,
            ),
            content_tag=ContentTag.EXTERNAL_CONTENT,
        )
        return ToolResult(ok=True, value=value)

    def write(self, agent_id: str, key: str, value: Any, *, derived_from: Sequence[int] = ()) -> ToolResult:
        if not self.topology.state_authorized(agent_id, "write"):
            self.collector.emit(
                EventCategory.STATE,
                EventType.STATE_WRITE,
                agent_id=agent_id,
                arguments={"key": key, "value": value},
                authorized=False,
                derived_from=tuple(derived_from),
                metadata={"reason": "not_authorized"},
            )
            return ToolResult(ok=False, error="not_authorized")

        self.cee.set_kv(key, value)
        self.collector.emit(
            EventCategory.STATE,
            EventType.STATE_WRITE,
            agent_id=agent_id,
            arguments={"key": key, "value": value},
            authorized=True,
            derived_from=tuple(derived_from),
        )
        return ToolResult(ok=True, value=value)
