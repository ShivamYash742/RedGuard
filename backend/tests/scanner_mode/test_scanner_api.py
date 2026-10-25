"""Scanner-mode HTTP surface. Disposable database, no model calls."""

import hashlib
import shutil

import pytest

from scanner_mode import api, inspector, scanner


@pytest.fixture
def policy_file(tmp_path, monkeypatch):
    """A private copy of policy.yaml that every module reads instead of the real one."""
    path = tmp_path / "policy.yaml"
    shutil.copyfile(inspector.POLICY_PATH, path)
    for module in (inspector, api, scanner):
        monkeypatch.setattr(module, "POLICY_PATH", path)
    return path


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
