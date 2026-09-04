# REDGUARD IMPLEMENTATION — PART 1 OF 3: FOUNDATION LAYER

## WHAT YOU ARE BUILDING

You are implementing the foundation layer for RedGuard's multi-agent security laboratory. This covers:

1. **Controlled Execution Environment (CEE)** — an in-memory mock resource layer
2. **Multi-Agent Orchestrator** — agent spawning, topology, execution control
3. **Tool Gateway** — per-agent tool authorization
4. **Message Bus** — topology-enforced inter-agent communication
5. **Event/Trace Collection** — structured append-only event logging

## CONSTRAINTS

- **DO NOT modify any existing files** except `backend/prisma/schema.prisma` (additive only) and `backend/app.py` (mount new router only).
- **DO NOT delete, rename, or refactor** any existing file.
- All existing functionality (Mode A legacy benchmark) must continue working unchanged.
- The repository is at `/home/shivammishra/Pictures/RedGuard`.
- Backend is Python (FastAPI). Use `from __future__ import annotations` in all new files.
- Follow existing code style: dataclasses for data structures, async functions for I/O.

---

## FILES TO CREATE

### 1. `backend/cee/__init__.py`
```python
"""Controlled Execution Environment (CEE) for RedGuard multi-agent experiments."""
```

### 2. `backend/cee/state.py`

**Purpose:** In-memory state store representing all mock resources agents interact with.

**Data structure:**

```python
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from copy import deepcopy
import json

@dataclass
class CEEState:
    """
    Controlled Execution Environment state.
    
    NOT a security sandbox. This is a deterministic research fixture
    providing mock resources for agent tools. No OS-level isolation.
    Agents still call real LLM APIs; only tool inputs/outputs are
    intercepted and served from this state.
    """
    
    # Mock filesystem: path → content string
    filesystem: Dict[str, str] = field(default_factory=dict)
    
    # Mock web search results: query_keyword → list of result strings
    web_results: Dict[str, List[str]] = field(default_factory=dict)
    
    # Mock key-value database: key → value (any JSON-serializable)
    database: Dict[str, Any] = field(default_factory=dict)
    
    # Event log of all state accesses (populated by tools)
    access_log: List[Dict[str, Any]] = field(default_factory=list)
    
    def snapshot(self) -> str:
        """Serialize current state to JSON string for reproducibility."""
        return json.dumps({
            "filesystem": self.filesystem,
            "web_results": self.web_results,
            "database": self.database,
        }, sort_keys=True, indent=2)
    
    @classmethod
    def from_snapshot(cls, snapshot_json: str) -> "CEEState":
        """Restore state from a JSON snapshot."""
        data = json.loads(snapshot_json)
        return cls(
            filesystem=data.get("filesystem", {}),
            web_results=data.get("web_results", {}),
            database=data.get("database", {}),
        )
    
    def reset_from(self, snapshot_json: str) -> None:
        """Reset to a saved snapshot state. Clears access_log."""
        data = json.loads(snapshot_json)
        self.filesystem = data.get("filesystem", {})
        self.web_results = data.get("web_results", {})
        self.database = data.get("database", {})
        self.access_log = []
    
    def deep_copy(self) -> "CEEState":
        """Return an independent deep copy of this state."""
        return deepcopy(self)
```

### 3. `backend/cee/manager.py`

**Purpose:** CEE lifecycle — create from config, reset, provide to orchestrator.

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, Optional
from .state import CEEState

@dataclass
class CEESnapshot:
    """Named snapshot configuration for an attack case's preconditions."""
    snapshot_id: str
    description: str
    state_json: str  # Serialized CEEState

class CEEManager:
    """Manages CEE lifecycle for experiments."""
    
    def __init__(self):
        self._snapshots: Dict[str, CEESnapshot] = {}
        self._active_state: Optional[CEEState] = None
    
    def register_snapshot(self, snapshot: CEESnapshot) -> None:
        """Register a named snapshot for use in experiments."""
        self._snapshots[snapshot.snapshot_id] = snapshot
    
    def create_from_snapshot(self, snapshot_id: str) -> CEEState:
        """Create a new CEE state from a registered snapshot."""
        snap = self._snapshots.get(snapshot_id)
        if snap is None:
            raise ValueError(f"Unknown snapshot: {snapshot_id}")
        self._active_state = CEEState.from_snapshot(snap.state_json)
        return self._active_state
    
    def create_from_config(self, config: Dict[str, Any]) -> CEEState:
        """Create a new CEE state from an inline configuration dict."""
        state = CEEState(
            filesystem=config.get("filesystem", {}),
            web_results=config.get("web_results", {}),
            database=config.get("database", {}),
        )
        self._active_state = state
        return state
    
    def reset(self, snapshot_id: str) -> CEEState:
        """Reset active state to a snapshot. Returns the reset state."""
        snap = self._snapshots.get(snapshot_id)
        if snap is None:
            raise ValueError(f"Unknown snapshot: {snapshot_id}")
        if self._active_state is None:
            self._active_state = CEEState()
        self._active_state.reset_from(snap.state_json)
        return self._active_state
    
    def get_active_state(self) -> Optional[CEEState]:
        return self._active_state
