"""Work-screenshot merge: replace API duplicate so rows are not silently dropped."""

from api.services.cockpit_snapshot import _merge_work_screenshot_into_landscape


def test_merge_replaces_api_row_with_same_time_title():
    api = [
        {
            "start_iso": "2026-04-12T10:00:00-05:00",
            "title": "Strategic Planning",
            "source": "google",
            "source_kind": "personal_google",
        }
    ]
    extra = [
        {
            "start_iso": "2026-04-12T10:00:00-05:00",
            "title": "Strategic Planning",
            "source": "google",
            "source_kind": "work_screenshot",
        }
    ]
    out = _merge_work_screenshot_into_landscape(api, extra)
    assert len(out) == 1
    assert out[0]["source_kind"] == "work_screenshot"


def test_merge_appends_when_no_api_match():
    api = [
        {
            "start_iso": "2026-04-12T09:00:00-05:00",
            "title": "Other",
            "source": "google",
            "source_kind": "personal_google",
        }
    ]
    extra = [
        {
            "start_iso": "2026-04-12T10:00:00-05:00",
            "title": "Shadow only",
            "source": "google",
            "source_kind": "work_screenshot",
        }
    ]
    out = _merge_work_screenshot_into_landscape(api, extra)
    assert len(out) == 2
    kinds = {r["title"]: r["source_kind"] for r in out}
    assert kinds["Shadow only"] == "work_screenshot"
