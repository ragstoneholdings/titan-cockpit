"""COCKPIT_API_KEY middleware (optional)."""

import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture
def with_api_key(monkeypatch):
    monkeypatch.setenv("COCKPIT_API_KEY", "test-secret-key")
    yield
    monkeypatch.delenv("COCKPIT_API_KEY", raising=False)


def test_health_public_without_key():
    c = TestClient(app)
    r = c.get("/api/health")
    assert r.status_code == 200


def test_cockpit_requires_key_when_set(with_api_key):
    c = TestClient(app)
    r = c.get("/api/cockpit", params={"day": "2026-04-11"})
    assert r.status_code == 401


def test_cockpit_ok_with_x_cockpit_key(with_api_key):
    c = TestClient(app)
    r = c.get(
        "/api/cockpit",
        params={"day": "2026-04-11"},
        headers={"X-Cockpit-Key": "test-secret-key"},
    )
    assert r.status_code == 200


def test_cockpit_ok_with_bearer(with_api_key):
    c = TestClient(app)
    r = c.get(
        "/api/cockpit",
        params={"day": "2026-04-11"},
        headers={"Authorization": "Bearer test-secret-key"},
    )
    assert r.status_code == 200
