"""Gemini-powered day planning/replanning for mobile assistant flows."""

from __future__ import annotations

import json
import uuid
from datetime import date
from typing import Any, Dict, List

from api.services.gemini_runtime import configure_genai_from_env, gemini_model_name


def _fallback_plan(day: date, context: Dict[str, Any], reason: str = "") -> Dict[str, Any]:
    sig = context.get("calendar_signals") if isinstance(context.get("calendar_signals"), dict) else {}
    g = sig.get("google") if isinstance(sig.get("google"), dict) else {}
    p = sig.get("personal") if isinstance(sig.get("personal"), dict) else {}
    summary = str(context.get("execution_day_summary") or "").strip()
    if not summary:
        summary = "Protect deep work first block, then execution admin closeout."
    return {
        "plan_id": str(uuid.uuid4()),
        "day": day.isoformat(),
        "summary": summary,
        "reason": reason,
        "generated_by": "fallback",
        "blocks": [
            {
                "id": "focus_1",
                "title": "Deep Work Block",
                "start_label": "08:00",
                "end_label": "09:30",
                "reason": "Create strategic output before reactive load.",
                "status": "planned",
            },
            {
                "id": "ops_1",
                "title": "Ops and Responses",
                "start_label": "11:00",
                "end_label": "12:00",
                "reason": "Close operational loops and inbox gate.",
                "status": "planned",
            },
            {
                "id": "review_1",
                "title": "Evening Review",
                "start_label": "17:30",
                "end_label": "18:00",
                "reason": "Capture wins, leaks, and tomorrow prep.",
                "status": "planned",
            },
        ],
        "calendar_observations": {
            "google_event_count": int(g.get("event_count") or 0),
            "personal_event_count": int(p.get("event_count") or 0),
        },
        "accepted": False,
    }


def _extract_json_payload(text: str) -> Dict[str, Any] | None:
    raw = text.strip()
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        i = raw.find("{")
        j = raw.rfind("}")
        if i < 0 or j < i:
            return None
        try:
            data = json.loads(raw[i : j + 1])
        except json.JSONDecodeError:
            return None
    return data if isinstance(data, dict) else None


def generate_day_plan(
    *,
    day: date,
    context: Dict[str, Any],
    objective: str = "",
    reason: str = "",
) -> Dict[str, Any]:
    genai, err = configure_genai_from_env()
    if genai is None:
        return _fallback_plan(day, context, reason=err or reason)

    model = genai.GenerativeModel(gemini_model_name())
    prompt = f"""You are an executive assistant planner.
Return ONLY JSON with shape:
{{
  "summary":"...",
  "blocks":[
    {{"id":"...", "title":"...", "start_label":"HH:MM", "end_label":"HH:MM", "reason":"...", "status":"planned"}}
  ]
}}

Context:
- day: {day.isoformat()}
- objective: {objective}
- reason: {reason}
- cockpit_summary: {context.get("execution_day_summary", "")}
- runway: {json.dumps(context.get("runway", {}), ensure_ascii=False)}
- schedule_day_signals: {json.dumps(context.get("schedule_day_signals", {}), ensure_ascii=False)}
- calendar_signals: {json.dumps(context.get("calendar_signals", {}), ensure_ascii=False)}
- sentry_state: {context.get("integrity_sentry_state", "NOMINAL")}

Rules:
- 3 to 6 blocks.
- concise executive tone.
- no markdown.
"""
    try:
        resp = model.generate_content(prompt)
        payload = _extract_json_payload(str(getattr(resp, "text", "") or ""))
    except Exception:
        payload = None

    if not payload:
        return _fallback_plan(day, context, reason="gemini_parse_fallback")

    blocks = payload.get("blocks")
    if not isinstance(blocks, list) or not blocks:
        return _fallback_plan(day, context, reason="gemini_empty_blocks")
    out_blocks: List[Dict[str, Any]] = []
    for i, b in enumerate(blocks[:6], start=1):
        if not isinstance(b, dict):
            continue
        out_blocks.append(
            {
                "id": str(b.get("id") or f"block_{i}"),
                "title": str(b.get("title") or f"Block {i}"),
                "start_label": str(b.get("start_label") or ""),
                "end_label": str(b.get("end_label") or ""),
                "reason": str(b.get("reason") or ""),
                "status": str(b.get("status") or "planned"),
            }
        )
    if not out_blocks:
        return _fallback_plan(day, context, reason="gemini_sanitized_empty")
    return {
        "plan_id": str(uuid.uuid4()),
        "day": day.isoformat(),
        "summary": str(payload.get("summary") or ""),
        "reason": reason,
        "generated_by": "gemini",
        "blocks": out_blocks,
        "accepted": False,
    }


def replan_with_drift(
    *,
    day: date,
    context: Dict[str, Any],
    drift_signals: List[str],
    reason: str = "",
) -> Dict[str, Any]:
    reason_line = reason.strip() or "drift_detected"
    if drift_signals:
        reason_line = f"{reason_line}; " + " | ".join(drift_signals[:4])
    return generate_day_plan(day=day, context=context, objective="", reason=reason_line)
