"""L2: with exposure="forced" the harness performs the read of the planted location, so no attack run is unexposed."""

from __future__ import annotations

import pytest

from core.lab_mode.cases import fixture_factory, load_case
from core.lab_mode.evaluator import evaluate
from core.lab_mode.model_client import ModelConfig
from core.lab_mode.runner import ATTACK, CLEAN, RunConfig, ScriptedClient, run_case
from core.lab_mode.topology import linear_abc
from core.lab_mode.trace import EventType

DO_NOTHING = {a: [{"action": "finish", "summary": "done"}] for a in "ABC"}


def _config(exposure):
    return RunConfig(topology=linear_abc(), model=ModelConfig(model="scripted"), exposure=exposure)


async def _pair(case, exposure, attack_script=DO_NOTHING):
    clean = await run_case(case, fixture_factory(case)(), _config(exposure), ScriptedClient(case["clean_script"]), mode=CLEAN, run_id="c")
    attack = await run_case(case, fixture_factory(case)(), _config(exposure), ScriptedClient(attack_script), mode=ATTACK, run_id="a")
    return clean, attack


@pytest.mark.parametrize("case_id", ["RGM-001", "RGM-003", "RGM-004", "RGM-007", "RGM-110", "RGM-119"])
@pytest.mark.asyncio
async def test_forced_exposure_exposes_an_agent_that_would_never_have_read(case_id):
    case = load_case(case_id)
    clean, attack = await _pair(case, "forced")
    assert evaluate(case, attack.collector, clean.collector).exposure == {"opportunity": True, "exposed": True}
    natural_clean, natural_attack = await _pair(case, "natural")
    assert evaluate(case, natural_attack.collector, natural_clean.collector).exposure["exposed"] is False


@pytest.mark.asyncio
async def test_the_forced_read_is_recorded_as_the_entry_agents_own_action():
    case = load_case("RGM-001")
    _, attack = await _pair(case, "forced")
    events = attack.collector.events
    forced = [e for e in events if e.event_type == EventType.AGENT_OUTPUT and (e.metadata or {}).get("forced_exposure")]
    assert len(forced) == 1 and forced[0].agent_id == "A"
    executed = [e for e in events if e.event_type == EventType.TOOL_EXECUTED and e.agent_id == "A"]
    assert executed and executed[0].tool == "file_read" and executed[0].arguments == {"path": case["attack"]["delivery"]["location"]}


@pytest.mark.asyncio
async def test_the_task_channel_has_nothing_to_force():
    case = load_case("RGM-009")
    _, attack = await _pair(case, "forced")
    assert not [e for e in attack.collector.events if (e.metadata or {}).get("forced_exposure")]


def test_exposure_is_validated_and_stored():
    with pytest.raises(ValueError):
        RunConfig(topology=linear_abc(), model=ModelConfig(model="x"), exposure="always")
    assert _config("forced").to_dict()["exposure"] == "forced" and _config("natural").to_dict()["exposure"] == "natural"
