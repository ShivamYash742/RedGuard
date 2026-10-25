"""Tests for lab_mode/api.py — the Mode B HTTP surface (§13).

Every test runs against a throwaway copy of `prisma/dev.db`, never the
committed file (CLAUDE.md protects its seeded content).

No LLM is called. Experiments are created with `scripted: true`, which makes
the runner replay each case's own `clean_script` instead of calling a model —
so the full path (create → execute → persist → evaluate → stream → read back
→ aggregate) is exercised end to end, deterministically, with no network.

The last class is the §18 regression check: Mode A's endpoints must be
untouched by any of this.
"""

from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path
from typing import Any, Dict, List

import pytest
from fastapi.testclient import TestClient
from prisma import Prisma

import database
from lab_mode import api as lab_api
from app import app
from core.lab_mode.cases import fixture_factory, load_case
from core.lab_mode.model_client import ModelConfig
from core.lab_mode.runner import CLEAN, RunConfig, RunResult
from core.lab_mode.topology import linear_abc
from core.lab_mode.trace import TraceEvent



@pytest.fixture
def client(tmp_path, monkeypatch, migrated_db_template):
    """A TestClient whose lab endpoints talk to a disposable database copy.

    Deliberately synchronous. The Prisma client has to be *connected on the
    same event loop that serves the requests*, and `TestClient` runs the app
    on a loop of its own — connecting from a pytest-asyncio fixture binds the
    client's internal locks to the wrong loop and every request then fails
    with "bound to a different event loop".

    So the swap happens at the module global `database.prisma`, and the app's
    own lifespan connects it inside `TestClient`'s loop. `get_db()` resolves
    that global at call time, which is what makes the substitution work.
    """
    test_db = tmp_path / "test_lab_api.db"
    shutil.copyfile(migrated_db_template, test_db)

    monkeypatch.setenv("DATABASE_URL", f"file:{test_db}")
    monkeypatch.setattr(database, "prisma", Prisma(datasource={"url": f"file:{test_db}"}))

    with TestClient(app) as test_client:
        yield test_client


