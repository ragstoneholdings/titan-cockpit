"""Zapier inbound: idempotency, rate limit envelope, trace path."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import api.routers.integrations as integrations_mod
from api.main import app


@pytest.fixture(autouse=True)
def _clear_zapier_rate_state() -> None:
    integrations_mod._zapier_hits.clear()
    yield
    integrations_mod._zapier_hits.clear()


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr("zapier_idempotency_store.PATH", tmp_path / "zapier_idempotency_keys.json")
    monkeypatch.setattr("zapier_trace_store.PATH", tmp_path / "zapier_inbound_log.json")
    monkeypatch.setattr("api.routers.integrations._zapier_max_per_window", 500)
    return TestClient(app)


def test_zapier_idempotency_dedupes(client: TestClient) -> None:
    r1 = client.post(
        "/api/integrations/zapier/inbound",
        json={"title": "Once", "source": "test"},
        headers={"X-Idempotency-Key": "idem-z-1"},
    )
    assert r1.status_code == 200
    assert r1.json().get("stored") is True
    r2 = client.post(
        "/api/integrations/zapier/inbound",
        json={"title": "Twice"},
        headers={"X-Idempotency-Key": "idem-z-1"},
    )
    assert r2.status_code == 200
    body = r2.json()
    assert body.get("deduped") is True
    assert body.get("idempotent") is True


def test_zapier_rate_limit_json(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr("api.routers.integrations._zapier_max_per_window", 3)
    monkeypatch.setattr("api.routers.integrations._zapier_window_sec", 60.0)
    for i in range(3):
        r = client.post("/api/integrations/zapier/inbound", json={"n": i})
        assert r.status_code == 200
    r = client.post("/api/integrations/zapier/inbound", json={"n": "over"})
    assert r.status_code == 429
    err = r.json()
    assert err.get("ok") is False
    assert err.get("error", {}).get("code") == "rate_limited"
