"""Scanner-mode HTTP surface. Disposable database, no model calls."""

import pytest

from scanner_mode import inspector


@pytest.fixture
def bad_policy(tmp_path, monkeypatch):
    path = tmp_path / "policy.yaml"
    path.write_text("ingress_rules: [unclosed")
    monkeypatch.setattr(inspector, "POLICY_PATH", path)


def test_scan_start_refuses_when_the_policy_cannot_load(client, bad_policy):
    before = len(client.get("/api/sessions").json())
    response = client.post("/api/scan/start", json={})
    assert response.status_code == 503
    assert "policy" in response.json()["detail"]
    assert len(client.get("/api/sessions").json()) == before
