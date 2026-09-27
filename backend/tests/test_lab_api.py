"""Tests for lab_api.py — the Mode B HTTP surface (§13).

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

import json
import shutil
from pathlib import Path
from typing import Any, Dict, List

import pytest
from fastapi.testclient import TestClient
from prisma import Prisma

import database
from app import app



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
        assert body["total"] == 9
        assert len(body["cases"]) == 9
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
        assert len(body["cases"]) == 9

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
        assert set(verdict) == {"agent_impact", "objective", "containment", "system_outcome"}
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
        source = (Path(__file__).parent.parent / "lab_store.py").read_text()
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