```

### 4. `backend/cee/tools.py`

**Purpose:** Sandboxed tool implementations that read/write CEE state instead of real resources. Each tool returns a result AND records a trace event via a callback.

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional
from .state import CEEState

# Type for the event emission callback
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
    Read a file from the CEE filesystem.
    
    Returns file content or denial message.
    Emits tool_requested, tool_authorized/tool_denied, tool_executed events.
    """
    # Emit tool_requested
    emit_event({
        "agent_id": agent_id,
        "event_type": "tool_requested",
        "tool": "file_read",
        "arguments": {"path": path},
    })
    
    # Check authorization
    denied = any(path.startswith(dp) for dp in denied_paths)
    allowed = any(path.startswith(ap) for ap in allowed_paths)
    
    if denied or not allowed:
        emit_event({
            "agent_id": agent_id,
            "event_type": "tool_denied",
            "tool": "file_read",
            "arguments": {"path": path},
            "authorized": False,
            "risk": "high",
        })
        return f"Access denied: {path} is not accessible to agent {agent_id}."
    
    emit_event({
        "agent_id": agent_id,
        "event_type": "tool_authorized",
        "tool": "file_read",
        "arguments": {"path": path},
        "authorized": True,
    })
    
    # Read from CEE state
    content = state.filesystem.get(path)
    if content is None:
        result = f"File not found: {path}"
    else:
        result = content
    
    emit_event({
        "agent_id": agent_id,
        "event_type": "tool_executed",
        "tool": "file_read",
        "arguments": {"path": path},
        "result": result[:500],  # Truncate for storage
        "authorized": True,
    })
    
    return result


def cee_web_search(
    state: CEEState,
    agent_id: str,
    query: str,
    emit_event: EventCallback,
) -> str:
    """
    Search mock web results from CEE state.
    
    Returns matching results or "no results found".
    """
    emit_event({
        "agent_id": agent_id,
        "event_type": "tool_requested",
        "tool": "web_search",
        "arguments": {"query": query},
    })
    
    emit_event({
        "agent_id": agent_id,
        "event_type": "tool_authorized",
        "tool": "web_search",
        "arguments": {"query": query},
        "authorized": True,
    })
    
    # Find matching results (simple keyword matching)
    results = []
    query_lower = query.lower()
    for keyword, entries in state.web_results.items():
        if keyword.lower() in query_lower or query_lower in keyword.lower():
            results.extend(entries)
    
    if not results:
        result_text = "No results found."
    else:
        result_text = "\n\n---\n\n".join(results[:5])
    
    emit_event({
        "agent_id": agent_id,
        "event_type": "tool_executed",
        "tool": "web_search",
        "arguments": {"query": query},
        "result": result_text[:500],
        "authorized": True,
    })
    
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
    Query the CEE mock database by key.
    """
    emit_event({
        "agent_id": agent_id,
        "event_type": "tool_requested",
        "tool": "db_query",
        "arguments": {"key": key},
    })
    
    denied = any(key.startswith(dk) for dk in denied_keys)
    allowed = not allowed_keys or any(key.startswith(ak) for ak in allowed_keys)
    
    if denied or not allowed:
        emit_event({
            "agent_id": agent_id,
            "event_type": "tool_denied",
            "tool": "db_query",
            "arguments": {"key": key},
            "authorized": False,
            "risk": "high",
        })
        return f"Access denied: key '{key}' is not accessible to agent {agent_id}."
    
    emit_event({
        "agent_id": agent_id,
        "event_type": "tool_authorized",
        "tool": "db_query",
        "arguments": {"key": key},
        "authorized": True,
    })
    
    import json
    value = state.database.get(key)
    if value is None:
        result = f"No record found for key: {key}"
    else:
        result = json.dumps(value) if not isinstance(value, str) else value
    
    emit_event({
        "agent_id": agent_id,
        "event_type": "tool_executed",
        "tool": "db_query",
        "arguments": {"key": key},
        "result": result[:500],
        "authorized": True,
    })
    
    return result


def cee_state_write(
    state: CEEState,
    agent_id: str,
    key: str,
    value: Any,
    emit_event: EventCallback,
) -> str:
    """
    Write a value to shared CEE state (key-value store).
    Always allowed (shared state), but fully observable.
    """
    import json
    
    old_value = state.database.get(key)
    
    emit_event({
        "agent_id": agent_id,
        "event_type": "state_write",
        "tool": "state_write",
        "arguments": {"key": key, "value": str(value)[:200]},
        "result": f"old={str(old_value)[:100]}",
    })
    
    state.database[key] = value
    return f"Stored: {key}"
```

