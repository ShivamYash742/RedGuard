"""Tests for lab_store.py: Experiment / LabRun / TraceEvent persistence.

Runs against a throwaway copy of prisma/dev.db (already has the lab tables
from `prisma db push`), never the committed file itself — CLAUDE.md protects
its seeded content, so nothing here may write to it.
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

DEV_DB = Path(__file__).parent.parent / "prisma" / "dev.db"


@pytest_asyncio.fixture
async def db(tmp_path):
    test_db_path = tmp_path / "test_lab_store.db"
    shutil.copyfile(DEV_DB, test_db_path)
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
