"""Google Calendar OAuth API smoke tests."""

from fastapi.testclient import TestClient

from api.main import app


def test_google_auth_status():
    c = TestClient(app)
    r = c.get("/api/auth/google/status")
    assert r.status_code == 200
    data = r.json()
    assert "connected" in data
    assert "credentials_file_present" in data


def test_google_oauth_start_without_credentials(tmp_path, monkeypatch):
    monkeypatch.setattr("api.routers.google_auth.CREDENTIALS_PATH", tmp_path / "missing.json")
    c = TestClient(app)
    r = c.get("/api/auth/google/start", follow_redirects=False)
    assert r.status_code == 503


def test_google_oauth_callback_missing_params():
    c = TestClient(app)
    r = c.get("/api/auth/google/callback", follow_redirects=False)
    assert r.status_code in (302, 307)
    assert "calendar_error" in (r.headers.get("location") or "")
