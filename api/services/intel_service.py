"""Stricter Gemini micro-copy for Combat (slot #1) immediate physical actions."""

from __future__ import annotations

from typing import Any, List

from power_trio import _extract_json_object


def gemini_immediate_physical_steps(
    genai_module: Any,
    model_name: str,
    task_title: str,
    task_description: str,
    purpose: str,
) -> List[str]:
    """Three concrete first-body / first-object moves; falls back to empty on parse failure."""
    model = genai_module.GenerativeModel(model_name)
    prompt = f"""You write in a Rugged Executive voice: direct, blunt, high-agency.

Titan purpose (context only; do not quote verbatim):
{(purpose or "(not set)")[:400]}

Combat task (must execute today):
{task_title}
Notes: {(task_description or "")[:500]}

Return ONLY valid JSON:
{{"steps":["...","...","..."]}}

Rules for each string in "steps":
- Exactly 3 entries.
- Each starts with a physical or object-touch verb (Open, Walk, Dial, Draft, Ship, Pack, Drive, Block, Log, Pay).
- Forbidden anywhere: consider, research, think about, look into, explore, maybe, try to.
- Each step is one short imperative clause (under 12 words)."""

    try:
        from google.generativeai.types import GenerationConfig

        cfg = GenerationConfig(temperature=0.2, max_output_tokens=256, response_mime_type="application/json")
        resp = model.generate_content(prompt, generation_config=cfg)
    except Exception:
        resp = model.generate_content(prompt)

    data = _extract_json_object(getattr(resp, "text", None) or "")
    if not isinstance(data, dict):
        return []
    steps = data.get("steps")
    if not isinstance(steps, list):
        return []
    out: List[str] = []
    for x in steps[:3]:
        s = str(x).strip()
        if s:
            out.append(s[:120])
    return out[:3]
