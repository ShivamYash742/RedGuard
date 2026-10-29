"""L7: repetitions at temperature 0 were exact copies for 5 of the 6 reported models.

A base seed gives repetition N the seed base + N (clean and attack halves of a pair share it), the
temperature is configurable, both are recorded, and an experiment that would produce identical
repetitions says so.
"""

from __future__ import annotations

import json

import httpx
import pytest

from core.lab_mode.cases import fixture_factory, load_case
from core.lab_mode.model_client import ModelClient, ModelConfig
from core.lab_mode.runner import ATTACK, RunConfig, ScriptedClient, repetition_config, repetition_warnings, run_case
from core.lab_mode.topology import linear_abc
from core.lab_mode.trace import EventType


def _config(seed=None, temperature=0.0):
    return RunConfig(topology=linear_abc(), model=ModelConfig(model="m", seed=seed, temperature=temperature))


class TestRepetitionConfig:
    def test_without_a_base_seed_nothing_changes(self):
        config = _config()
        assert repetition_config(config, 3) is config

    def test_each_repetition_gets_base_plus_its_number(self):
        config = _config(seed=100, temperature=0.4)
        seeds = [repetition_config(config, rep).model.seed for rep in (1, 2, 3)]
        assert seeds == [101, 102, 103]
        assert config.model.seed == 100                                  # the experiment's own config is untouched
        again = repetition_config(config, 2)
        assert (again.model.temperature, again.model.model, again.max_steps) == (0.4, "m", config.max_steps)

    def test_a_base_seed_of_zero_is_a_seed(self):
        assert repetition_config(_config(seed=0), 1).model.seed == 1


class TestRunRepetitionsRefusesIdenticalCopies:
    """LAB-08: run_repetitions reused one config (one seed) for every repetition."""

    @pytest.mark.asyncio
    async def test_a_seeded_model_with_several_repetitions_is_refused(self):
        from core.lab_mode.runner import run_repetitions
        case = load_case("RGM-001")
        with pytest.raises(ValueError, match="repetition_config"):
            await run_repetitions(case, fixture_factory(case), _config(seed=7), ScriptedClient(case["clean_script"]),
                                  reps=3, experiment_id="e")

    @pytest.mark.asyncio
    async def test_one_repetition_or_no_seed_is_fine(self):
        from core.lab_mode.runner import run_repetitions
        case = load_case("RGM-001")
        for config, reps in ((_config(seed=7), 1), (_config(), 3)):
            pairs = await run_repetitions(case, fixture_factory(case), config, ScriptedClient(case["clean_script"]),
                                          reps=reps, experiment_id="e")
            assert len(pairs) == reps


class TestWarnings:
    base = {"repetitions": 5, "scripted": False, "model": {"temperature": 0.0, "seed": None}}

    def test_repetitions_at_temperature_zero_without_a_seed_are_flagged(self):
        (warning,) = repetition_warnings(self.base)
        assert "5 repetitions at temperature 0" in warning and "exact copies" in warning

    @pytest.mark.parametrize("change", [
        {"model": {"temperature": 0.0, "seed": 7}},      # seeded
        {"model": {"temperature": 0.3, "seed": None}},   # sampled
        {"repetitions": 1},                              # nothing to repeat
        {"scripted": True},                              # a replay is deterministic by design
    ])
    def test_the_other_configurations_are_not(self, change):
        assert repetition_warnings({**self.base, **change}) == []


class TestStoredConfig:
    def test_a_resumed_experiment_keeps_its_temperature_seed_and_token_budget(self):
        original = ModelConfig.from_env(provider="ollama", model="granite3.3:2b", temperature=0.7, seed=41, max_tokens=900)
        rebuilt = ModelConfig.from_stored(original.to_dict())
        assert (rebuilt.temperature, rebuilt.seed, rebuilt.max_tokens, rebuilt.model) == (0.7, 41, 900, "granite3.3:2b")

    def test_an_old_config_without_those_fields_gets_the_defaults(self):
        rebuilt = ModelConfig.from_stored({"provider": "ollama", "model": "x"})
        assert (rebuilt.temperature, rebuilt.seed) == (0.0, None)


class TestWhatReachesTheModelAndTheTrace:
    @pytest.mark.asyncio
    async def test_the_request_carries_the_repetitions_seed_and_the_temperature(self):
        sent = []

        def handler(request: httpx.Request) -> httpx.Response:
            sent.append(json.loads(request.content))
            return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})

        base = _config(seed=50, temperature=0.8)
        for rep in (1, 2):
            client = ModelClient(repetition_config(base, rep).model, transport=httpx.MockTransport(handler))
            await client.complete([{"role": "user", "content": "hi"}])
        assert [(p["seed"], p["temperature"]) for p in sent] == [(51, 0.8), (52, 0.8)]

    @pytest.mark.asyncio
    async def test_no_seed_is_sent_when_none_is_set(self):
        sent = []

        def handler(request: httpx.Request) -> httpx.Response:
            sent.append(json.loads(request.content))
            return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})

        client = ModelClient(repetition_config(_config(), 1).model, transport=httpx.MockTransport(handler))
        await client.complete([])
        assert "seed" not in sent[0]

    @pytest.mark.asyncio
    async def test_each_runs_actual_seed_is_in_its_config_snapshot(self):
        case = load_case("RGM-001")
        seeds = []
        for rep in (1, 2, 3):
            cfg = repetition_config(_config(seed=10), rep)
            result = await run_case(case, fixture_factory(case)(), cfg, ScriptedClient(case["clean_script"]), mode=ATTACK, run_id=f"r{rep}")
            snapshot = next(e for e in result.collector.events if e.event_type == EventType.CONFIG_SNAPSHOT)
            seeds.append(snapshot.arguments["model"]["seed"])
        assert seeds == [11, 12, 13]