### 5. `backend/orchestrator/__init__.py`
```python
"""Multi-agent orchestration for RedGuard experiments."""
```

### 6. `backend/orchestrator/topology.py`

**Purpose:** Topology configuration and validation.

```python
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

@dataclass
class AgentConfig:
    """Configuration for a single agent in the topology."""
    agent_id: str                    # e.g., "agent_a"
    role: str                        # e.g., "researcher"
    system_prompt: str               # Role-specific system prompt
    allowed_tools: List[str]         # Tool IDs: ["file_read", "web_search", "db_query"]
    allowed_file_paths: List[str]    # CEE paths this agent may read
    denied_file_paths: List[str]     # CEE paths denied to this agent
    allowed_db_keys: List[str]       # DB keys this agent may query
    denied_db_keys: List[str]        # DB keys denied to this agent

@dataclass 
class TopologyConfig:
    """
    Topology for a multi-agent experiment.
    MVP: linear A → B → C only.
    """
    topology_id: str                     # e.g., "linear_3_permissive"
    description: str
    agents: List[AgentConfig]            # Ordered list of agents
    edges: List[Tuple[str, str]]         # Directed edges: (sender_id, receiver_id)
    defense_variant: str = "permissive"  # "permissive" or "validated"
    
    def get_agent(self, agent_id: str) -> Optional[AgentConfig]:
        for a in self.agents:
            if a.agent_id == agent_id:
                return a
        return None
    
    def get_downstream(self, agent_id: str) -> List[str]:
        """Get IDs of agents this agent can send messages to."""
        return [dst for src, dst in self.edges if src == agent_id]
    
    def get_upstream(self, agent_id: str) -> List[str]:
        """Get IDs of agents that can send messages to this agent."""
        return [src for src, dst in self.edges if dst == agent_id]
    
    def validate(self) -> List[str]:
        """Return list of validation errors (empty = valid)."""
        errors = []
        agent_ids = {a.agent_id for a in self.agents}
        
        if len(self.agents) < 2:
            errors.append("Topology must have at least 2 agents")
        
        for src, dst in self.edges:
            if src not in agent_ids:
                errors.append(f"Edge source '{src}' not in agents")
            if dst not in agent_ids:
                errors.append(f"Edge destination '{dst}' not in agents")
            if src == dst:
                errors.append(f"Self-loop not allowed: {src}")
        
        if self.defense_variant not in ("permissive", "validated"):
            errors.append(f"Unknown defense_variant: {self.defense_variant}")
        
        return errors
```

### 7. `backend/orchestrator/message_bus.py`

**Purpose:** Route messages between agents per topology. Apply content tags. Emit events.

```python
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

EventCallback = Callable[[Dict[str, Any]], None]

@dataclass
class AgentMessage:
    """A message between two agents."""
    message_id: str
    sender_id: str
    receiver_id: str
    content: str
    content_tag: str       # "original_task" | "external_content" | "derived" | "attacker_artifact"
    source_event_id: Optional[str] = None  # Provenance: event that produced this content
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()

class MessageBus:
    """
    Routes messages between agents according to topology edges.
    Does NOT alter message content. Records and tags only.
    """
    
    def __init__(self, allowed_edges: List[tuple], emit_event: EventCallback):
        self._allowed_edges = set(allowed_edges)  # {(src, dst), ...}
        self._emit_event = emit_event
        self._message_log: List[AgentMessage] = []
    
    def send(self, message: AgentMessage) -> bool:
        """
        Attempt to route a message. Returns True if delivered.
        Emits message_sent and message_received (or message_filtered) events.
        """
        edge = (message.sender_id, message.receiver_id)
        
        self._emit_event({
            "agent_id": message.sender_id,
            "event_type": "message_sent",
            "arguments": {
                "receiver": message.receiver_id,
                "content_length": len(message.content),
                "content_tag": message.content_tag,
                "content_preview": message.content[:200],
            },
            "source_event_id": message.source_event_id,
            "content_tag": message.content_tag,
        })
        
        if edge not in self._allowed_edges:
            self._emit_event({
                "agent_id": message.sender_id,
                "event_type": "message_filtered",
                "arguments": {
                    "receiver": message.receiver_id,
                    "reason": "not_in_topology",
                },
                "risk": "medium",
            })
            return False
        
        self._message_log.append(message)
        
        self._emit_event({
            "agent_id": message.receiver_id,
            "event_type": "message_received",
            "arguments": {
                "sender": message.sender_id,
                "content_length": len(message.content),
                "content_tag": message.content_tag,
                "content_preview": message.content[:200],
            },
            "source_event_id": message.source_event_id,
            "content_tag": message.content_tag,
        })
        
        return True
    
    def get_log(self) -> List[AgentMessage]:
        return list(self._message_log)
```

