"""request_guard.py: the Origin and Content-Type checks on both modes' routes."""

import pytest

from scanner_mode import scanner

EVIL = {"origin": "https://evil.example"}
TEXT = {"content-type": "text/plain"}

#: Endpoints that read a JSON body.
JSON_BODY = [
    ("PUT", "/api/policy"),
    ("POST", "/api/probes"),
    ("POST", "/api/scan/start"),
    ("POST", "/api/scan/finalize"),
    ("POST", "/api/scan/cancel"),
    ("POST", "/api/lab/experiments"),
]
#: Everything else that changes state or runs work.
NO_BODY = [
    ("POST", "/api/lab/experiments/x/start"),
    ("POST", "/api/lab/experiments/x/stop"),
    ("DELETE", "/api/probes/x"),
    ("PUT", "/api/probes/x/toggle"),
    ("GET", "/api/scan/family?sessionId=x&agentId=a&category=C"),
    ("GET", "/api/lab/experiments/x/run"),
]


@pytest.mark.parametrize("method, path", JSON_BODY)
def test_a_body_that_is_not_json_is_refused(client, policy_file, method, path):
    before = policy_file.read_text()
    response = client.request(method, path, content='{"yaml": "x"}', headers=TEXT)
    assert response.status_code == 415
    assert policy_file.read_text() == before


@pytest.mark.parametrize("method, path", JSON_BODY + NO_BODY)
@pytest.mark.parametrize("origin", ["https://evil.example", "null", "http://localhost:3001"])
def test_a_foreign_origin_is_refused(client, policy_file, method, path, origin):
    before = policy_file.read_text()
    body = {"json": {"yaml": "ingress_rules: []"}} if (method, path) in JSON_BODY else {}
    response = client.request(method, path, headers={"origin": origin}, **body)
    assert response.status_code == 403
    assert policy_file.read_text() == before


def test_a_foreign_origin_creates_nothing(client, policy_file):
    before = len(client.get("/api/sessions").json())
    assert client.post("/api/scan/start", json={}, headers=EVIL).status_code == 403
    assert len(client.get("/api/sessions").json()) == before


@pytest.mark.parametrize("origin", ["http://localhost:3000", "http://127.0.0.1:3000", None])
def test_the_ui_origins_and_origin_less_clients_pass(client, policy_file, origin):
    headers = {"origin": origin} if origin else {}
    new = policy_file.read_text().replace("value: 0.2", "value: 0.25")
    assert client.put("/api/policy", json={"yaml": new}, headers=headers).status_code == 200
    assert client.get("/api/policy", headers=headers).json() == {"yaml": new}
    # bodyless POST: passes the guard, then 404s because the experiment does not exist
    assert client.post("/api/lab/experiments/x/start", headers=headers).status_code == 404


def test_json_with_a_charset_is_accepted(client, policy_file):
    response = client.put("/api/policy", json={"yaml": policy_file.read_text()},
                          headers={"content-type": "application/json; charset=utf-8"})
    assert response.status_code == 200


def test_family_scan_with_an_unknown_session_never_reaches_a_model(client, monkeypatch):
    calls = []

    async def spy(*args, **kwargs):
        calls.append(args)
        return "ok"

    monkeypatch.setattr(scanner, "_invoke_agent", spy)
    response = client.get("/api/scan/family?sessionId=nope&agentId=fake&category=DIRECT_INJECTION")
    assert "event: error" in response.text
    assert calls == []
