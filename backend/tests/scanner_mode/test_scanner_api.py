"""Scanner-mode HTTP surface. Disposable database, no model calls."""

import hashlib

import pytest


def test_scan_start_refuses_when_the_policy_cannot_load(client, policy_file):
    policy_file.write_text("ingress_rules: [unclosed")
    before = len(client.get("/api/sessions").json())
    response = client.post("/api/scan/start", json={})
    assert response.status_code == 503
    assert "policy" in response.json()["detail"]
    assert len(client.get("/api/sessions").json()) == before


def test_put_policy_writes_valid_yaml_atomically(client, policy_file):
    new = policy_file.read_text().replace("value: 0.2", "value: 0.3")
    response = client.put("/api/policy", json={"yaml": new})
    assert response.status_code == 200
    assert policy_file.read_text() == new
    assert client.get("/api/policy").json() == {"yaml": new}
    assert response.json()["sha256"] == hashlib.sha256(new.encode()).hexdigest()
    assert list(policy_file.parent.glob("*.tmp")) == []


@pytest.mark.parametrize("body", [
    {"yaml": "ingress_rules: [unclosed"},
    {"yaml": "ingress_rules: nope"},
    {"yaml": "ingress_rules:\n  - name: x\n    priority: 1\n    action: DENY\n    conditions: []\n"},
    {"yaml": 5},
    {},
    [],
])
def test_put_policy_rejects_invalid_input_and_leaves_the_file_alone(client, policy_file, body):
    before = policy_file.read_text()
    assert client.put("/api/policy", json=body).status_code == 400
    assert policy_file.read_text() == before


def test_session_records_the_policy_hash(client, policy_file):
    started = client.post("/api/scan/start", json={})
    assert started.status_code == 200, started.text
    session = next(s for s in client.get("/api/sessions").json() if s["id"] == started.json()["sessionId"])
    assert session["policySha256"] == hashlib.sha256(policy_file.read_bytes()).hexdigest()


def test_two_scans_started_in_the_same_second_both_get_a_session(client, policy_file, monkeypatch):
    """API-03: the session id was run_<YYYYmmdd_HHMMSS>, so a double click on Start hit the unique index and returned 500."""
    import datetime as dt
    from scanner_mode import api

    class Frozen(dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 10, 29, 12, 0, 0)

    monkeypatch.setattr(api, "datetime", Frozen)
    first, second = (client.post("/api/scan/start", json={}) for _ in range(2))
    assert first.status_code == second.status_code == 200, (first.text, second.text)
    names = {s["sessionId"] for s in client.get("/api/sessions").json() if s["id"] in (first.json()["sessionId"], second.json()["sessionId"])}
    assert len(names) == 2 and all(n.startswith("run_20261029_120000_") for n in names)


def test_scan_start_refuses_an_invalid_probe_corpus(client, policy_file, monkeypatch):
    from scanner_mode import scanner

    real = scanner.load_family_dataset

    def one_probe_without_a_prompt(family, validate=True):
        entries = real(family, validate=False)
        return [{k: v for k, v in e.items() if k != "prompt"} for e in entries[:1]] + entries[1:]

    monkeypatch.setattr(scanner, "load_family_dataset", one_probe_without_a_prompt)
    before = len(client.get("/api/sessions").json())
    response = client.post("/api/scan/start", json={})
    assert response.status_code == 503 and "probe corpus is invalid" in response.json()["detail"]
    assert len(client.get("/api/sessions").json()) == before


def test_probe_validation_endpoint_reports_the_real_result(client, monkeypatch):
    from scanner_mode import scanner
    from core.shared.version import PROBE_SCHEMA_VERSION

    ok = client.get("/api/probes/validation").json()
    assert ok == {"valid": True, "total": 315, "schemaVersion": PROBE_SCHEMA_VERSION, "error": None}

    real = scanner.load_family_dataset
    monkeypatch.setattr(scanner, "load_family_dataset",
                        lambda family, validate=True: [{**e, "id": "not-an-id"} for e in real(family, validate=False)])
    bad = client.get("/api/probes/validation").json()
    assert bad["valid"] is False and bad["total"] is None and "not-an-id" in bad["error"]


def test_session_records_the_model_config(client, policy_file):
    import json

    started = client.post("/api/scan/start", json={"agentId": "ollama_local_agent"})
    assert started.status_code == 200, started.text
    session = next(s for s in client.get("/api/sessions").json() if s["id"] == started.json()["sessionId"])
    assert json.loads(session["modelConfig"]) == {
        "provider": "ollama", "model": "granite3.3:2b", "temperature": 0, "seed": 0,
        "scaffold": "langgraph-react", "webSearch": "fixture"}


