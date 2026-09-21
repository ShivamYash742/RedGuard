"""
RedGuard Tool Layer + Gateway
==============================

Three MVP tools over the CEE, and the `ToolGateway` that is the single
authorization chokepoint between an agent and the CEE (§5.2 of
MULTI_AGENT_LAB_PLAN.md).

`ToolGateway.call` is the *only* path from an agent to the CEE:

  1. emit `tool_requested` (args recorded verbatim)
  2. `topology.tool_authorized(agent, tool)` -> if false: emit `tool_denied`
     with reason, return a denial result, **do not execute**
  3. execute -> emit `tool_executed` with result, or `tool_error`
  4. tag the result event `content_tag = external_content`; if the result
     contains the planted artifact marker, add the artifact event to
     `derived_from`

This is what makes tool-layer containment architectural rather than a prompt
suggestion: the denial happens here, in the harness, before the CEE is ever
touched — an unauthorized call cannot mutate CEE state.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, Sequence, Tuple

from .cee import NO_RESULTS, ControlledExecutionEnvironment
from .topology import Topology
from .trace import ContentTag, EventCategory, EventCollector, EventType


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


class ToolGateway:
    """The sole authorization chokepoint between an agent and the CEE.

    `artifact_step` / `artifact_marker` are optional: when set (by the
    runner, once it has planted an artifact and recorded that event's
    step), a tool result containing the marker gets that event added to its
    `derived_from`, linking observed content back to the injection.
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