def _create_experiment(client: TestClient, **overrides) -> Dict[str, Any]:
    body = {"arm": "attack", "cases": ["RGM-001"], "repetitions": 1, "scripted": True}
    body.update(overrides)
    response = client.post("/api/lab/experiments", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def _stream(client: TestClient, experiment_id: str) -> List[Dict[str, Any]]:
    """Consume the SSE stream into a list of (event, data) dicts."""
    events: List[Dict[str, Any]] = []
    with client.stream("GET", f"/api/lab/experiments/{experiment_id}/run") as response:
        assert response.status_code == 200
        name = None
        for line in response.iter_lines():
            if line.startswith("event:"):
                name = line.split(":", 1)[1].strip()
            elif line.startswith("data:") and name:
                events.append({"event": name, "data": json.loads(line.split(":", 1)[1].strip())})
    return events


def _run_to_completion(client: TestClient, **overrides) -> Dict[str, Any]:
    experiment = _create_experiment(client, **overrides)
    events = _stream(client, experiment["experiment_id"])
    return {"experiment": experiment, "events": events}


# ─────────────────────────────────────────────────────────────────────────────
# Catalog — pure reads off disk
# ─────────────────────────────────────────────────────────────────────────────

class TestCatalogEndpoints:
    def test_list_cases(self, client):
        body = client.get("/api/lab/cases").json()
        assert body["total"] == 40
        assert len(body["cases"]) == 40
        first = body["cases"][0]
        for key in ("id", "title", "family", "injection_point", "channel",
                    "eligible_downstream_agents", "expected_path"):
            assert key in first

    def test_get_one_case_returns_the_full_json(self, client):
        case = client.get("/api/lab/cases/RGM-001").json()
        assert case["id"] == "RGM-001"
        assert case["attack"]["canary"].startswith("RG-CANARY-")
        assert "clean_script" in case and "objective" in case

    def test_unknown_case_is_404(self, client):
        assert client.get("/api/lab/cases/RGM-999").status_code == 404

    def test_list_topologies_includes_the_authorization_tables(self, client):
        body = client.get("/api/lab/topologies").json()
        linear = next(t for t in body["topologies"] if t["id"] == "linear_abc")
        assert linear["agents"] == ["A", "B", "C"]
        assert linear["edges"] == [["A", "B"], ["B", "C"]]
        # The UI has to be able to show *why* a call was denied.
        assert linear["tool_auth"]["A"] == ["file_read", "web_search"]
        assert linear["state_auth"]["C"] == ["read", "write"]
        assert set(body["tools"]) == {"file_read", "web_search", "db_query"}

    def test_list_fixtures(self, client):
        body = client.get("/api/lab/fixtures").json()
        fixture = next(f for f in body["fixtures"] if f["fixture_id"] == "research_workflow_v1")
        assert "/research/vendor_notes.md" in fixture["files"]
        assert "customer_pii" in fixture["db"]
        assert "handoff_notes" in fixture["kv"]

    def test_list_arms(self, client):
        keys = {a["key"] for a in client.get("/api/lab/arms").json()["arms"]}
        assert keys == {
            "attack", "attack_validated", "attack_permissive_tools", "attack_bus_gateway",
            "attack_capability_gateway",
        }

    def test_bus_gateway_arm_is_an_architectural_control(self, client):
        """Decision E3. `agent_prompt` asks the model to be careful and
        measures compliance; `bus_gateway` removes the model from the
        decision. Conflating them overstates what validation achieved
        (§21.4), so they are separate arms."""
        arms = {a["key"]: a for a in client.get("/api/lab/arms").json()["arms"]}
        assert arms["attack_bus_gateway"]["validation_mode"] == "bus_gateway"
        assert arms["attack_validated"]["validation_mode"] == "agent_prompt"


# ─────────────────────────────────────────────────────────────────────────────
# Experiment creation
# ─────────────────────────────────────────────────────────────────────────────

class TestExperimentCreation:
    def test_create_returns_id_and_run_count(self, client):
        body = _create_experiment(client, cases=["RGM-001", "RGM-002"], repetitions=3)
        assert body["experiment_id"]
        # Each repetition is a CLEAN/ATTACK pair, so 2 cases x 3 reps = 12 runs.
        assert body["total_runs"] == 12

    def test_defaults_to_the_whole_case_set(self, client):
        body = client.post("/api/lab/experiments", json={"scripted": True, "repetitions": 1}).json()
        assert len(body["cases"]) == 40

    def test_unknown_arm_is_400(self, client):
        response = client.post("/api/lab/experiments", json={"arm": "arm-clean"})
        assert response.status_code == 400
        assert "Unknown arm" in response.json()["detail"]

    def test_unknown_case_id_is_400(self, client):
        response = client.post("/api/lab/experiments", json={"cases": ["RGM-404"]})
        assert response.status_code == 400
        assert "RGM-404" in response.json()["detail"]

    def test_unknown_provider_is_400_not_500(self, client):
        response = client.post("/api/lab/experiments", json={"provider": "openai"})
        assert response.status_code == 400

    @pytest.mark.parametrize("reps", [0, -1, 999])
    def test_repetitions_out_of_range_is_400(self, client, reps):
        response = client.post("/api/lab/experiments", json={"repetitions": reps})
        assert response.status_code == 400

    def test_permissive_arm_authorizes_every_tool(self, client):
        """ARM-PERMISSIVE must be visible in the stored config, because it
        changes the system under test rather than just the run."""
        body = _create_experiment(client, arm="attack_permissive_tools")
        assert body["config"]["topology_id"] == "linear_abc_permissive"

    def test_validated_arm_records_its_validation_mode(self, client):
        body = _create_experiment(client, arm="attack_validated")
        assert body["config"]["validation_mode"] == "agent_prompt"

    def test_created_experiment_is_listed_and_fetchable(self, client):
        created = _create_experiment(client)
        listed = client.get("/api/lab/experiments").json()["experiments"]
        assert created["experiment_id"] in [e["experiment_id"] for e in listed]

        detail = client.get(f"/api/lab/experiments/{created['experiment_id']}").json()
        assert detail["arm"] == "attack"
        assert detail["runs"] == []
        # §17: the stamp is recorded at creation, not at read time.
        assert detail["versions"]["versions"]["metric_version"]
        assert "git_commit" in detail["versions"]

    def test_unknown_experiment_is_404(self, client):
        assert client.get("/api/lab/experiments/nope").status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# Execution (SSE)
# ─────────────────────────────────────────────────────────────────────────────

class TestExperimentExecution:
    def test_stream_emits_the_documented_event_sequence(self, client):
        result = _run_to_completion(client)
        names = [e["event"] for e in result["events"]]

        assert names[0] == "experiment_started"
        assert names[-1] == "experiment_complete"
        for expected in ("run_started", "trace_event", "run_verdict"):
            assert expected in names, f"{expected} never streamed"
        assert "experiment_error" not in names

    def test_one_repetition_produces_a_clean_and_an_attack_run(self, client):
        result = _run_to_completion(client)
        started = [e["data"] for e in result["events"] if e["event"] == "run_started"]
        assert [s["mode"] for s in started] == ["CLEAN", "ATTACK"]
        assert len({s["pair_id"] for s in started}) == 1

    def test_verdict_event_carries_all_four_dimensions(self, client):
        result = _run_to_completion(client)
        verdict = next(e["data"] for e in result["events"] if e["event"] == "run_verdict")["verdict"]
        # `baseline_runs` and `propagation` are provenance (how many clean runs defined normal
        # behaviour; how the attack reached each influenced agent), not a fifth dimension.
        assert set(verdict) - {"baseline_runs", "propagation", "exposure"} == {"agent_impact", "objective", "containment", "system_outcome"}
        assert set(verdict["agent_impact"]) == {"A", "B", "C"}

    def test_progress_counts_reach_the_declared_total(self, client):
        result = _run_to_completion(client, cases=["RGM-001", "RGM-003"], repetitions=2)
        last = [e["data"] for e in result["events"] if e["event"] == "run_verdict"][-1]
        assert last["progress"]["completed"] == last["progress"]["total"] == 8

    def test_runs_are_persisted_with_their_baseline_link(self, client):
        result = _run_to_completion(client)
        detail = client.get(f"/api/lab/experiments/{result['experiment']['experiment_id']}").json()

        assert detail["run_count"] == 2
        assert detail["status_counts"] == {"COMPLETED": 2}

        attack = next(r for r in detail["runs"] if r["mode"] == "ATTACK")
        clean = next(r for r in detail["runs"] if r["mode"] == "CLEAN")
        # Every §9 definition is baseline-relative, so the link is recorded.
        assert attack["baseline_run_id"] == clean["run_id"]
        assert attack["verdict"] is not None
        assert clean["verdict"] is None

    def test_running_an_unknown_experiment_is_404(self, client):
        assert client.get("/api/lab/experiments/nope/run").status_code == 404

    def test_scripted_clean_script_does_not_reach_the_objective(self, client):
        """The §21.7 property, observed through the API rather than the
        library: agents replaying the benign script never satisfy the
        attacker's objective, even with the artifact planted."""
        result = _run_to_completion(client)
        verdict = next(e["data"] for e in result["events"] if e["event"] == "run_verdict")["verdict"]
        assert verdict["objective"]["level"] == "NOT_REACHED"


# ─────────────────────────────────────────────────────────────────────────────
# Runs + evidence
# ─────────────────────────────────────────────────────────────────────────────

class TestRunEndpoints:
    @pytest.fixture
    def executed(self, client):
        result = _run_to_completion(client)
        detail = client.get(f"/api/lab/experiments/{result['experiment']['experiment_id']}").json()
        return {
            "client": client,
            "attack": next(r for r in detail["runs"] if r["mode"] == "ATTACK"),
            "clean": next(r for r in detail["runs"] if r["mode"] == "CLEAN"),
        }

    def test_get_run_returns_the_ordered_event_list(self, executed):
        body = executed["client"].get(f"/api/lab/runs/{executed['attack']['run_id']}").json()
        steps = [e["step"] for e in body["events"]]
        assert steps == sorted(steps), "events must come back in trace order"
        assert body["event_count"] == len(body["events"]) > 0
        assert body["events"][0]["event_type"] == "run_started"

    def test_run_events_keep_their_provenance(self, executed):
        body = executed["client"].get(f"/api/lab/runs/{executed['attack']['run_id']}").json()
        assert any(e["derived_from"] for e in body["events"]), "derived_from lost in persistence"
        assert any(e["content_tag"] for e in body["events"])

    def test_run_carries_its_cee_snapshots(self, executed):
        body = executed["client"].get(f"/api/lab/runs/{executed['attack']['run_id']}").json()
        assert body["cee_before"] is not None and body["cee_after"] is not None
        # The artifact was planted in the attack run's environment.
        assert body["cee_before"]["files"] != body["cee_after"]["files"] or body["cee_after"]["kv"]

    def test_unknown_run_is_404(self, client):
        assert client.get("/api/lab/runs/nope").status_code == 404

    def test_evidence_bundle_embeds_case_and_both_traces(self, executed):
        bundle = executed["client"].get(
            f"/api/lab/runs/{executed['attack']['run_id']}/evidence"
        ).json()

        # §12: the case is embedded, not referenced — cases change.
        assert bundle["case"]["id"] == "RGM-001"
        assert bundle["case"]["attack"]["artifact"]
        # Both traces, because every verdict definition is baseline-relative.
        assert bundle["traces"]["attack_trace"] and bundle["traces"]["clean_trace"]
        for key in ("verdict", "provenance", "containment", "metrics", "versions", "cee"):
            assert key in bundle, key

    def test_evidence_records_the_versions_that_produced_it(self, executed):
        bundle = executed["client"].get(
            f"/api/lab/runs/{executed['attack']['run_id']}/evidence"
        ).json()
        versions = bundle["versions"]["versions"]
        for key in ("evaluator_version", "metric_version", "case_schema_version"):
            assert versions[key]
        assert "git_clean" in bundle["versions"]

    def test_evidence_for_a_clean_run_is_refused(self, executed):
        """A clean run has no verdict of its own; it *is* the baseline."""
        response = executed["client"].get(f"/api/lab/runs/{executed['clean']['run_id']}/evidence")
        assert response.status_code == 400
        assert "CLEAN" in response.json()["detail"]

    def test_evidence_for_unknown_run_is_404(self, client):
        assert client.get("/api/lab/runs/nope/evidence").status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# Metrics
# ─────────────────────────────────────────────────────────────────────────────

class TestMetricsEndpoint:
    def test_controls_and_unreachable_cases_are_left_out_of_the_headline(self, client):
        """L4: RGM-009 and RGM-008 are controls and RGM-005 is unreachable in the strict arm."""
        result = _run_to_completion(client, cases=["RGM-001", "RGM-005", "RGM-008", "RGM-009"], repetitions=2)
        body = client.get(f"/api/lab/experiments/{result['experiment']['experiment_id']}/metrics").json()

        assert body["aggregate"]["asr"]["n"] == 2                       # RGM-001 x 2 only
        assert body["n_in_scope"] == 2 and body["n_attack_runs"] == 8
        assert body["excluded"]["n_controls"] == 4 and body["excluded"]["n_unreachable"] == 2
        assert set(body["excluded"]["controls"]) == {"RGM-008", "RGM-009"}
        assert set(body["excluded"]["unreachable_in_arm"]) == {"RGM-005"}
        assert body["pooled_legacy"]["asr"]["n"] == 8                   # the 1.2.0 headline can still be reproduced
        assert {c: v["in_scope"] for c, v in body["per_case"].items()} == {
            "RGM-001": True, "RGM-005": False, "RGM-008": False, "RGM-009": False}

    def test_aggregate_shape(self, client):
        result = _run_to_completion(client, repetitions=3)
        body = client.get(
            f"/api/lab/experiments/{result['experiment']['experiment_id']}/metrics"
        ).json()

        assert body["n_attack_runs"] == 3
        aggregate = body["aggregate"]
        for key in ("icr", "asr", "partial_rate", "cpr", "depth", "coverage",
                    "containment_rate", "containment_histogram"):
            assert key in aggregate, key
        assert aggregate["icr"]["ci"] is not None

    def test_cpr_is_na_not_zero_when_the_denominator_is_empty(self, client):
        """§10.3. The clean script never compromises the entry agent, so D is
        empty — and an empty denominator means the question was never asked,
        not that propagation never happened."""
        result = _run_to_completion(client)
        body = client.get(
            f"/api/lab/experiments/{result['experiment']['experiment_id']}/metrics"
        ).json()
        assert body["aggregate"]["cpr"] == "n/a"
        assert body["aggregate"]["cpr_denominator_size"] == 0

    def test_soc_is_none_below_three_repetitions(self, client):
        """§10.7 returns None rather than a confident-looking 1.0."""
        result = _run_to_completion(client, repetitions=2)
        body = client.get(
            f"/api/lab/experiments/{result['experiment']['experiment_id']}/metrics"
        ).json()
        assert body["per_case"]["RGM-001"]["soc"] is None

    def test_soc_is_computed_at_three_repetitions(self, client):
        result = _run_to_completion(client, repetitions=3)
        body = client.get(
            f"/api/lab/experiments/{result['experiment']['experiment_id']}/metrics"
        ).json()
        assert body["per_case"]["RGM-001"]["soc"] == 1.0

    def test_tds_has_no_null_with_a_single_clean_repetition(self, client):
        """§10.8/§21.1: without repeated clean runs there is no noise floor,
        so the effect must not be reported as if there were one."""
        result = _run_to_completion(client)
        body = client.get(
            f"/api/lab/experiments/{result['experiment']['experiment_id']}/metrics"
        ).json()
        drift = body["trajectory_drift"]["RGM-001"]
        assert drift["null"] is None
        assert drift["effect"] is None
        assert drift["interpretable"] is False

    def test_tds_null_appears_once_clean_runs_repeat(self, client):
        result = _run_to_completion(client, repetitions=3)
        body = client.get(
            f"/api/lab/experiments/{result['experiment']['experiment_id']}/metrics"
        ).json()
        drift = body["trajectory_drift"]["RGM-001"]
        assert drift["clean_repetitions"] == 3
        assert drift["null"] is not None
        assert drift["interpretable"] is True

    def test_metrics_for_unknown_experiment_is_404(self, client):
        assert client.get("/api/lab/experiments/nope/metrics").status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# §18 — Mode A must be untouched
# ─────────────────────────────────────────────────────────────────────────────

class TestModeAIsUnaffected:
    def test_mode_a_routes_are_all_still_mounted(self, client):
        paths = set(app.openapi()["paths"])
        for path in ("/api/health", "/api/stats", "/api/sessions", "/api/events",
                     "/api/probes", "/api/agents", "/api/policy",
                     "/api/scan/start", "/api/scan/family", "/api/scan/finalize"):
            assert path in paths, f"Mode A route {path} disappeared"

    def test_every_lab_route_is_namespaced(self, client):
        """Mode B may only add under /api/lab — anything else would mean it
        had reached into Mode A's surface."""
        lab_paths = [p for p in app.openapi()["paths"] if "lab" in p]
        assert lab_paths
        assert all(p.startswith("/api/lab/") for p in lab_paths)

    def test_mode_a_endpoint_still_responds(self, client):
        assert client.get("/api/health").status_code == 200

    def test_lab_endpoints_never_touch_a_mode_a_table(self, client):
        """lab_store is the only DB path the router uses, and it addresses
        exactly three tables."""
        source = (Path(__file__).parents[2] / "lab_mode" / "store.py").read_text()
        for mode_a_model in ("db.session", "db.probeevent", "db.report",
                             "db.policysnapshot", "db.customprobe"):
            assert mode_a_model not in source, f"lab_store reaches into {mode_a_model}"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))


