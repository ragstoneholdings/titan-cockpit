"""Escalation Protocol Auditor — heuristics + optional Gemini firewall summary."""

from __future__ import annotations

from typing import Any, Dict, List

from integrations.env_loader import env_str


def _title_blob(t: Dict[str, Any]) -> str:
    return f"{t.get('content') or ''} {t.get('description') or ''}".lower()


def detect_firefighting_signals(by_id: Dict[str, Any]) -> List[str]:
    """Lightweight heuristics for manual admin / firefighting patterns."""
    raw = env_str("FIREFIGHTING_TITLE_SUBSTRINGS", "password reset,vpn,support ticket,access request,fix login,reset mfa,onboard,offboard,ticket #,incident,sev-")
    needles = [x.strip().lower() for x in raw.split(",") if x.strip()]
    if not needles:
        needles = ["password", "reset", "ticket", "access", "vpn"]
    seen: List[str] = []
    for t in by_id.values():
        if not isinstance(t, dict):
            continue
        blob = _title_blob(t)
        for n in needles:
            if n and n in blob:
                title = str(t.get("content") or "").strip()[:120]
                if title and title not in seen:
                    seen.append(title)
                break
        if len(seen) >= 8:
            break
    return seen


def gemini_firewall_audit_summary(signals: List[str]) -> str:
    """2–4 bullets when Gemini configured; else empty."""
    if not signals:
        return ""
    try:
        from api.services.gemini_runtime import configure_genai_from_env, gemini_model_name
    except Exception:
        return ""
    genai, err = configure_genai_from_env()
    if genai is None or err:
        return ""
    try:
        from google.generativeai.types import GenerationConfig
    except Exception:
        GenerationConfig = None  # type: ignore
    model = genai.GenerativeModel(gemini_model_name())
    lines = "\n".join(f"- {s}" for s in signals[:8])
    prompt = f"""You are a systems architect. These Todoist titles look like manual firefighting or repetitive admin:
{lines}

Return ONLY valid JSON: {{"bullets":["...","..."]}}
Rules: 2–4 short bullets. Each names the risk (single point of failure) and one automation or delegation next step. Rugged Executive tone; no therapy language."""
    try:
        if GenerationConfig:
            cfg = GenerationConfig(
                temperature=0.2,
                max_output_tokens=400,
                response_mime_type="application/json",
            )
            resp = model.generate_content(prompt, generation_config=cfg)
        else:
            resp = model.generate_content(prompt)
    except Exception:
        return ""
    text = (getattr(resp, "text", None) or "").strip()
    from power_trio import _extract_json_object

    data = _extract_json_object(text)
    if not isinstance(data, dict):
        return ""
    bullets = data.get("bullets")
    if not isinstance(bullets, list):
        return ""
    out = [str(b).strip() for b in bullets[:4] if str(b).strip()]
    return " ".join(f"• {b}" for b in out)
