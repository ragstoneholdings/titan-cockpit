"""Titan Prep (wardrobe week-ahead) API."""

from datetime import date, timedelta

from fastapi.testclient import TestClient

from api.main import app
from api.routers.titan_prep import build_titan_prep_prompt
from api.services import titan_sartorial_store


def test_titan_prep_get_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(titan_sartorial_store, "_PATH", tmp_path / "tp.json")
    c = TestClient(app)
    wk = (date.today() + timedelta(days=3)).isoformat()
    r = c.get("/api/titan-prep", params={"week_start": wk})
    assert r.status_code == 200
    data = r.json()
    assert data["week_start"] == wk
    assert data["text"] == ""
    assert data.get("grounding_event_count") is None


def test_titan_prep_generate_mock_gemini(tmp_path, monkeypatch):
    monkeypatch.setattr(titan_sartorial_store, "_PATH", tmp_path / "tp.json")

    class _Resp:
        text = "Suit: board. L6: internal reviews. Prep: steam Friday."

    class _Model:
        def generate_content(self, _prompt):
            return _Resp()

    class _Gen:
        def GenerativeModel(self, _name):
            return _Model()

    monkeypatch.setattr("api.routers.titan_prep.configure_genai_from_env", lambda: (_Gen(), ""))
    monkeypatch.setattr(
        "api.routers.titan_prep.build_week_digest_for_titan_prep",
        lambda _wk, _cid: ("", 0),
    )

    c = TestClient(app)
    r = c.post("/api/titan-prep/generate")
    assert r.status_code == 200
    body = r.json()
    assert "Suit" in body.get("text", "")
    assert body.get("grounding_event_count") == 0


def test_titan_prep_generate_prompt_includes_digest_when_events(tmp_path, monkeypatch):
    monkeypatch.setattr(titan_sartorial_store, "_PATH", tmp_path / "tp.json")
    prompts: list[str] = []

    class _Resp:
        text = "Grounded reply."

    class _Model:
        def generate_content(self, prompt: str):
            prompts.append(prompt)
            return _Resp()

    class _Gen:
        def GenerativeModel(self, _name):
            return _Model()

    monkeypatch.setattr("api.routers.titan_prep.configure_genai_from_env", lambda: (_Gen(), ""))
    monkeypatch.setattr(
        "api.routers.titan_prep.build_week_digest_for_titan_prep",
        lambda _wk, _cid: ("2026-04-14  10:00–11:00  [google]  Board review", 1),
    )

    c = TestClient(app)
    r = c.post("/api/titan-prep/generate")
    assert r.status_code == 200
    assert prompts
    assert "CALENDAR DIGEST" in prompts[0]
    assert "Board review" in prompts[0]
    assert r.json().get("grounding_event_count") == 1


def test_titan_prep_generate_prompt_no_calendar_branch(tmp_path, monkeypatch):
    monkeypatch.setattr(titan_sartorial_store, "_PATH", tmp_path / "tp.json")
    prompts: list[str] = []

    class _Resp:
        text = "Generic prep only."

    class _Model:
        def generate_content(self, prompt: str):
            prompts.append(prompt)
            return _Resp()

    class _Gen:
        def GenerativeModel(self, _name):
            return _Model()

    monkeypatch.setattr("api.routers.titan_prep.configure_genai_from_env", lambda: (_Gen(), ""))
    monkeypatch.setattr(
        "api.routers.titan_prep.build_week_digest_for_titan_prep",
        lambda _wk, _cid: ("", 0),
    )

    c = TestClient(app)
    r = c.post("/api/titan-prep/generate")
    assert r.status_code == 200
    assert "No calendar rows" in prompts[0]
    assert "CALENDAR DIGEST" not in prompts[0]


def test_build_titan_prep_prompt_truncation_note():
    wk = date(2026, 4, 13)
    digest = "line\n" * 3
    p = build_titan_prep_prompt(
        today=date(2026, 4, 10),
        week_monday=wk,
        digest=digest,
        digest_event_total=250,
    )
    assert "capped at 200" in p
    assert "250" in p


def test_build_titan_prep_prompt_empty_digest_treated_as_no_calendar():
    wk = date(2026, 4, 13)
    p = build_titan_prep_prompt(
        today=date(2026, 4, 10),
        week_monday=wk,
        digest="",
        digest_event_total=0,
    )
    assert "No calendar rows" in p
