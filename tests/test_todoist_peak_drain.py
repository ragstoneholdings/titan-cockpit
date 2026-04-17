"""Peak cognitive window post-sort for high-drain tasks."""

import todoist_service as ts


def test_apply_peak_cognitive_drain_guard_swaps_first():
    prof = {"high_drain_labels": ["#highdrain"], "high_drain_title_substrings": []}
    by_id = {
        "a": {"id": "a", "content": "Tax #highdrain", "description": "", "labels": []},
        "b": {"id": "b", "content": "Lift session", "description": "", "labels": []},
    }
    ranked = ["a", "b"]
    out = ts.apply_peak_cognitive_drain_guard(ranked, by_id, prof, 9)
    assert out[0] == "b"


def test_apply_peak_cognitive_demotes_second_slot():
    prof = {"high_drain_labels": [], "high_drain_title_substrings": ["admin"]}
    by_id = {
        "a": {"id": "a", "content": "Deep work block", "description": "", "labels": []},
        "b": {"id": "b", "content": "Admin paperwork", "description": "", "labels": []},
        "c": {"id": "c", "content": "Call vendor", "description": "", "labels": []},
    }
    ranked = ["a", "b", "c"]
    out = ts.apply_peak_cognitive_drain_guard(ranked, by_id, prof, 10)
    assert out[0] == "a"
    assert out[1] == "c"
    assert out[2] == "b"


def test_apply_peak_outside_window_noop():
    prof = {"high_drain_labels": ["x"], "high_drain_title_substrings": []}
    by_id = {"a": {"content": "x y", "description": "", "labels": []}}
    ranked = ["a"]
    assert ts.apply_peak_cognitive_drain_guard(ranked, by_id, prof, 14) == ranked