### 8. `backend/orchestrator/tool_gateway.py`

**Purpose:** Per-agent tool authorization. Delegates to CEE tools.

```python
from __future__ import annotations
from typing import Any, Callable, Dict, List
from backend.cee.state import CEEState
from backend.cee import tools as cee_tools

EventCallback = Callable[[Dict[str, Any]], None]

class ToolGateway:
    """
    Per-agent tool authorization gateway.
    Checks agent permissions before delegating to CEE tool implementations.
    """
    
    def __init__(self, state: CEEState, emit_event: EventCallback):
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
        Execute a tool call through the gateway.
        Returns the tool result string.
        """
        # Check if agent is allowed to use this tool at all
        if tool_name not in agent_allowed_tools:
            self._emit({
                "agent_id": agent_id,
                "event_type": "tool_denied",
                "tool": tool_name,
                "arguments": arguments,
                "authorized": False,
                "risk": "high",
            })
            return f"Tool '{tool_name}' is not available to agent {agent_id}."
        
        # Dispatch to CEE tool
        if tool_name == "file_read":
            return cee_tools.cee_file_read(
                state=self._state,
                agent_id=agent_id,
                path=arguments.get("path", ""),
                allowed_paths=agent_allowed_file_paths,
                denied_paths=agent_denied_file_paths,
                emit_event=self._emit,
            )
        elif tool_name == "web_search":
            return cee_tools.cee_web_search(
                state=self._state,
                agent_id=agent_id,
                query=arguments.get("query", ""),
                emit_event=self._emit,
            )
        elif tool_name == "db_query":
            return cee_tools.cee_db_query(
                state=self._state,
                agent_id=agent_id,
                key=arguments.get("key", ""),
                allowed_keys=agent_allowed_db_keys,
                denied_keys=agent_denied_db_keys,
                emit_event=self._emit,
            )
        elif tool_name == "state_write":
            return cee_tools.cee_state_write(
                state=self._state,
                agent_id=agent_id,
                key=arguments.get("key", ""),
                value=arguments.get("value", ""),
                emit_event=self._emit,
            )
        else:
            self._emit({
                "agent_id": agent_id,
                "event_type": "tool_denied",
                "tool": tool_name,
                "arguments": arguments,
                "authorized": False,
                "risk": "medium",
            })
            return f"Unknown tool: {tool_name}"
```

### 9. `backend/tracing/__init__.py`
```python
"""Structured trace event collection for RedGuard experiments."""
```

### 10. `backend/tracing/schema.py`

**Purpose:** TraceEvent dataclass and event type/content tag enums.