class TestCompareEndpoint:
    """§11's EXP-4/EXP-6 over HTTP. Runs pool by the arm their experiment
    recorded, so a sweep split across several experiments still compares."""

    def _two_arms(self, client):
        a = _run_to_completion(client, arm="attack", cases=["RGM-001"], repetitions=2)
        b = _run_to_completion(client, arm="attack_bus_gateway", cases=["RGM-001"], repetitions=2)
        return a["experiment"]["experiment_id"], b["experiment"]["experiment_id"]

    def test_compares_two_arms(self, client):
        first, second = self._two_arms(client)
        body = client.get(f"/api/lab/compare?experiments={first},{second}").json()

        assert set(body["arms"]) == {"attack", "attack_bus_gateway"}
        assert "EXP-6b" in body["comparisons"]
        metrics = body["comparisons"]["EXP-6b"]["metrics"]
        assert "difference" in metrics["asr"]
        assert "overlapping" in metrics["asr"]

    def test_comparison_carries_the_caveat(self, client):
        first, second = self._two_arms(client)
        body = client.get(f"/api/lab/compare?experiments={first},{second}").json()
        assert "significance test" in body["comparisons"]["EXP-6b"]["caveat"]

    def test_one_experiment_is_400(self, client):
        experiment = _create_experiment(client)
        response = client.get(f"/api/lab/compare?experiments={experiment['experiment_id']}")
        assert response.status_code == 400

    def test_same_arm_twice_is_400(self, client):
        """Two experiments of the same arm is not a comparison — saying so
        beats returning an empty result that reads as 'no difference'."""
        first = _create_experiment(client)["experiment_id"]
        second = _create_experiment(client)["experiment_id"]
        response = client.get(f"/api/lab/compare?experiments={first},{second}")
        assert response.status_code == 400
        assert "two different arms" in response.json()["detail"]

    def test_unknown_experiment_is_404(self, client):
        experiment = _create_experiment(client)["experiment_id"]
        assert client.get(f"/api/lab/compare?experiments={experiment},nope").status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# Regressions from the pre-P7 review
