"""End-to-end: mocked vision returns multi-column week; cockpit recon Tuesday loads work rows."""

import io
import json
from datetime import date

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from api.main import app
from api.services import work_advisory_store as wa


@pytest.fixture
def tiny_png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), color=(240, 240, 240)).save(buf, format="PNG")
    return buf.getvalue()


def test_multi_column_events_without_week_notes_then_tuesday_cockpit_has_work(
    tmp_path, monkeypatch, tiny_png
):
    """Regression: two different column_date_iso values must trigger same-week filter even if notes omit 'week of'."""
    adv_path = tmp_path / "work_calendar_advisory.json"
    monkeypatch.setattr(wa, "WORK_CALENDAR_ADVISORY_PATH", adv_path)

    mon = date(2026, 6, 1)
    assert mon.weekday() == 0
    tue = date(2026, 6, 2)

    payload = {
        "recon_day": mon.isoformat(),
        "visibility": "recon_day_visible",
        "advisory_events": [
            {
                "title": "Mon block",
                "start_local_guess": "09:00",
                "end_local_guess": None,
                "confidence": 0.9,
                "column_date_iso": mon.isoformat(),
                "column_weekday": "Monday",
            },
            {
                "title": "Tue review",
                "start_local_guess": "11:00",
                "end_local_guess": None,
                "confidence": 0.9,
                "column_date_iso": tue.isoformat(),
                "column_weekday": "Tuesday",
            },
        ],
        "suggested_anchor": {"title": None, "start_local_guess": None, "reason": ""},
        "tactical_brief": {
            "morning": {"fragmentation": "x", "kill_zone": "y", "priority": "z"},
            "afternoon": {"fragmentation": "x", "kill_zone": "y", "priority": "z"},
            "evening": {"fragmentation": "x", "kill_zone": "y", "priority": "z"},
        },
        "time_coaching": "",
        "notes": "Google Calendar agenda (no week-of phrase).",
        "is_advisory_only": True,
    }

    class _Cand:
        pass

    class _Resp:
        text = json.dumps(payload)
        candidates = [_Cand()]

    class _Model:
        def generate_content(self, _parts, generation_config=None):
            return _Resp()

    class _Gen:
        def GenerativeModel(self, _name):
            return _Model()

    monkeypatch.setattr(
        "api.services.calendar_advisory_gemini.configure_genai_from_env",
        lambda: (_Gen(), ""),
    )

    c = TestClient(app)
    files = [("files", ("stub.png", tiny_png, "image/png"))]
    r = c.post(f"/api/calendar/screenshots/analyze?day={mon.isoformat()}", files=files)
    assert r.status_code == 200, r.text
    assert adv_path.is_file()
    saved = json.loads(adv_path.read_text(encoding="utf-8"))
    rows = saved["by_date"][mon.isoformat()]["landscape_rows"]
    assert len(rows) == 2
    colz = {str(r.get("column_date_iso") or "")[:10] for r in rows}
    assert colz == {mon.isoformat(), tue.isoformat()}

    r2 = c.get("/api/cockpit", params={"day": tue.isoformat()})
    assert r2.status_code == 200
    land = r2.json()["daily_landscape"]
    ws_titles = [str(e.get("title") or "") for e in land if e.get("source_kind") == "work_screenshot"]
    assert any("Tue review" in t for t in ws_titles)