```python
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import uuid4

# Valid event types
EVENT_TYPES = {
    # System
    "experiment_started", "experiment_completed", "cee_created", "cee_reset",
    # Agent
    "agent_created", "task_assigned", "agent_step_started", "agent_step_completed",
    # Communication
    "message_sent", "message_received", "message_filtered",
    # Tool
    "tool_requested", "tool_authorized", "tool_denied", "tool_executed", "tool_result_returned",
    # State
    "state_read", "state_write", "state_modified",
    # Injection
    "attack_injected",
    # Evaluation
    "verdict_computed",
}

# Content tags (observational labels, NOT security enforcement)
CONTENT_TAGS = {
    "original_task",       # From experiment controller
    "external_content",    # From CEE mock external sources
    "derived",             # Agent-produced, incorporates external
    "attacker_artifact",   # Adversarial payload
    "system",              # System/infrastructure event
}

@dataclass
class TraceEvent:
    """A single observable event in an experiment run."""
    
    event_id: str = field(default_factory=lambda: str(uuid4()))
    run_id: str = ""
    step: int = 0
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    agent_id: Optional[str] = None      # null for system events
    event_type: str = ""                 # Must be in EVENT_TYPES
    tool: Optional[str] = None
    arguments: Optional[Dict[str, Any]] = None
    result: Optional[str] = None
    authorized: Optional[bool] = None
    source_event_id: Optional[str] = None  # Provenance: prior event this derives from
    content_tag: str = "system"            # Must be in CONTENT_TAGS
    risk: str = "none"                     # "none" | "low" | "medium" | "high"
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "run_id": self.run_id,
            "step": self.step,
            "timestamp": self.timestamp,
            "agent_id": self.agent_id,
            "event_type": self.event_type,
            "tool": self.tool,
            "arguments": self.arguments,
            "result": self.result,
            "authorized": self.authorized,
            "source_event_id": self.source_event_id,
            "content_tag": self.content_tag,
            "risk": self.risk,
            "metadata": self.metadata,
        }
```

### 11. `backend/tracing/collector.py`

**Purpose:** Append-only event collector. Assigns sequential step numbers. Stores in memory during run, provides flush to DB.

```python
from __future__ import annotations
from typing import Any, Dict, List, Optional
from datetime import datetime
from uuid import uuid4
from .schema import TraceEvent, EVENT_TYPES

class EventCollector:
    """
    Collects trace events for a single experiment run.
    Append-only. Assigns sequential step numbers.
    """
    
    def __init__(self, run_id: str):
        self.run_id = run_id
        self._events: List[TraceEvent] = []
        self._step_counter: int = 0
    
    def emit(self, event_data: Dict[str, Any]) -> TraceEvent:
        """
        Create and store a trace event from a dict of fields.
        Automatically assigns run_id, step, timestamp, event_id.
        Returns the created TraceEvent.
        """
        self._step_counter += 1
        
        event = TraceEvent(
            event_id=str(uuid4()),
            run_id=self.run_id,
            step=self._step_counter,
            timestamp=datetime.utcnow().isoformat(),
            agent_id=event_data.get("agent_id"),
            event_type=event_data.get("event_type", ""),
            tool=event_data.get("tool"),
            arguments=event_data.get("arguments"),
            result=event_data.get("result"),
            authorized=event_data.get("authorized"),
            source_event_id=event_data.get("source_event_id"),
            content_tag=event_data.get("content_tag", "system"),
            risk=event_data.get("risk", "none"),
            metadata=event_data.get("metadata"),
        )
        
        self._events.append(event)
        return event
    
    def get_events(self) -> List[TraceEvent]:
        """Return all collected events (ordered by step)."""
        return list(self._events)
    
    def get_events_by_agent(self, agent_id: str) -> List[TraceEvent]:
        return [e for e in self._events if e.agent_id == agent_id]
    
    def get_events_by_type(self, event_type: str) -> List[TraceEvent]:
        return [e for e in self._events if e.event_type == event_type]
    
    def to_dicts(self) -> List[Dict[str, Any]]:
        """Serialize all events to list of dicts (for JSON storage)."""
        return [e.to_dict() for e in self._events]
    
    @property
    def event_count(self) -> int:
        return len(self._events)
```

### 12. `backend/orchestrator/agent_wrapper.py`

**Purpose:** Wraps a LangGraph ReAct agent so that all tool calls go through the Tool Gateway and all actions emit trace events. This is the most complex file.

**Key design:**
- Creates LangChain `@tool` functions that delegate to `ToolGateway`
- Uses `create_react_agent` from `langgraph.prebuilt` (same pattern as existing agents)
- Intercepts tool calls transparently
- Emits `agent_step_started` / `agent_step_completed` events
- Returns the agent's final text response

