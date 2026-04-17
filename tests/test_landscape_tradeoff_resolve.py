"""Per-overlap landscape resolution (planning truth only)."""

from __future__ import annotations

from datetime import datetime, timedelta

from api.services.landscape_tradeoff_resolve import (
    apply_overlap_decisions_to_landscape,
    overlap_answer_key,
    stable_overlap_id,
)


def _tz():
    return datetime.now().astimezone().tzinfo


def test_stable_overlap_id_deterministic():
    tz = _tz()
    ov = {
        "start_iso": datetime(2026, 6, 1, 10, 0, tzinfo=tz).isoformat(),
        "end_iso": datetime(2026, 6, 1, 10, 30, tzinfo=tz).isoformat(),
        "start_a_iso": datetime(2026, 6, 1, 9, 30, tzinfo=tz).isoformat(),
        "end_a_iso": datetime(2026, 6, 1, 10, 30, tzinfo=tz).isoformat(),
        "start_b_iso": datetime(2026, 6, 1, 10, 0, tzinfo=tz).isoformat(),
        "end_b_iso": datetime(2026, 6, 1, 11, 0, tzinfo=tz).isoformat(),
        "title_a": "Meeting A",
        "title_b": "Meeting B",
        "source_a": "google",
        "source_b": "work_screenshot",
    }
    assert stable_overlap_id(ov) == stable_overlap_id(ov)


def test_apply_overlap_prioritize_a_removes_b():
    tz = _tz()
    t0 = datetime(2026, 6, 2, 14, 0, tzinfo=tz)
    landscape = [
        {
            "start_iso": t0.isoformat(),
            "title": "Alpha",
            "source": "google",
            "source_kind": "personal_google",
        },
        {
            "start_iso": t0.isoformat(),
            "title": "Beta",
            "source": "google",
            "source_kind": "work_screenshot",
        },
    ]
    overlaps = [
        {
            "start_iso": t0.isoformat(),
            "end_iso": (t0 + timedelta(minutes=30)).isoformat(),
            "title_a": "Alpha",
            "title_b": "Beta",
            "source_a": "google",
            "source_b": "work_screenshot",
            "start_a_iso": t0.isoformat(),
            "end_a_iso": (t0 + timedelta(hours=1)).isoformat(),
            "start_b_iso": t0.isoformat(),
            "end_b_iso": (t0 + timedelta(hours=1)).isoformat(),
        }
    ]
    oid = stable_overlap_id(overlaps[0])
    overlaps[0]["id"] = oid
    answers = {overlap_answer_key(oid): "a"}
    out = apply_overlap_decisions_to_landscape(landscape, overlaps, answers)
    titles = [r["title"] for r in out]
    assert titles == ["Alpha"]


def test_apply_overlap_undecided_keeps_both():
    tz = _tz()
    t0 = datetime(2026, 6, 3, 11, 0, tzinfo=tz)
    landscape = [
        {
            "start_iso": t0.isoformat(),
            "title": "One",
            "source": "google",
            "source_kind": "personal_google",
        },
        {
            "start_iso": t0.isoformat(),
            "title": "Two",
            "source": "personal",
            "source_kind": "personal_ics",
        },
    ]
    overlaps = [
        {
            "start_iso": t0.isoformat(),
            "end_iso": (t0 + timedelta(minutes=20)).isoformat(),
            "title_a": "One",
            "title_b": "Two",
            "source_a": "google",
            "source_b": "personal",
            "start_a_iso": t0.isoformat(),
            "end_a_iso": (t0 + timedelta(minutes=30)).isoformat(),
            "start_b_iso": t0.isoformat(),
            "end_b_iso": (t0 + timedelta(minutes=30)).isoformat(),
        }
    ]
    oid = stable_overlap_id(overlaps[0])
    overlaps[0]["id"] = oid
    answers = {overlap_answer_key(oid): "undecided"}
    out = apply_overlap_decisions_to_landscape(landscape, overlaps, answers)
    assert len(out) == 2
