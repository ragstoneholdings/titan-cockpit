"""Morning brief dismiss API."""

from datetime import date

from fastapi.testclient import TestClient

from api.main import app
from api.services import morning_brief_store


def test_morning_brief_dismiss_persists(tmp_path, monkeypatch):
    p = tmp_path / "morning_brief_state.json"
    monkeypatch.setattr(morning_brief_store, "_STORE_PATH", p)
    c = TestClient(app)
    d = date(2026, 7, 1)
    r = c.post("/api/cockpit/morning-brief/dismiss", params={"day": d.isoformat()})
    assert r.status_code == 200
    assert r.json().get("ok") is True
    assert morning_brief_store.is_morning_brief_dismissed(d)
