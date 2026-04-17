"""Unit tests for Power Trio helpers."""

from power_trio import validate_and_fill_order


def test_validate_and_fill_order_preserves_extras():
    known = ["a", "b", "c"]
    ordered = ["c", "a"]
    out = validate_and_fill_order(ordered, known)
    assert out == ["c", "a", "b"]
