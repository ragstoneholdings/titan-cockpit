"""Runway / protocol / identity API tests."""

from fastapi.testclient import TestClient

from api.main import app


def test_get_protocol():
    c = TestClient(app)
    r = c.get("/api/protocol")
    assert r.status_code == 200
    data = r.json()
    assert "resolved_posture_minutes" in data


def test_get_identity_purpose():
    c = TestClient(app)
    r = c.get("/api/identity/purpose")
    assert r.status_code == 200
    assert "purpose" in r.json()


def test_runway_day_get():
    c = TestClient(app)
    r = c.get("/api/runway/2026-04-11")
    assert r.status_code == 200
    assert r.json().get("date") == "2026-04-11"