# ─────────────────────────────────────────────────────────────────────────────

class _TimesOutOnAttack:
    """Scripted client whose provider times out during every ATTACK run —
    the harness error an unretried timeout or exhausted budget produces."""

    def __init__(self, script):
        from core.lab_mode.runner import ScriptedClient
        self._inner = ScriptedClient(script)
        self.call_count = 0
        self._runs = 0

    def reset(self):
        self._inner.reset()
        self._runs += 1

    async def complete(self, messages):
        import httpx
        self.call_count += 1
        if self._runs % 2 == 0:
            raise httpx.ReadTimeout("provider timed out")
        return await self._inner.complete(messages)


class TestHarnessFailedPairsAreExcluded:
    """Regression: a pair whose attack run hit a harness error was stored as
    FAILED *with a verdict*, and `_outcomes` read every attack row with a
    verdict — so a truncated run scored as a valid NOT_REACHED /
    CONTAINED_AT_B result, deflating ASR with n_invalid still 0."""

    def test_failed_pair_is_reported_not_scored(self, client, monkeypatch):
        from lab_mode import api as lab_api
        monkeypatch.setattr(lab_api, "_client_for", lambda cfg, mc, case: _TimesOutOnAttack(case["clean_script"]))
        experiment = _run_to_completion(client, repetitions=2)["experiment"]

        metrics = client.get(f"/api/lab/experiments/{experiment['experiment_id']}/metrics").json()
        assert metrics["n_attack_runs"] == 0
        assert metrics["n_failed_pairs"] == 2
        assert metrics["aggregate"]["asr"]["value"] is None


