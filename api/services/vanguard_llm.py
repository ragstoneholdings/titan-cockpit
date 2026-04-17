"""Gemini helpers for Vanguard Cockpit (on-demand only)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import identity_store
from api.services.gemini_runtime import configure_genai_from_env, gemini_model_name
from integrations.env_loader import env_str
from power_trio import _extract_json_object


def _model():
    genai, err = configure_genai_from_env()
    if genai is None or err:
        return None, err or "Gemini not configured."
    return genai.GenerativeModel(gemini_model_name()), ""


def opportunity_cost_narrative(
    *,
    title: str,
    notes: str = "",
    estimated_minutes: Optional[int] = None,
) -> Dict[str, Any]:
    purpose = identity_store.load_identity_purpose()
    rstrat = env_str("POWER_RAGSTONE_STRATEGY", "")
    est = f"{estimated_minutes}m" if estimated_minutes is not None else "unknown"
    m, err = _model()
    if m is None:
        return {"ok": False, "error": err, "narrative": "", "cuts": []}
    prompt = f"""You challenge an executive's assumptions about taking on work. Life purpose (context): {(purpose or '')[:500]}
Ragstone strategy: {(rstrat or '')[:400]}

Proposed task title: {title[:500]}
Notes: {(notes or '')[:800]}
Estimated time: {est}

Return ONLY valid JSON:
{{"narrative":"one paragraph opportunity-cost framing","cuts":["short counterfactual 1","short cut 2","short cut 3"]}}

Tone: adversarial, logically brutal, no therapy language. Forbid hedging in "cuts" — each is an imperative alternative or kill."""
    try:
        from google.generativeai.types import GenerationConfig

        cfg = GenerationConfig(
            temperature=0.35,
            max_output_tokens=700,
            response_mime_type="application/json",
        )
        resp = m.generate_content(prompt, generation_config=cfg)
    except Exception:
        resp = m.generate_content(prompt)
    data = _extract_json_object(getattr(resp, "text", None) or "")
    if not isinstance(data, dict):
        return {"ok": False, "error": "Parse error.", "narrative": "", "cuts": []}
    cuts = data.get("cuts")
    if not isinstance(cuts, list):
        cuts = []
    return {
        "ok": True,
        "error": "",
        "narrative": str(data.get("narrative") or "").strip(),
        "cuts": [str(c).strip() for c in cuts[:5] if str(c).strip()],
    }


def windshield_triage(*, text: str, mode: str = "windshield") -> Dict[str, Any]:
    purpose = identity_store.load_identity_purpose()
    rstrat = env_str("POWER_RAGSTONE_STRATEGY", "")
    m, err = _model()
    if m is None:
        return {"ok": False, "error": err, "verdict": "road", "one_line_reason": ""}
    if mode == "utility_alarm":
        sys_add = (
            "UTILITY ALARM: reject emotional appeals and pathos. "
            "Verdict may be road, bug, or soft (soft = peacekeeping / agreeableness eroding sovereignty). "
            "one_line_reason must be cold and blunt."
        )
        verdict_hint = "road | bug | soft"
    else:
        sys_add = "Classify as Road (mission-critical) vs Bug (distraction / low leverage)."
        verdict_hint = "road | bug"
    prompt = f"""{sys_add}
Purpose: {(purpose or '')[:400]}
Strategy: {(rstrat or '')[:300]}

Text to classify:
{(text or '')[:4000]}

