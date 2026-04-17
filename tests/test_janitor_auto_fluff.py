"""Janitor auto-fluff archive (env-gated)."""

import todoist_service as ts


def test_janitor_auto_archive_fluff_disabled_by_default(monkeypatch):
    monkeypatch.delenv("JANITOR_AUTO_ARCHIVE_FLUFF", raising=False)
    n, hint, log = ts.janitor_auto_archive_fluff("fake-key")
    assert n == 0
    assert log == []


def test_janitor_auto_archive_fluff_closes_match(monkeypatch):
    monkeypatch.setenv("JANITOR_AUTO_ARCHIVE_FLUFF", "1")
    closed: list[str] = []

    def fake_fetch(_k):
        return [
            {"id": "99", "content": "Read newsletter summaries", "description": "", "checked": False},
            {"id": "100", "content": "Read newsletter @Titan_Core", "description": "", "checked": False},
        ]

    def fake_close(_k, tid):
        closed.append(tid)

    monkeypatch.setattr(ts, "fetch_all_tasks_rest_v2", fake_fetch)
    monkeypatch.setattr(ts, "close_task_rest_v2", fake_close)

    n, _hint, log = ts.janitor_auto_archive_fluff("k")
    assert n == 1
    assert closed == ["99"]
    assert log and log[0]["task_id"] == "99"
    assert "newsletter" in log[0]["title"].lower()
