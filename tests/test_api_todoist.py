"""Todoist API smoke tests (no live Todoist/Gemini)."""

from fastapi.testclient import TestClient

from api.main import app


def test_todoist_status():
    c = TestClient(app)
    r = c.get("/api/todoist/status")
    assert r.status_code == 200
    data = r.json()
    assert "todoist_configured" in data
    assert "gemini_configured" in data
    assert "state_path" in data


def test_power_trio_get_empty():
    c = TestClient(app)
    r = c.get("/api/todoist/power-trio")
    assert r.status_code == 200
    data = r.json()
    assert data.get("task_total", -1) >= 0
    assert isinstance(data.get("slots"), list)
    for slot in data.get("slots") or []:
        assert "tactical_steps" in slot
        assert isinstance(slot["tactical_steps"], list)
        assert len(slot["tactical_steps"]) <= 3


def test_power_trio_future_day_query():
    """Per-day bucket: recon_day echoes requested day (forward planning uses same API)."""
    c = TestClient(app)
    r = c.get("/api/todoist/power-trio", params={"day": "2030-06-15"})
    assert r.status_code == 200
    data = r.json()
    assert data.get("recon_day") == "2030-06-15"
    assert isinstance(data.get("slots"), list)


def test_sync_without_key(monkeypatch):
    monkeypatch.delenv("TODOIST_API_KEY", raising=False)
    c = TestClient(app)
    r = c.post("/api/todoist/sync")
    assert r.status_code == 503
    detail = r.json().get("detail", "")
    assert "TODOIST" in (detail if isinstance(detail, str) else str(detail))


def test_graveyard_reopen_no_key(monkeypatch):
    monkeypatch.delenv("TODOIST_API_KEY", raising=False)
    c = TestClient(app)
    r = c.post("/api/todoist/graveyard/reopen", json={"task_ids": ["123"]})
    assert r.status_code == 503


def test_graveyard_reopen_empty_body(monkeypatch):
    monkeypatch.setenv("TODOIST_API_KEY", "fake-key-for-test")
    c = TestClient(app)
    r = c.post("/api/todoist/graveyard/reopen", json={"task_ids": []})
    assert r.status_code == 400


def test_graveyard_reopen_calls_todoist(monkeypatch):
    monkeypatch.setenv("TODOIST_API_KEY", "fake-key-for-test")
    called = []

    def fake_list_entries(limit: int = 2000):
        assert limit == 3000
        return [
            {"task_id": "alpha", "title": "t", "closed_at": "x", "source": "janitor"},
            {"task_id": "beta", "title": "u", "closed_at": "y", "source": "manual"},
        ]

    def fake_reopen(key: str, ids: list[str]):
        called.append((key, list(ids)))
        return len(ids), [], ids

    monkeypatch.setattr("api.routers.todoist.list_entries", fake_list_entries)
    monkeypatch.setattr("todoist_service.reopen_tasks_for_ids", fake_reopen)

    c = TestClient(app)
    r = c.post("/api/todoist/graveyard/reopen", json={"task_ids": ["alpha", "beta", "alpha"]})
    assert r.status_code == 200
    data = r.json()
    assert data["reopened"] == 1
    assert "beta" in data["skipped_not_in_janitor_graveyard"]
    assert called == [("fake-key-for-test", ["alpha"])]


def test_graveyard_reopen_skipped_only_no_todoist_call(monkeypatch):
    monkeypatch.setenv("TODOIST_API_KEY", "fake-key-for-test")

    def fake_list_entries(limit: int = 2000):
        return [{"task_id": "alpha", "title": "t", "closed_at": "x", "source": "janitor"}]

    def fake_reopen(_key: str, _ids: list[str]):
        raise AssertionError("reopen_tasks_for_ids should not run when filter is empty")

    monkeypatch.setattr("api.routers.todoist.list_entries", fake_list_entries)
    monkeypatch.setattr("todoist_service.reopen_tasks_for_ids", fake_reopen)

    c = TestClient(app)
    r = c.post("/api/todoist/graveyard/reopen", json={"task_ids": ["zzz"]})
    assert r.status_code == 200
    data = r.json()
    assert data["reopened"] == 0
    assert data["skipped_not_in_janitor_graveyard"] == ["zzz"]
    assert data["reopened_task_ids"] == []
