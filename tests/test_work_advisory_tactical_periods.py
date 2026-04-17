"""Tactical brief normalization (morning/afternoon/evening + legacy flat)."""

from api.services.work_advisory_store import (
    normalize_tactical_brief_to_periods,
    tactical_brief_has_content,
)


def test_legacy_flat_maps_to_morning_only():
    raw = {"fragmentation": "a", "kill_zone": "b", "priority": "c"}
    out = normalize_tactical_brief_to_periods(raw)
    assert out["morning"] == {"fragmentation": "a", "kill_zone": "b", "priority": "c"}
    assert out["afternoon"]["fragmentation"] == ""
    assert out["evening"]["priority"] == ""


def test_nested_periods_merge():
    raw = {
        "morning": {"fragmentation": "m1", "kill_zone": "", "priority": ""},
        "afternoon": {"fragmentation": "", "kill_zone": "a1", "priority": ""},
        "evening": {"fragmentation": "", "kill_zone": "", "priority": "e1"},
    }
    out = normalize_tactical_brief_to_periods(raw)
    assert out["morning"]["fragmentation"] == "m1"
    assert out["afternoon"]["kill_zone"] == "a1"
    assert out["evening"]["priority"] == "e1"


def test_tactical_brief_has_content_any_period():
    p = normalize_tactical_brief_to_periods({"fragmentation": "x", "kill_zone": "", "priority": ""})
    assert tactical_brief_has_content(p) is True
    q = normalize_tactical_brief_to_periods({})
    assert tactical_brief_has_content(q) is False