```python
from __future__ import annotations
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass

from langchain_core.tools import tool as langchain_tool
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from backend.orchestrator.tool_gateway import ToolGateway
from backend.orchestrator.topology import AgentConfig

EventCallback = Callable[[Dict[str, Any]], None]


@dataclass
class WrappedAgent:
    """An agent wrapped with CEE tools and event emission."""
    agent_id: str
    role: str
    config: AgentConfig
    agent_instance: Any  # LangGraph agent
    
    async def invoke(self, prompt: str) -> str:
        """Send a prompt to the agent and return text response."""
        result = await self.agent_instance.ainvoke(
            {"messages": [{"role": "user", "content": prompt}]},
            config={"recursion_limit": 10}
        )
        messages = result.get("messages") if isinstance(result, dict) else None
        if not messages:
            return str(result)
        last = messages[-1]
        content = getattr(last, "content", "")
        if isinstance(content, list):
            return "\n".join(
                str(item.get("text", item)) if isinstance(item, dict) else str(item)
                for item in content
            ).strip()
        return str(content).strip()


def create_wrapped_agent(
    config: AgentConfig,
    model_id: str,
    api_key: str,
    api_base: str,
    gateway: ToolGateway,
    emit_event: EventCallback,
    temperature: float = 0,
) -> WrappedAgent:
    """
    Create a LangGraph agent with CEE-backed tools.
    
    All tool calls go through the ToolGateway. The agent sees 
    standard LangChain tools but they are backed by the CEE.
    """
    agent_id = config.agent_id
    
    # Create tool functions that route through the gateway
    @langchain_tool
    def file_read(path: str) -> str:
        """Read a file by its path."""
        return gateway.call_tool(
            agent_id=agent_id, tool_name="file_read",
            arguments={"path": path},
            agent_allowed_tools=config.allowed_tools,
            agent_allowed_file_paths=config.allowed_file_paths,
            agent_denied_file_paths=config.denied_file_paths,
            agent_allowed_db_keys=config.allowed_db_keys,
            agent_denied_db_keys=config.denied_db_keys,
        )
    
    @langchain_tool
    def web_search(query: str) -> str:
        """Search the web for information."""
        return gateway.call_tool(
            agent_id=agent_id, tool_name="web_search",
            arguments={"query": query},
            agent_allowed_tools=config.allowed_tools,
            agent_allowed_file_paths=config.allowed_file_paths,
            agent_denied_file_paths=config.denied_file_paths,
            agent_allowed_db_keys=config.allowed_db_keys,
            agent_denied_db_keys=config.denied_db_keys,
        )
    
    @langchain_tool
    def db_query(key: str) -> str:
        """Query the database by key."""
        return gateway.call_tool(
            agent_id=agent_id, tool_name="db_query",
            arguments={"key": key},
            agent_allowed_tools=config.allowed_tools,
            agent_allowed_file_paths=config.allowed_file_paths,
            agent_denied_file_paths=config.denied_file_paths,
            agent_allowed_db_keys=config.allowed_db_keys,
            agent_denied_db_keys=config.denied_db_keys,
        )
    
    # Build tool list based on agent config
    tool_map = {
        "file_read": file_read,
        "web_search": web_search,
        "db_query": db_query,
    }
    agent_tools = [tool_map[t] for t in config.allowed_tools if t in tool_map]
    
    # Create LLM
    llm = ChatOpenAI(
        model=model_id,
        openai_api_key=api_key,
        base_url=api_base,
        temperature=temperature,
        max_retries=1,
        timeout=30.0,
    )
    
    # Create LangGraph agent
    agent_instance = create_react_agent(
        model=llm,
        tools=agent_tools,
        prompt=config.system_prompt,
    )
    
    emit_event({
        "agent_id": agent_id,
        "event_type": "agent_created",
        "metadata": {"role": config.role, "model": model_id, "tools": config.allowed_tools},
    })
    
    return WrappedAgent(
        agent_id=agent_id,
        role=config.role,
        config=config,
        agent_instance=agent_instance,
    )
```

### 13. `backend/orchestrator/controller.py`

**Purpose:** Top-level experiment execution controller. Spawns agents, injects task, injects attack, runs the linear pipeline A→B→C, collects events.

This file orchestrates a single run. It:
1. Creates CEE state from snapshot/config
2. Creates event collector
3. Creates tool gateway
4. Creates message bus
5. Spawns wrapped agents
6. Assigns task to Agent A
7. Optionally injects attack into CEE state (for attacked runs)
8. Runs Agent A → collects response → forwards to Agent B → ... → Agent C
9. Returns all trace events + final output