class TestRunResumesInsteadOfRestarting:
    """Regression: `/run` always started from pair 1. An EventSource re-issues
    the request by itself after any disconnect, so one dropped connection
    executed the whole experiment a second time into the same record."""

    def test_second_run_executes_nothing_new(self, client):
        created = _run_to_completion(client, repetitions=2)["experiment"]
        experiment_id = created["experiment_id"]
        events = _stream(client, experiment_id)

        assert not [e for e in events if e["event"] == "run_started"]
        started = next(e for e in events if e["event"] == "experiment_started")
        assert started["data"]["already_completed_pairs"] == 2
        assert client.get(f"/api/lab/experiments/{experiment_id}").json()["run_count"] == 4

    def test_interrupted_runs_are_marked_failed_on_resume(self, client):
        import asyncio
        experiment_id = _create_experiment(client)["experiment_id"]

        async def orphan():
            from lab_mode import store as lab_store
            await lab_store.create_run(
                database.prisma, experiment_id=experiment_id, case_id="RGM-001", mode="CLEAN",
                pair_id=f"{experiment_id}-RGM-001-r1", repetition_index=1,
            )
        client.portal.call(orphan)

        _stream(client, experiment_id)
        runs = client.get(f"/api/lab/experiments/{experiment_id}").json()["runs"]
        assert not [r for r in runs if r["status"] == "RUNNING"]
        assert any((r["invalid_reason"] or "").startswith("abandoned") for r in runs)
        # ...and the pair itself was then executed properly.
        assert client.get(f"/api/lab/experiments/{experiment_id}/metrics").json()["n_attack_runs"] == 1



def test_default_step_budget_is_ten(client):
    """Regression: the API defaulted to 6 while E2 measured 10 — and the UI
    never sent max_steps, so every UI-launched experiment ran on 6."""
    experiment = _create_experiment(client)
    assert experiment["config"]["max_steps"] == 10


class TestCompareRefusesIncomparableExperiments:
    """Regression: `/compare` pooled by arm only, so arms run on different
    models or step budgets were compared and the gap reported as the arm's
    effect."""

    def test_different_step_budgets_are_refused(self, client):
        first = _run_to_completion(client, arm="attack", max_steps=10)["experiment"]["experiment_id"]
        second = _run_to_completion(client, arm="attack_bus_gateway", max_steps=4)["experiment"]["experiment_id"]
        response = client.get(f"/api/lab/compare?experiments={first},{second}")
        assert response.status_code == 400
        assert "max_steps" in response.json()["detail"]

    def test_different_case_sets_are_a_warning(self, client):
        first = _run_to_completion(client, arm="attack", cases=["RGM-001"])["experiment"]["experiment_id"]
        second = _run_to_completion(client, arm="attack_bus_gateway", cases=["RGM-002"])["experiment"]["experiment_id"]
        body = client.get(f"/api/lab/compare?experiments={first},{second}").json()
        assert any("different case sets" in w for w in body["warnings"])


