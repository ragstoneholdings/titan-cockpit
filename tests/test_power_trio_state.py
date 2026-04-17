"""Per-day Power Trio disk state (v2) isolation."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

import todoist_service as ts

from api.services import power_trio_state as pts


@pytest.fixture(autouse=True)
def _tmp_ranked_cache(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(ts, "RANKED_CACHE_PATH", tmp_path / "ranked_cache.json")


@pytest.fixture
def isolated_state_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    p = tmp_path / "cockpit_power_trio_state.json"
    monkeypatch.setattr(pts, "STATE_PATH", p)
    return p


def _seed_three_tasks() -> dict:
    return {
        "a": {"id": "a", "content": "Task A", "description": "", "project_name": "P", "priority": 4, "due_date": ""},
        "b": {"id": "b", "content": "Task B", "description": "", "project_name": "P", "priority": 3, "due_date": ""},
        "c": {"id": "c", "content": "Task C", "description": "", "project_name": "P", "priority": 2, "due_date": ""},
    }


def test_rank_tasks_for_day_writes_separate_day_buckets(isolated_state_path: Path) -> None:
    d1 = date(2026, 3, 2)
    d2 = date(2026, 3, 9)
    st = pts._empty_state()
    st["tasks_by_id"] = _seed_three_tasks()
    pts.save_state(st)

    pts.rank_tasks_for_day(d1)
    pts.rank_tasks_for_day(d2)
    st2 = pts.load_state()
    b1 = st2["days"][d1.isoformat()]
    b2 = st2["days"][d2.isoformat()]
    assert isinstance(b1.get("ranked_ids"), list) and b1["ranked_ids"]
    assert isinstance(b2.get("ranked_ids"), list) and b2["ranked_ids"]
    assert b1.get("last_rank_iso")
    assert b2.get("last_rank_iso")


def test_trio_payload_reads_only_requested_day_bucket(isolated_state_path: Path) -> None:
    d1 = date(2026, 4, 1)
    d2 = date(2026, 4, 2)
    st = pts._empty_state()
    st["tasks_by_id"] = _seed_three_tasks()
    st.setdefault("days", {})
    st["days"][d1.isoformat()] = {
        "ranked_ids": ["a", "b", "c"],
        "rank_warning": "",
        "last_rank_iso": "2026-04-01T12:00:00+00:00",
        "tactical_steps_by_task_id": {},
    }
    st["days"][d2.isoformat()] = {
        "ranked_ids": ["c", "b", "a"],
        "rank_warning": "",
        "last_rank_iso": "2026-04-02T12:00:00+00:00",
        "tactical_steps_by_task_id": {},
    }
    pts.save_state(st)

    v1 = pts.trio_payload(st, day=d1)
    v2 = pts.trio_payload(st, day=d2)
    assert [s["task_id"] for s in v1["slots"]] == ["a", "b", "c"]
    assert [s["task_id"] for s in v2["slots"]] == ["c", "b", "a"]
    assert v1["recon_day"] == d1.isoformat()
    assert v2["recon_day"] == d2.isoformat()


def test_complete_task_only_mutates_requested_day_bucket(
    isolated_state_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(pts, "todoist_api_key", lambda: "test-key")
    monkeypatch.setattr(
        "api.services.power_trio_state.todoist_service.close_task_rest_v2",
        lambda *_a, **_k: None,
    )

    d1 = date(2026, 5, 10)
    d2 = date(2026, 5, 11)
    st = pts._empty_state()
    st["tasks_by_id"] = _seed_three_tasks()
    st.setdefault("days", {})
    st["days"][d1.isoformat()] = {
        "ranked_ids": ["a", "b", "c"],
        "rank_warning": "",
        "last_rank_iso": "",
        "tactical_steps_by_task_id": {},
    }
    st["days"][d2.isoformat()] = {
        "ranked_ids": ["a", "b", "c"],
        "rank_warning": "",
        "last_rank_iso": "",
        "tactical_steps_by_task_id": {},
    }
    pts.save_state(st)

    pts.complete_task("a", day=d1)
    st_after = pts.load_state()
    assert "a" not in st_after["days"][d1.isoformat()]["ranked_ids"]
    assert st_after["days"][d2.isoformat()]["ranked_ids"] == ["a", "b", "c"]