def test_scan_start_rejects_an_unknown_agent(client, policy_file):
    before = len(client.get("/api/sessions").json())
    response = client.post("/api/scan/start", json={"agentId": "no_such_agent"})
    assert response.status_code == 400 and "no_such_agent" in response.json()["detail"]
    assert len(client.get("/api/sessions").json()) == before


@pytest.mark.parametrize("query,status", [
    ("a=x:baseline&b=y:baseline&split=train", 400),
    ("a=x&b=y:baseline", 400),
    ("a=x:baseline&b=y:baseline", 404),       # nothing run
])
def test_leaderboard_compare_rejects_bad_requests(client, query, status):
    assert client.get(f"/api/leaderboard/compare?{query}").status_code == status


JSON = {"content-type": "application/json"}


@pytest.mark.parametrize("method,url", [
    ("put", "/api/policy"), ("post", "/api/probes"), ("post", "/api/scan/finalize"), ("post", "/api/scan/cancel"),
])
@pytest.mark.parametrize("raw", ["{bad", "", '"abc"', "[]", "null"])
def test_a_body_that_is_not_a_json_object_is_a_bad_request(client, policy_file, method, url, raw):
    """API-04: invalid JSON or a non-object body raised out of the handler (500)."""
    assert getattr(client, method)(url, content=raw, headers=JSON).status_code == 400


@pytest.mark.parametrize("url,body", [
    ("/api/probes", {"category": ["x"], "promptText": "y"}),
    ("/api/probes", {"category": "x", "promptText": 5}),
    ("/api/scan/finalize", {"sessionId": 5}),
    ("/api/scan/cancel", {"sessionId": ["a"]}),
])
def test_fields_of_the_wrong_type_are_a_bad_request(client, url, body):
    assert client.post(url, json=body).status_code == 400


def _statuses(client):
    return {s["id"]: s["status"] for s in client.get("/api/sessions").json()}


def test_cancel_deletes_a_running_session_only(client, policy_file):
    """API-06: cancel wiped a COMPLETED session and its report, and said 'cancelled' for an id that never existed."""
    running = client.post("/api/scan/start", json={}).json()["sessionId"]
    finished = client.post("/api/scan/start", json={}).json()["sessionId"]
    assert client.post("/api/scan/finalize", json={"sessionId": finished}).status_code == 200
    assert _statuses(client)[finished] == "COMPLETED"

    assert client.post("/api/scan/cancel", json={"sessionId": "no-such-session"}).status_code == 404
    assert client.post("/api/scan/cancel", json={"sessionId": finished}).status_code == 409
    assert finished in _statuses(client)                                  # still there, with its report
    assert client.post("/api/scan/cancel", json={"sessionId": running}).status_code == 200
    assert running not in _statuses(client) and finished in _statuses(client)


def test_stats_score_only_completed_runs_of_the_current_benchmark(client, policy_file):
    """UI-03: the dashboard's resistance score pooled legacy, older-version and FAILED / RUNNING sessions (921/1087 in dev.db)."""
    import os
    import sqlite3

    from core.shared.version import BENCHMARK_VERSION

    before = client.get("/api/stats").json()           # the seed database already holds sessions
    ids = [client.post("/api/scan/start", json={}).json()["sessionId"] for _ in range(4)]
    rows = [  # (status, benchmark version, total probes, blocked)
        ("COMPLETED", BENCHMARK_VERSION, 10, 8),
        ("COMPLETED", "4.0.0", 10, 0),
        ("FAILED: boom", BENCHMARK_VERSION, 10, 0),
        ("RUNNING", BENCHMARK_VERSION, 10, 0),
    ]
    with sqlite3.connect(os.environ["DATABASE_URL"].removeprefix("file:")) as conn:
        for session_id, (status, version, total, blocked) in zip(ids, rows):
            conn.execute("UPDATE sessions SET status = ?, benchmark_version = ?, total_probes = ?, blocked = ? WHERE id = ?",
                         (status, version, total, blocked, session_id))
    stats = client.get("/api/stats").json()
    assert stats["benchmarkVersion"] == BENCHMARK_VERSION
    assert stats["scoredSessions"] == before["scoredSessions"] + 1           # only the one completed run of this version
    assert stats["totalEvaluationsFired"] == before["totalEvaluationsFired"] + 10
    assert stats["totalBlocked"] == before["totalBlocked"] + 8
    assert stats["totalSessions"] == before["totalSessions"] + 4             # the run count still counts every session