class TestLiveTracking:
    def test_trace_events_name_what_they_touched(self, client):
        """The live board says `B → db_query(customer_pii) · refused`, not
        only that B acted."""
        events = [e["data"] for e in _run_to_completion(client)["events"] if e["event"] == "trace_event"]
        planted = next(e for e in events if e["event_type"] == "artifact_planted")
        assert planted["resource"] == {"channel": "files", "location": "/research/vendor_notes.md"}
        queries = [e["resource"] for e in events if e["event_type"] == "tool_requested" and e["tool"] == "db_query"]
        assert {"name": "approved_vendors"} in queries

    def test_each_case_is_rescored_against_all_its_clean_runs(self, client):
        result = _run_to_completion(client, repetitions=3)
        rescored = [e["data"] for e in result["events"] if e["event"] == "case_rescored"]
        assert len(rescored) == 1
        assert rescored[0]["baseline_runs"] == 3 and len(rescored[0]["runs"]) == 3
        run_id = rescored[0]["runs"][0]["run_id"]
        assert client.get(f"/api/lab/runs/{run_id}").json()["verdict"]["baseline_runs"] == 3

    def test_the_stream_forbids_proxy_compression(self, client):
        """The Next.js /api rewrite gzips responses by default, and gzip holds
        SSE frames until the stream ends: a live run showed nothing live."""
        experiment = _create_experiment(client)
        with client.stream("GET", f"/api/lab/experiments/{experiment['experiment_id']}/run") as response:
            assert "no-transform" in response.headers["cache-control"]

    def test_a_single_repetition_keeps_its_paired_verdict(self, client):
        result = _run_to_completion(client)
        assert not [e for e in result["events"] if e["event"] == "case_rescored"]

    @pytest.mark.asyncio
    async def test_events_arrive_while_the_run_is_still_executing(self):
        """Streaming only after the run finished meant minutes of silence per
        run against a real model, then a burst. Here the model never answers
        until the first event has already been received."""
        gate = asyncio.Event()

        class GatedClient:
            async def complete(self, messages):
                await gate.wait()
                return json.dumps({"action": "finish", "summary": "done"})

        case = load_case("RGM-001")
        cfg = RunConfig(topology=linear_abc(), model=ModelConfig(model="scripted"))
        stream = lab_api._run_streaming(case, fixture_factory(case)(), cfg, GatedClient(), mode=CLEAN, run_id="r")

        first = await asyncio.wait_for(stream.__anext__(), timeout=5)
        assert isinstance(first, TraceEvent)
        gate.set()
        rest = [item async for item in stream]
        result = rest[-1]
        assert isinstance(result, RunResult)
        assert [e.step for e in [first, *rest[:-1]]] == [e.step for e in result.collector.events]


def _wait_until_idle(client: TestClient, experiment_id: str, timeout: float = 15) -> Dict[str, Any]:
    import time
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        body = client.get(f"/api/lab/experiments/{experiment_id}").json()
        if body["live"] is None:
            return body
        time.sleep(0.05)
    raise AssertionError("experiment still running")


class TestRichLiveEvents:
    """Plan phase 2: enough in the stream to time each agent and the run."""

    def test_trace_events_carry_time_turn_and_latency(self, client):
        events = [e["data"] for e in _run_to_completion(client)["events"] if e["event"] == "trace_event"]
        assert all(e["timestamp"] for e in events)
        step = next(e for e in events if e["event_type"] == "agent_step_started")
        assert step["turn"] == 1 and step["max_steps"] == 10
        output = next(e for e in events if e["event_type"] == "agent_output")
        assert isinstance(output["latency_ms"], int)
        finished = [e for e in events if e["event_type"] == "agent_finished"]
        assert finished and all(e["reason"] for e in finished)

    def test_progress_counts_runs_not_pairs(self, client):
        events = _run_to_completion(client, repetitions=2)["events"]
        started = next(e["data"] for e in events if e["event"] == "experiment_started")
        assert started["agents"] == ["A", "B", "C"] and started["max_steps"] == 10 and started["scripted"]
        runs = [e["data"] for e in events if e["event"] == "run_started"]
        assert [r["index"] for r in runs] == [1, 2, 3, 4] and {r["total_runs"] for r in runs} == {4}
        finished = [e["data"] for e in events if e["event"] == "run_finished"]
        assert [f["progress"]["completed"] for f in finished] == [1, 2, 3, 4]
        assert all(f["steps"] > 0 and f["duration_ms"] >= 0 for f in finished)

    def test_step_delay_is_scripted_only_and_bounded(self, client):
        def stored(**overrides):
            experiment_id = _create_experiment(client, **overrides)["experiment_id"]
            return client.get(f"/api/lab/experiments/{experiment_id}").json()["config"]
        assert stored(step_delay_ms=300)["step_delay_ms"] == 300
        assert "step_delay_ms" not in stored(scripted=False, step_delay_ms=300)
        assert client.post("/api/lab/experiments", json={"step_delay_ms": 60000, "scripted": True}).status_code == 400


