"""Regression: calendar advisory JSON extraction must tolerate real model output shapes."""

from api.services.calendar_advisory_gemini import _extract_json_object


def test_extract_json_brace_inside_string_value():
    raw = '{"title": "Discuss } tradeoffs", "advisory_events": []}'
    out = _extract_json_object(raw)
    assert out.get("title") == "Discuss } tradeoffs"
    assert out.get("advisory_events") == []


def test_extract_json_trailing_prose_after_object():
    raw = '{"visibility": "unclear", "notes": "ok"}\nThanks!'
    out = _extract_json_object(raw)
    assert out.get("visibility") == "unclear"


def test_extract_json_markdown_fence():
    raw = '```json\n{"recon_day": "2026-04-01", "x": 1}\n```'
    out = _extract_json_object(raw)
    assert out.get("recon_day") == "2026-04-01"
    assert out.get("x") == 1


def test_extract_json_empty_returns_empty_dict():
    assert _extract_json_object("") == {}
    assert _extract_json_object("no brace") == {}
