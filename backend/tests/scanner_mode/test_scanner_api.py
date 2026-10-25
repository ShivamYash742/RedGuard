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
    assert ok == {"valid": True, "total": 56, "schemaVersion": PROBE_SCHEMA_VERSION, "error": None}

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
        "provider": "ollama", "model": "granite3.3:2b", "temperature": 0, "seed": 0, "scaffold": "langgraph-react"}


def test_scan_start_rejects_an_unknown_agent(client, policy_file):
    before = len(client.get("/api/sessions").json())
    response = client.post("/api/scan/start", json={"agentId": "no_such_agent"})
    assert response.status_code == 400 and "no_such_agent" in response.json()["detail"]
    assert len(client.get("/api/sessions").json()) == before