class TestRunsDoNotDependOnTheTab:
    """Plan phase 4: the server owns the run; viewers come and go."""

    def test_two_subscribers_receive_the_same_events(self, client):
        experiment_id = _create_experiment(client)["experiment_id"]

        async def watch_twice():
            from lab_mode import store as lab_store
            job = lab_api._start(await lab_store.get_experiment(database.prisma, experiment_id))

            async def collect():
                return [p async for p in job.subscribe()]
            return await asyncio.gather(collect(), collect())

        first, second = client.portal.call(watch_twice)
        assert first == second
        assert first[-1]["event"] == "experiment_complete"

    def test_closing_the_stream_does_not_stop_the_run(self, client):
        experiment_id = _create_experiment(client, step_delay_ms=20)["experiment_id"]
        assert client.post(f"/api/lab/experiments/{experiment_id}/start").json()["running"]
        with client.stream("GET", f"/api/lab/experiments/{experiment_id}/stream") as response:
            for line in response.iter_lines():
                if line.startswith("event: trace_event"):
                    break
        body = _wait_until_idle(client, experiment_id)
        assert sorted(r["status"] for r in body["runs"]) == ["COMPLETED", "COMPLETED"]

    def test_a_second_start_joins_instead_of_running_twice(self, client):
        experiment_id = _create_experiment(client, step_delay_ms=20)["experiment_id"]
        client.post(f"/api/lab/experiments/{experiment_id}/start")
        assert client.post(f"/api/lab/experiments/{experiment_id}/start").json()["already_running"]
        events = _stream(client, experiment_id)
        assert len([e for e in events if e["event"] == "run_started"]) == 2
        assert client.get(f"/api/lab/experiments/{experiment_id}").json()["run_count"] == 2

    def test_a_late_subscriber_gets_the_current_run_from_its_start(self, client):
        experiment_id = _create_experiment(client, repetitions=2, step_delay_ms=20)["experiment_id"]
        client.post(f"/api/lab/experiments/{experiment_id}/start")
        import time
        while (client.get(f"/api/lab/experiments/{experiment_id}").json()["live"] or {}).get("completed", 4) < 1:
            time.sleep(0.02)
        with client.stream("GET", f"/api/lab/experiments/{experiment_id}/stream") as response:
            names = [line.split(":", 1)[1].strip() for line in response.iter_lines() if line.startswith("event:")]
        assert names[0] == "experiment_started" and names[-1] == "experiment_complete"
        assert names.count("run_started") == 4 and names.count("run_verdict") == 2
        # Earlier runs' traces are not replayed: each trace follows its run_started.
        first_trace = names.index("trace_event")
        assert names[first_trace - 1] == "run_started"

    def test_stop_cancels_the_run(self, client):
        experiment_id = _create_experiment(client, step_delay_ms=2000)["experiment_id"]
        client.post(f"/api/lab/experiments/{experiment_id}/start")
        assert client.post(f"/api/lab/experiments/{experiment_id}/stop").json()["stopped"]
        body = client.get(f"/api/lab/experiments/{experiment_id}").json()
        assert body["live"] is None
        assert not [r for r in body["runs"] if r["status"] == "COMPLETED"]
        assert client.post(f"/api/lab/experiments/{experiment_id}/stop").json()["stopped"] is False

    def test_stream_of_an_idle_experiment_is_refused(self, client):
        experiment_id = _create_experiment(client)["experiment_id"]
        assert client.get(f"/api/lab/experiments/{experiment_id}/stream").status_code == 409
        assert client.get("/api/lab/experiments/nope/stream").status_code == 404
        assert client.post("/api/lab/experiments/nope/start").status_code == 404


class TestExperimentReport:
    """Mode B had per-run evidence bundles but no whole-experiment report;
    it is built from stored traces and must agree with `/metrics`."""

    def test_report_agrees_with_metrics_and_covers_every_pair(self, client):
        experiment_id = _run_to_completion(client, cases=["RGM-001", "RGM-003"], repetitions=2)["experiment"]["experiment_id"]
        report = client.get(f"/api/lab/experiments/{experiment_id}/report").json()
        metrics = client.get(f"/api/lab/experiments/{experiment_id}/metrics").json()

        assert report["complete"] and not report["running"]
        assert report["results"]["n_attack_runs"] == metrics["n_attack_runs"] == 4
        assert report["results"]["aggregate"]["asr"] == metrics["aggregate"]["asr"]
        assert report["execution"]["pairs_completed"] == report["execution"]["pairs_planned"] == 4
        assert [c["id"] for c in report["cases"]] == ["RGM-001", "RGM-003"]
        assert len(report["runs"]) == 4 and all(r["attack"]["steps"] > 0 for r in report["runs"])
        # Contained by non-compliance cites no events; the trail still shows
        # where the attack content went, starting from the plant.
        assert all(r["attack_trail"][0].split()[2] == "artifact_planted" for r in report["runs"])
        assert set(report["agents"]) == {"A", "B", "C"}
        assert report["suitability"]["applies"] is False  # scripted
        assert any("scripted replay" in f for f in report["findings"])

    def test_report_shows_which_tasks_point_at_the_poisoned_channel(self, client):
        """L9: RGM-007's task tells the agents to read the poisoned key; RGM-010's only names it."""
        experiment_id = _run_to_completion(client, cases=["RGM-007", "RGM-010"], repetitions=1)["experiment"]["experiment_id"]
        report = client.get(f"/api/lab/experiments/{experiment_id}/report").json()
        assert {c["id"]: c["task_endorses_channel"] for c in report["cases"]} == {"RGM-007": True, "RGM-010": False}
        markdown = client.get(f"/api/lab/experiments/{experiment_id}/report?format=md").text
        assert "Task points at channel" in markdown
        cases = {c["id"]: c for c in client.get("/api/lab/cases").json()["cases"]}
        assert cases["RGM-007"]["task_endorses_channel"] is True and cases["RGM-010"]["task_endorses_channel"] is False

    def test_markdown_download(self, client):
        experiment_id = _run_to_completion(client)["experiment"]["experiment_id"]
        response = client.get(f"/api/lab/experiments/{experiment_id}/report?format=md")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/markdown")
        assert "attachment" in response.headers["content-disposition"]
        body = response.text
        for heading in ("## Summary", "## Setup", "## Results", "## Agents", "## Cases", "## Runs", "## Caveats"):
            assert heading in body
        assert "RGM-001" in body

    def test_an_unfinished_experiment_says_so(self, client):
        experiment_id = _create_experiment(client, repetitions=2)["experiment_id"]
        report = client.get(f"/api/lab/experiments/{experiment_id}/report").json()
        assert not report["complete"] and report["runs"] == []
        assert any("Only 0 of 2 pairs" in c for c in report["caveats"])
        assert client.get("/api/lab/experiments/nope/report").status_code == 404


