"""Schedule tradeoff MCQ persistence + golden path proposal actions."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr("api.services.schedule_tradeoff_store.STORE_PATH", tmp_path / "schedule_tradeoff_answers.json")
    monkeypatch.setattr(
        "api.services.golden_path_proposal_store.STORE_PATH", tmp_path / "golden_path_proposal_actions.json"
    )
    return TestClient(app)


def test_put_get_schedule_tradeoffs(client: TestClient) -> None:
    day = "2026-05-01"
    r0 = client.get("/api/schedule-tradeoffs", params={"day": day})
    assert r0.status_code == 200
    assert r0.json()["answers"] == {}

    overlap_key = "overlap:" + "a" * 22
    r1 = client.put(
        "/api/schedule-tradeoffs",
        params={"day": day},
        json={overlap_key: "a", "work_vs_personal_truth": "undecided"},
    )
    assert r1.status_code == 200
    assert r1.json()["answers"][overlap_key] == "a"
    assert r1.json()["answers"]["work_vs_personal_truth"] == "undecided"

    r2 = client.get("/api/schedule-tradeoffs", params={"day": day})
    assert r2.json()["answers"][overlap_key] == "a"


def test_put_schedule_tradeoffs_rejects_unknown_key(client: TestClient) -> None:
    r = client.put("/api/schedule-tradeoffs", params={"day": "2026-05-02"}, json={"nope": "x"})
    assert r.status_code == 400


def test_golden_path_proposal_action(client: TestClient) -> None:
    day = "2026-05-03"
    r = client.post(
        "/api/golden-path/proposal-action",
        params={"day": day},
        json={"proposal_id": "no_deep_slot", "action": "dismiss"},
    )
    assert r.status_code == 200
    bucket = r.json()["bucket"]
    assert "no_deep_slot" in bucket["dismissed"]


def test_golden_path_clear_snooze(client: TestClient) -> None:
    day = "2026-05-04"
    client.post(
        "/api/golden-path/proposal-action",
        params={"day": day},
        json={"proposal_id": "x", "action": "snooze"},
    )
    r = client.post("/api/golden-path/clear-snooze", params={"day": day})
    assert r.status_code == 200
    assert r.json()["ok"] is True