Return ONLY valid JSON with keys verdict and one_line_reason.
verdict must be one of: {verdict_hint}."""
    try:
        from google.generativeai.types import GenerationConfig

        cfg = GenerationConfig(
            temperature=0.2,
            max_output_tokens=200,
            response_mime_type="application/json",
        )
        resp = m.generate_content(prompt, generation_config=cfg)
    except Exception:
        resp = m.generate_content(prompt)
    data = _extract_json_object(getattr(resp, "text", None) or "")
    if not isinstance(data, dict):
        return {"ok": False, "error": "Parse error.", "verdict": "road", "one_line_reason": ""}
    v = str(data.get("verdict") or "road").lower()
    if mode != "utility_alarm" and v not in ("road", "bug"):
        v = "road"
    if mode == "utility_alarm" and v not in ("road", "bug", "soft"):
        v = "soft"
    return {
        "ok": True,
        "error": "",
        "verdict": v,
        "one_line_reason": str(data.get("one_line_reason") or "").strip()[:500],
    }


def past_in_the_past(*, text: str) -> Dict[str, Any]:
    m, err = _model()
    if m is None:
        return {"ok": False, "error": err, "rumination_score": 0.0, "reframe": ""}
    prompt = f"""The user may be using past failure to justify present avoidance. Text:
{(text or '')[:3000]}

Return ONLY valid JSON:
{{"rumination_score":0.0,"reframe":"one line forward-looking reframe using probability / next action, not therapy"}}

rumination_score is 0–1 how much past baggage distorts the present."""
    try:
        from google.generativeai.types import GenerationConfig

        cfg = GenerationConfig(
            temperature=0.25,
            max_output_tokens=250,
            response_mime_type="application/json",
        )
        resp = m.generate_content(prompt, generation_config=cfg)
    except Exception:
        resp = m.generate_content(prompt)
    data = _extract_json_object(getattr(resp, "text", None) or "")
    if not isinstance(data, dict):
        return {"ok": False, "error": "Parse error.", "rumination_score": 0.0, "reframe": ""}
    try:
        rs = float(data.get("rumination_score"))
    except (TypeError, ValueError):
        rs = 0.0
    rs = max(0.0, min(1.0, rs))
    return {
        "ok": True,
        "error": "",
        "rumination_score": rs,
        "reframe": str(data.get("reframe") or "").strip()[:500],
    }


def calendar_leanness(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """rows: title, start_iso, end_iso optional."""
    m, err = _model()
    if m is None:
        return {"ok": False, "error": err, "items": []}
    lines = []
    for r in rows[:40]:
        if not isinstance(r, dict):
            continue
        title = str(r.get("title") or "").strip()
        st = str(r.get("start_iso") or "")
        en = str(r.get("end_iso") or "")
        lines.append(f"- {st} → {en} | {title[:120]}")
    blob = "\n".join(lines) if lines else "(no meetings)"
    prompt = f"""Meetings for one day (read-only):
{blob}

Return ONLY valid JSON:
{{"items":[{{"title":"exact or shortened","fat_score":0.0,"extraction_plan_one_liner":"..."}}]}}

fat_score 0–1 (high = vague, no decision, passive). extraction_plan: async summary, 5m stand-up, or decline pattern — one short line."""
    try:
        from google.generativeai.types import GenerationConfig

        cfg = GenerationConfig(
            temperature=0.25,
            max_output_tokens=1200,
            response_mime_type="application/json",
        )
        resp = m.generate_content(prompt, generation_config=cfg)
    except Exception:
        resp = m.generate_content(prompt)
    data = _extract_json_object(getattr(resp, "text", None) or "")
    if not isinstance(data, dict):
        return {"ok": False, "error": "Parse error.", "items": []}
    items = data.get("items")
    out: List[Dict[str, Any]] = []
    if isinstance(items, list):
        for it in items[:12]:
            if not isinstance(it, dict):
                continue
            try:
                fs = float(it.get("fat_score"))
            except (TypeError, ValueError):
                fs = 0.0
            out.append(
                {
                    "title": str(it.get("title") or "")[:200],
                    "fat_score": max(0.0, min(1.0, fs)),
                    "extraction_plan_one_liner": str(it.get("extraction_plan_one_liner") or "").strip()[:300],
                }
            )
    out.sort(key=lambda x: -float(x.get("fat_score") or 0))
    return {"ok": True, "error": "", "items": out[:3]}