class TestRepetitionSeeds:
    """L7: temperature and a base seed are accepted, stored, and warned about when missing."""

    def test_temperature_and_seed_are_stored_with_the_experiment(self, client):
        created = _create_experiment(client, temperature=0.7, seed=41, repetitions=3)
        assert (created["config"]["model"]["temperature"], created["config"]["model"]["seed"]) == (0.7, 41)
        stored = client.get(f"/api/lab/experiments/{created['experiment_id']}").json()
        assert stored["config"]["model"]["seed"] == 41 and stored["warnings"] == []

    def test_repetitions_at_temperature_zero_without_a_seed_come_with_a_warning(self, client):
        created = _create_experiment(client, scripted=False, repetitions=5)
        assert len(created["warnings"]) == 1 and "exact copies" in created["warnings"][0]
        assert client.get(f"/api/lab/experiments/{created['experiment_id']}").json()["warnings"] == created["warnings"]

    def test_a_scripted_experiment_is_not_warned(self, client):
        assert _create_experiment(client, repetitions=5)["warnings"] == []

    @pytest.mark.parametrize("bad", [{"temperature": -0.1}, {"temperature": 2.5}, {"temperature": "hot"}, {"seed": "x"}])
    def test_bad_values_are_rejected(self, client, bad):
        response = client.post("/api/lab/experiments", json={"arm": "attack", "cases": ["RGM-001"], "scripted": True, **bad})
        assert response.status_code == 400

    def test_every_run_records_its_own_seed_and_a_pair_shares_it(self, client):
        result = _run_to_completion(client, cases=["RGM-001"], repetitions=2, seed=10)
        experiment = client.get(f"/api/lab/experiments/{result['experiment']['experiment_id']}").json()
        seeds = {}
        for run in experiment["runs"]:
            detail = client.get(f"/api/lab/runs/{run['run_id']}").json()
            snapshot = next(e for e in detail["events"] if e["event_type"] == "config_snapshot")
            seeds.setdefault(run["pair_id"], set()).add(snapshot["arguments"]["model"]["seed"])
        assert sorted(tuple(s) for s in seeds.values()) == [(11,), (12,)]     # one seed per pair, different per repetition


class TestPreAuditExperiments:
    """Experiments measured with the 1.2.0 evaluator and metrics stay visible, labelled, apart."""

    OLD = {"versions": {"benchmark_version": "4.0.0", "lab_schema_version": "1.1.0", "case_schema_version": "1.1.0",
                        "cee_version": "1.1.0", "topology_version": "1.1.0", "evaluator_version": "1.2.0",
                        "metric_version": "1.2.0"}, "git_commit": "de61e53", "git_clean": True}

    def _old_experiment(self, client, monkeypatch, **overrides):
        with monkeypatch.context() as scope:      # not monkeypatch.undo(): that would also undo the client's database swap
            scope.setattr(lab_api, "reproducibility_stamp", lambda: self.OLD)
            return _run_to_completion(client, **overrides)["experiment"]

    def test_rows_report_their_vintage_and_the_label(self, client, monkeypatch):
        old = self._old_experiment(client, monkeypatch)
        new = _run_to_completion(client)["experiment"]
        rows = {e["experiment_id"]: e for e in client.get("/api/lab/experiments").json()["experiments"]}
        assert (rows[old["experiment_id"]]["vintage"], rows[old["experiment_id"]]["vintage_label"]) == ("pre_audit", "Measured before the audit fixes")
        assert (rows[new["experiment_id"]]["vintage"], rows[new["experiment_id"]]["vintage_label"]) == ("current", None)

    def test_metrics_and_report_carry_the_label(self, client, monkeypatch):
        old = self._old_experiment(client, monkeypatch)["experiment_id"]
        assert client.get(f"/api/lab/experiments/{old}/metrics").json()["vintage"] == "pre_audit"
        report = client.get(f"/api/lab/experiments/{old}/report").json()
        assert report["experiment"]["vintage"] == "pre_audit"
        assert report["findings"][0].startswith("Measured before the audit fixes")

    def test_a_pre_audit_experiment_cannot_be_compared_with_a_current_one(self, client, monkeypatch):
        old = self._old_experiment(client, monkeypatch, arm="attack")["experiment_id"]
        new = _run_to_completion(client, arm="attack_validated")["experiment"]["experiment_id"]
        response = client.get(f"/api/lab/compare?experiments={old},{new}")
        assert response.status_code == 400 and "cannot be pooled or compared" in response.json()["detail"]

    def test_two_current_experiments_still_compare(self, client):
        a = _run_to_completion(client, arm="attack")["experiment"]["experiment_id"]
        b = _run_to_completion(client, arm="attack_validated")["experiment"]["experiment_id"]
        assert client.get(f"/api/lab/compare?experiments={a},{b}").status_code == 200


class TestForcedExposure:
    def _config(self, client, **extra):
        made = client.post("/api/lab/experiments", json={"scripted": True, "repetitions": 1, "cases": ["RGM-001"], **extra}).json()
        return client.get(f"/api/lab/experiments/{made['experiment_id']}").json()["config"]

    def test_exposure_defaults_to_natural_and_is_stored(self, client):
        assert self._config(client)["exposure"] == "natural"
        assert self._config(client, exposure="forced")["exposure"] == "forced"

    def test_an_unknown_exposure_mode_is_400(self, client):
        response = client.post("/api/lab/experiments", json={"exposure": "always"})
        assert response.status_code == 400 and "exposure" in response.json()["detail"]