```python
from __future__ import annotations
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from uuid import uuid4

from backend.cee.manager import CEEManager
from backend.cee.state import CEEState
from backend.orchestrator.topology import TopologyConfig, AgentConfig
from backend.orchestrator.tool_gateway import ToolGateway
from backend.orchestrator.message_bus import MessageBus, AgentMessage
from backend.orchestrator.agent_wrapper import create_wrapped_agent, WrappedAgent
from backend.tracing.collector import EventCollector

@dataclass
class RunConfig:
    """Configuration for a single experiment run."""
    run_id: str = field(default_factory=lambda: str(uuid4())[:12])
    topology: TopologyConfig = None
    model_id: str = ""
    api_key: str = ""
    api_base: str = ""
    temperature: float = 0
    cee_config: Dict[str, Any] = field(default_factory=dict)
    task_prompt: str = ""
    is_clean_baseline: bool = False
    attack_injection: Optional[Dict[str, Any]] = None  # {location, content}

@dataclass
class RunResult:
    """Result of a single experiment run."""
    run_id: str
    is_clean_baseline: bool
    events: List[Dict[str, Any]]
    agent_outputs: Dict[str, str]  # agent_id → final text
    status: str  # "completed" | "failed" | "timeout"
    error: Optional[str] = None


async def execute_run(config: RunConfig) -> RunResult:
    """
    Execute a single experiment run (clean or attacked).
    
    Flow:
    1. Create CEE from config
    2. If attacked: inject adversarial content into CEE
    3. Create agents A, B, C
    4. Agent A executes task (uses CEE tools)
    5. Agent A's output → message → Agent B
    6. Agent B processes (uses CEE tools)
    7. Agent B's output → message → Agent C
    8. Agent C processes (uses CEE tools)
    9. Collect all events
    """
    collector = EventCollector(run_id=config.run_id)
    emit = collector.emit
    
    # 1. Create CEE
    cee_manager = CEEManager()
    state = cee_manager.create_from_config(config.cee_config)
    
    emit({"event_type": "cee_created", "metadata": {"snapshot": config.cee_config}})
    
    # 2. Inject attack if not clean baseline
    attack_source_event_id = None
    if not config.is_clean_baseline and config.attack_injection:
        location = config.attack_injection["location"]  # e.g., "web_results.issue_42"
        content = config.attack_injection["content"]
        
        # Parse location and inject into CEE state
        parts = location.split(".", 1)
        resource_type = parts[0]
        resource_key = parts[1] if len(parts) > 1 else ""
        
        if resource_type == "web_results":
            if resource_key not in state.web_results:
                state.web_results[resource_key] = []
            state.web_results[resource_key].append(content)
        elif resource_type == "filesystem":
            state.filesystem[resource_key] = content
        elif resource_type == "database":
            state.database[resource_key] = content
        
        attack_event = emit({
            "event_type": "attack_injected",
            "content_tag": "attacker_artifact",
            "metadata": {
                "location": location,
                "content_preview": content[:200],
            },
        })
        attack_source_event_id = attack_event.event_id
    
    emit({"event_type": "experiment_started", "metadata": {
        "topology": config.topology.topology_id,
        "is_clean": config.is_clean_baseline,
        "model": config.model_id,
    }})
    
    # 3. Create gateway and message bus
    gateway = ToolGateway(state=state, emit_event=emit)
    bus = MessageBus(allowed_edges=config.topology.edges, emit_event=emit)
    
    # 4. Create wrapped agents
    agents: Dict[str, WrappedAgent] = {}
    for agent_config in config.topology.agents:
        agent = create_wrapped_agent(
            config=agent_config,
            model_id=config.model_id,
            api_key=config.api_key,
            api_base=config.api_base,
            gateway=gateway,
            emit_event=emit,
            temperature=config.temperature,
        )
        agents[agent_config.agent_id] = agent
    
    agent_outputs: Dict[str, str] = {}
    
    try:
        # 5. Execute pipeline: iterate agents in topology order
        current_input = config.task_prompt
        
        for i, agent_config in enumerate(config.topology.agents):
            agent = agents[agent_config.agent_id]
            
            # Assign task
            emit({
                "agent_id": agent.agent_id,
                "event_type": "task_assigned",
                "arguments": {"prompt_preview": current_input[:200]},
                "content_tag": "original_task" if i == 0 else "derived",
            })
            
            # Execute agent
            emit({"agent_id": agent.agent_id, "event_type": "agent_step_started"})
            
            response = await agent.invoke(current_input)
            agent_outputs[agent.agent_id] = response
            
            emit({
                "agent_id": agent.agent_id,
                "event_type": "agent_step_completed",
                "result": response[:300],
            })
            
            # Forward to next agent via message bus (if not last)
            downstream = config.topology.get_downstream(agent.agent_id)
            if downstream:
                next_agent_id = downstream[0]  # Linear topology: one downstream
                
                # Determine content tag
                content_tag = "derived"
                if not config.is_clean_baseline and attack_source_event_id:
                    # If agent received external content, tag as derived
                    content_tag = "derived"
                
                msg = AgentMessage(
                    message_id=str(uuid4())[:8],
                    sender_id=agent.agent_id,
                    receiver_id=next_agent_id,
                    content=response,
                    content_tag=content_tag,
                    source_event_id=attack_source_event_id,
                )
                bus.send(msg)
                
                # Next agent receives this as input
                current_input = f"You are receiving the following from {agent.role} ({agent.agent_id}):\n\n{response}\n\nPlease process this according to your role."
        
        emit({"event_type": "experiment_completed", "metadata": {"status": "completed"}})
        
        return RunResult(
            run_id=config.run_id,
            is_clean_baseline=config.is_clean_baseline,
            events=collector.to_dicts(),
            agent_outputs=agent_outputs,
            status="completed",
        )
    
    except Exception as e:
        emit({
            "event_type": "experiment_completed",
            "metadata": {"status": "failed", "error": str(e)},
            "risk": "medium",
        })
        return RunResult(
            run_id=config.run_id,
            is_clean_baseline=config.is_clean_baseline,
            events=collector.to_dicts(),
            agent_outputs=agent_outputs,
            status="failed",
            error=str(e),
        )
```

