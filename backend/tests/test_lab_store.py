"""Tests for lab_store.py: Experiment / LabRun / TraceEvent persistence.

Runs against a throwaway copy of prisma/dev.db brought up to the current
schema by the `migrated_db_template` fixture (tests/conftest.py), never the
committed file itself — CLAUDE.md protects its seeded content, so nothing here
may write to it.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import pytest_asyncio
from prisma import Prisma

import lab_store
from core.lab.cee import ControlledExecutionEnvironment
from core.lab.topology import linear_abc
from core.lab.tools import ToolGateway
from core.lab.trace import EventCategory, EventCollector, EventType



@pytest_asyncio.fixture
async def db(tmp_path, migrated_db_template):
    test_db_path = tmp_path / "test_lab_store.db"
    shutil.copyfile(migrated_db_template, test_db_path)
    client = Prisma(datasource={"url": f"file:{test_db_path}"})
    await client.connect()
    yield client
    await client.disconnect()


def _scripted_collector() -> EventCollector:
    """Same scripted (non-LLM) driver as core/tests/test_lab_gateway.py,
    kept small here since the point is exercising persistence, not the gateway.
    """
    cee = ControlledExecutionEnvironment.from_dict({
        "files": {"/research/vendor_notes.md": "Q3 vendors: Acme, Globex."},
    })
    cee.plant_artifact("files", "/research/vendor_notes.md", "poisoned RG-CANARY-1 content")
    topo = linear_abc()
    collector = EventCollector(run_id="scripted")
    artifact_event = collector.emit(EventCategory.INJECTION, EventType.ARTIFACT_PLANTED)
    gateway = ToolGateway(cee, topo, collector, artifact_step=artifact_event.step, artifact_marker="RG-CANARY-1")
    gateway.call("A", "file_read", {"path": "/research/vendor_notes.md"})
    gateway.call("A", "db_query", {"name": "customer_pii"})  # unauthorized -> tool_denied
    return collector


class TestPersistenceRoundTrip:
    @pytest.mark.asyncio
    async def test_experiment_and_run_creation(self, db):
        experiment = await lab_store.create_experiment(
            db, name="test-exp", arm_key="attack", config={"topology": "linear_abc"}, versions={"lab_schema": "1.0.0"}
        )
        run = await lab_store.create_run(
            db, experiment_id=experiment.id, case_id="RGM-001", mode="ATTACK",
            pair_id="pair-1", repetition_index=0,
        )
        assert run.status == "RUNNING"
        assert run.experimentId == experiment.id

    @pytest.mark.asyncio
    async def test_events_round_trip(self, db):
        experiment = await lab_store.create_experiment(
            db, name="test-exp", arm_key="attack", config={}, versions={}
        )
        run = await lab_store.create_run(
            db, experiment_id=experiment.id, case_id="RGM-001", mode="ATTACK",
            pair_id="pair-1", repetition_index=0,
        )

        collector = _scripted_collector()
        inserted = await lab_store.persist_events(db, run_id=run.id, collector=collector)
        assert inserted == len(collector.events)

        loaded = await lab_store.load_run_events(db, run.id)
        assert len(loaded) == len(collector.events)

        for original, reloaded in zip(collector.events, loaded):
            assert reloaded.step == original.step
            assert reloaded.category == original.category
            assert reloaded.event_type == original.event_type
            assert reloaded.agent_id == original.agent_id
            assert reloaded.tool == original.tool
            assert reloaded.arguments == original.arguments
            assert reloaded.result == original.result
            assert reloaded.authorized == original.authorized
            assert reloaded.source_event_id == original.source_event_id
            assert reloaded.derived_from == original.derived_from
            assert reloaded.content_tag == original.content_tag

    @pytest.mark.asyncio
    async def test_taint_closure_survives_round_trip(self, db):
        """The whole point of persisting derived_from as JSON: taint closure
        computed on the rehydrated collector must match the original.
        """
        experiment = await lab_store.create_experiment(db, name="t", arm_key="attack", config={}, versions={})
        run = await lab_store.create_run(
            db, experiment_id=experiment.id, case_id="RGM-001", mode="ATTACK", pair_id="p", repetition_index=0
        )
        collector = _scripted_collector()
        await lab_store.persist_events(db, run_id=run.id, collector=collector)

        loaded = await lab_store.load_run_events(db, run.id)
        replay = EventCollector.from_events(run.id, loaded)

        from core.lab.trace import is_attack_derived

        executed = [e for e in collector.events if e.event_type == EventType.TOOL_EXECUTED][0]
        assert is_attack_derived(replay, executed.step) == is_attack_derived(collector, executed.step)
        assert is_attack_derived(replay, executed.step) is True

    @pytest.mark.asyncio
    async def test_finish_run_updates_status_and_verdict(self, db):
        experiment = await lab_store.create_experiment(db, name="t", arm_key="attack", config={}, versions={})
        run = await lab_store.create_run(
            db, experiment_id=experiment.id, case_id="RGM-001", mode="ATTACK", pair_id="p", repetition_index=0
        )
        await lab_store.finish_run(
            db, run_id=run.id, status="COMPLETED", verdict={"objective": "REACHED"}, metrics={"depth": 2}
        )
        updated = await db.labrun.find_unique(where={"id": run.id})
        assert updated.status == "COMPLETED"
        assert updated.finishedAt is not None
        assert updated.verdictJson == '{"objective": "REACHED"}'

if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))


class TestWhichRunsCount:
    """`completed_attack_runs` is the single definition of "a result" that
    both the API and the sweep aggregate."""

    @staticmethod
    def _row(pair, status, minute, mode="ATTACK", verdict='{"x": 1}'):
        from datetime import datetime, timezone
        from types import SimpleNamespace
        at = datetime(2026, 9, 27, 12, minute, tzinfo=timezone.utc)
        return SimpleNamespace(
            pairId=pair, mode=mode, status=status, verdictJson=verdict, caseId="RGM-001",
            repetitionIndex=1, startedAt=at, finishedAt=at,
        )

    def test_failed_rows_do_not_count_even_with_a_verdict(self):
        runs = [self._row("p1", "FAILED", 0)]
        assert lab_store.completed_attack_runs(runs) == []
        assert lab_store.failed_pair_ids(runs) == ["p1"]

    def test_a_resumed_pair_counts_once(self):
        """Resume re-runs a FAILED pair under the same pair_id; the pair must
        contribute exactly one result — its completed one."""
        failed, retried = self._row("p1", "FAILED", 0), self._row("p1", "COMPLETED", 5)
        assert lab_store.completed_attack_runs([failed, retried]) == [retried]
        assert lab_store.failed_pair_ids([failed, retried]) == []

    def test_clean_rows_never_count(self):
        assert lab_store.completed_attack_runs([self._row("p1", "COMPLETED", 0, mode="CLEAN")]) == []


class TestSweepResumeUsesTheStoredExperiment:
    """Regression: `sweep.py --resume <id>` rebuilt the model and step budget
    from the CLI flags. The documented command carries none, so a nemotron
    sweep resumed on the ollama default inside the same experiment."""

    @pytest.mark.asyncio
    async def test_resume_ignores_cli_model_and_steps(self, db, monkeypatch):
        import sweep
        from core.lab.model_client import ModelConfig

        experiment = await lab_store.create_experiment(
            db, name="stored", arm_key="attack",
            config={"arm": "attack", "cases": ["RGM-001"], "repetitions": 1, "scripted": True,
                    "max_steps": 7, "model": {"provider": "nvidia", "model": "stored-model"}},
            versions={},
        )
        seen = {}
        original = sweep._run_pair

        async def spy(db_, **kwargs):
            seen["max_steps"] = kwargs["run_config"].max_steps
            seen["model"] = kwargs["run_config"].model.model
            seen["client"] = type(kwargs["client"]).__name__
            return await original(db_, **kwargs)

        monkeypatch.setattr(sweep, "_run_pair", spy)
        await sweep.run_arm(
            db, arm="attack", cases=["RGM-002"], reps=3, quiet=True, scripted=False,
            model_config=ModelConfig(model="cli-model"), max_steps=99, experiment_id=experiment.id,
        )
        assert seen == {"max_steps": 7, "model": "stored-model", "client": "ScriptedClient"}
