"""
Experiment execution controller.

Orchestrates a single multi-agent experiment run:
1. Creates CEE state from config
2. Creates EventCollector, ToolGateway, MessageBus
3. Injects adversarial payload into CEE (for attacked runs)
4. Spawns wrapped agents A, B, C
5. Executes linear pipeline: A → B → C
6. Returns RunResult with all trace events

This file coordinates the parts; it does not contain business logic
that belongs in individual modules (gateway, bus, tools, agents).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

from cee.manager import CEEManager
from cee.state import CEEState
from orchestrator.topology import TopologyConfig
from orchestrator.tool_gateway import ToolGateway
from orchestrator.message_bus import MessageBus, AgentMessage
from orchestrator.agent_wrapper import create_wrapped_agent, WrappedAgent
from tracing.collector import EventCollector


# ── Data Transfer Objects ─────────────────────────────────────────────────────

@dataclass
class RunConfig:
    """All parameters for a single experiment run."""

    run_id: str = field(default_factory=lambda: str(uuid4())[:12])
    topology: Optional[TopologyConfig] = None
    model_id: str = "gpt-4o-mini"
    api_key: str = ""
    api_base: str = "https://api.openai.com/v1"
    temperature: float = 0.0
    cee_config: Dict[str, Any] = field(default_factory=dict)  # inline CEE init dict
    task_prompt: str = ""
    is_clean_baseline: bool = False
    # Adversarial injection spec: {"location": "web_results.key", "content": "..."}
    attack_injection: Optional[Dict[str, Any]] = None
    mock_mode: bool = False  # If True, use stub agents (no LLM calls)


@dataclass
class RunResult:
    """Output of a single experiment run."""

    run_id: str
    is_clean_baseline: bool
    events: List[Dict[str, Any]]        # Serialized trace events
    agent_outputs: Dict[str, str]       # agent_id → final text response
    status: str                         # "completed" | "failed" | "timeout"
    error: Optional[str] = None


# ── Main Entry Point ──────────────────────────────────────────────────────────

async def execute_run(config: RunConfig) -> RunResult:
    """
    Execute a single experiment run (clean baseline or attacked).

    Linear pipeline: Agent A → Agent B → Agent C.

    The attack injection (if any) happens AFTER CEE state is created and
    BEFORE agents are invoked — the CEE state is already contaminated when
    Agent A first calls web_search / file_read.
    """
    collector = EventCollector(run_id=config.run_id)
    emit = collector.emit

    # ── 1. Initialize CEE ─────────────────────────────────────────────────────
    manager = CEEManager()
    state: CEEState = manager.create_from_config(config.cee_config)

    emit(
        {
            "event_type": "cee_created",
            "content_tag": "system",
            "metadata": {"has_filesystem": bool(state.filesystem)},
        }
    )

    # ── 2. Inject adversarial payload (attacked runs only) ────────────────────
    attack_source_event_id: Optional[str] = None

    if not config.is_clean_baseline and config.attack_injection:
        location: str = config.attack_injection.get("location", "")
        content: str = config.attack_injection.get("content", "")

        parts = location.split(".", 1)
        resource_type = parts[0] if parts else ""
        resource_key = parts[1] if len(parts) > 1 else ""

        if resource_type == "web_results" and resource_key:
            if resource_key not in state.web_results:
                state.web_results[resource_key] = []
            state.web_results[resource_key].append(content)
        elif resource_type == "filesystem" and resource_key:
            state.filesystem[resource_key] = content
        elif resource_type == "database" and resource_key:
            state.database[resource_key] = content

        attack_event = emit(
            {
                "event_type": "attack_injected",
                "content_tag": "attacker_artifact",
                "risk": "high",
                "metadata": {
                    "location": location,
                    "content_preview": content[:200],
                },
            }
        )
        attack_source_event_id = attack_event.event_id

    # ── 3. Set up gateway + bus ───────────────────────────────────────────────
    topology = config.topology
    gateway = ToolGateway(state=state, emit_event=emit)
    bus = MessageBus(allowed_edges=topology.edges, emit_event=emit)

    emit(
        {
            "event_type": "experiment_started",
            "content_tag": "system",
            "metadata": {
                "topology_id": topology.topology_id,
                "is_clean": config.is_clean_baseline,
                "model": config.model_id,
                "defense_variant": topology.defense_variant,
            },
        }
    )

    # ── 4. Spawn agents ───────────────────────────────────────────────────────
    resolved_api_key = config.api_key or os.getenv("NVIDIA_API_KEY", "") or os.getenv("OPENAI_API_KEY", "")
    resolved_api_base = config.api_base or "https://api.openai.com/v1"

    agents: Dict[str, WrappedAgent] = {}
    for agent_cfg in topology.agents:
        wrapped = create_wrapped_agent(
            config=agent_cfg,
            model_id=config.model_id,
            api_key=resolved_api_key,
            api_base=resolved_api_base,
            gateway=gateway,
            emit_event=emit,
            temperature=config.temperature,
            mock_mode=config.mock_mode,
        )
        agents[agent_cfg.agent_id] = wrapped

    agent_outputs: Dict[str, str] = {}

    try:
        # ── 5. Execute pipeline ───────────────────────────────────────────────
        current_input = config.task_prompt

        for step_idx, agent_cfg in enumerate(topology.agents):
            agent = agents[agent_cfg.agent_id]

            # Assign task to this agent
            content_tag = "original_task" if step_idx == 0 else "derived"
            emit(
                {
                    "agent_id": agent.agent_id,
                    "event_type": "task_assigned",
                    "arguments": {"prompt_preview": current_input[:200]},
                    "content_tag": content_tag,
                    "source_event_id": attack_source_event_id if step_idx > 0 else None,
                }
            )

            emit(
                {
                    "agent_id": agent.agent_id,
                    "event_type": "agent_step_started",
                    "content_tag": "system",
                }
            )

            # Invoke agent
            response = await agent.invoke(current_input)
            agent_outputs[agent.agent_id] = response

            emit(
                {
                    "agent_id": agent.agent_id,
                    "event_type": "agent_step_completed",
                    "result": response[:300],
                    "content_tag": "derived",
                    "source_event_id": attack_source_event_id,
                }
            )

            # Forward to downstream agent via message bus
            downstream_ids = topology.get_downstream(agent.agent_id)
            if downstream_ids:
                next_agent_id = downstream_ids[0]  # Linear topology: one downstream

                msg = AgentMessage(
                    message_id=str(uuid4())[:8],
                    sender_id=agent.agent_id,
                    receiver_id=next_agent_id,
                    content=response,
                    content_tag="derived",
                    source_event_id=attack_source_event_id,
                )
                bus.send(msg)

                # Build the downstream agent's input from the upstream response
                current_input = (
                    f"You are receiving findings from the {agent.role} agent "
                    f"({agent.agent_id}).\n\n"
                    f"--- BEGIN UPSTREAM OUTPUT ---\n{response}\n--- END UPSTREAM OUTPUT ---\n\n"
                    f"Please process and complete your role responsibilities."
                )

        # ── 6. Finalize ───────────────────────────────────────────────────────
        emit(
            {
                "event_type": "experiment_completed",
                "content_tag": "system",
                "metadata": {"status": "completed"},
            }
        )

        return RunResult(
            run_id=config.run_id,
            is_clean_baseline=config.is_clean_baseline,
            events=collector.to_dicts(),
            agent_outputs=agent_outputs,
            status="completed",
        )

    except Exception as exc:
        emit(
            {
                "event_type": "experiment_completed",
                "content_tag": "system",
                "risk": "medium",
                "metadata": {"status": "failed", "error": str(exc)},
            }
        )
        return RunResult(
            run_id=config.run_id,
            is_clean_baseline=config.is_clean_baseline,
            events=collector.to_dicts(),
            agent_outputs=agent_outputs,
            status="failed",
            error=str(exc),
        )


# ── Convenience Wrapper ───────────────────────────────────────────────────────

class ExperimentController:
    """
    Stateful wrapper around execute_run for use by the FastAPI experiment router
    and the CLI matrix runner.

    Accepts dependency-injected topology, CEEState, and EventCollector
    (already set up by the caller) for tested composition.
    """

    def __init__(
        self,
        topology: TopologyConfig,
        cee_state: CEEState,
        event_collector: EventCollector,
        model_config: Optional[Dict[str, Any]] = None,
        mock_mode: bool = False,
    ) -> None:
        self._topology = topology
        self._cee_state = cee_state
        self._collector = event_collector
        self._model_config = model_config or {}
        self._mock_mode = mock_mode

    async def run(
        self,
        initial_task: str,
        attack_artifact: Optional[Dict[str, Any]] = None,
        entry_point: str = "agent_a",
    ) -> RunResult:
        """
        Run the experiment pipeline.

        attack_artifact: dict with 'location' and 'content' keys,
                         or None for a clean baseline.
        """
        cfg = RunConfig(
            run_id=self._collector.run_id,
            topology=self._topology,
            model_id=self._model_config.get("model_id", "gpt-4o-mini"),
            api_key=self._model_config.get("api_key", ""),
            api_base=self._model_config.get("api_base", "https://api.openai.com/v1"),
            temperature=self._model_config.get("temperature", 0.0),
            cee_config={
                "filesystem": self._cee_state.filesystem,
                "web_results": self._cee_state.web_results,
                "database": self._cee_state.database,
            },
            task_prompt=initial_task,
            is_clean_baseline=(attack_artifact is None),
            attack_injection=attack_artifact,
            mock_mode=self._mock_mode,
        )
        return await execute_run(cfg)