---

## DATABASE CHANGES

Add these models to `backend/prisma/schema.prisma` **at the end of the file** (do not modify existing models):

```prisma
// ── Multi-Agent Lab (Mode B) ─────────────────────────────

model Experiment {
  id              String   @id @default(cuid())
  name            String
  mode            String   // "multi_agent"
  topologyConfig  String   // JSON
  ceeSnapshotId   String
  modelConfig     String   // JSON
  probeIds        String   // JSON array
  manifestJson    String   // JSON
  createdAt       DateTime @default(now())
  runs            Run[]
}

model Run {
  id              String       @id @default(cuid())
  experiment      Experiment   @relation(fields: [experimentId], references: [id])
  experimentId    String
  runNumber       Int
  isCleanBaseline Boolean      @default(false)
  status          String       // "running" | "completed" | "failed" | "timeout"
  startedAt       DateTime     @default(now())
  finishedAt      DateTime?
  verdictJson     String?      // JSON
  metricsJson     String?      // JSON
  events          TraceEvent[]

  @@index([experimentId, runNumber])
}

model TraceEvent {
  id              String   @id @default(cuid())
  run             Run      @relation(fields: [runId], references: [id])
  runId           String
  step            Int
  timestamp       DateTime @default(now())
  agentId         String?
  eventType       String
  tool            String?
  arguments       String?  // JSON
  result          String?
  authorized      Boolean?
  sourceEventId   String?
  contentTag      String
  risk            String
  metadata        String?  // JSON

  @@index([runId, step])
  @@index([runId, eventType])
  @@index([runId, agentId])
}
```

After adding, run:
```bash
cd /home/shivammishra/Pictures/RedGuard && npx prisma migrate dev --name add_multiagent_models
```

---

## TESTS TO WRITE

Create `backend/tests/test_cee.py`:

1. **test_cee_state_snapshot_roundtrip** — Create state, snapshot, restore, verify identical
2. **test_cee_reset_clears_access_log** — Reset clears log but restores data
3. **test_cee_file_read_allowed** — Read from allowed path returns content
4. **test_cee_file_read_denied** — Read from denied path returns denial message
5. **test_cee_web_search_returns_matching** — Search returns matching CEE entries
6. **test_cee_db_query_allowed** — Query allowed key returns value
7. **test_cee_db_query_denied** — Query denied key returns denial
8. **test_cee_state_write_observable** — Write emits state_write event

Create `backend/tests/test_orchestrator.py`:

1. **test_topology_validation** — Invalid topologies produce errors
2. **test_message_bus_allowed_edge** — Message on valid edge is delivered
3. **test_message_bus_blocked_edge** — Message on invalid edge is filtered
4. **test_tool_gateway_denies_unlisted_tool** — Agent calling unlisted tool gets denial
5. **test_event_collector_sequential_steps** — Steps are sequential and gapless

---

## ACCEPTANCE CRITERIA

- [ ] `CEEState` can be created, serialized to JSON, and restored identically
- [ ] CEE tools only access in-memory state (no `pathlib`, no `requests`, no `subprocess`)
- [ ] Tool gateway denies unauthorized tool calls and emits `tool_denied` events
- [ ] Message bus only routes messages along topology edges
- [ ] Every tool call and message produces at least one TraceEvent
- [ ] TraceEvent steps are sequential within a run
- [ ] New Prisma models migrate without affecting existing tables
- [ ] All tests pass
- [ ] Existing `npm run dev` still works (Mode A unchanged)
