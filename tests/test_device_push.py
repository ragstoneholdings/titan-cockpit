"""Device token registration (Phase 5 stub)."""

from fastapi.testclient import TestClient

from api.main import app


def test_device_register():
    c = TestClient(app)
    r = c.post(
        "/api/device/register",
        json={"device_token_hex": "a" * 64, "platform": "ios", "label": "test"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data.get("ok") is True
