"""Posture protocol JSON API (isolated file path)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    fake = tmp_path / "posture_protocol_state.json"
    monkeypatch.setattr("api.services.posture_protocol_read.PROTOCOL_STATE_PATH", fake)
    return TestClient(app)


def test_get_put_posture_protocol_roundtrip(client: TestClient) -> None:
    day = "2026-04-20"
    r0 = client.get("/api/posture-protocol", params={"day": day})
    assert r0.status_code == 200
    body0 = r0.json()
    assert body0["date"] == day
    assert body0["items"]["chin_tucks"] is False

    r1 = client.put("/api/posture-protocol", params={"day": day}, json={"chin_tucks": True})
    assert r1.status_code == 200
    assert r1.json()["items"]["chin_tucks"] is True
    assert r1.json()["items"]["wall_slides"] is False

    r2 = client.get("/api/posture-protocol", params={"day": day})
    assert r2.json()["items"]["chin_tucks"] is True


def test_put_posture_protocol_requires_field(client: TestClient) -> None:
    r = client.put("/api/posture-protocol", params={"day": "2026-04-21"}, json={})
    assert r.status_code == 400
