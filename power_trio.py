"""
Power Trio: Todoist via todoist_service; Gemini for The Plan (3 steps) and Quick Execution.
"""

from __future__ import annotations

import json
import re
from typing import Any, List

from todoist_service import (
    MAX_TASKS_RANK,
    close_task_rest_v2,
    fetch_all_tasks_rest_v2,
    fetch_todoist_projects,
    gemini_rank_tasks,
    normalize_power_task,
    rank_tasks_for_power_trio,
    save_ranked_cache,
    validate_and_fill_order,
)

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None  # type: ignore

# Re-export for callers that imported from power_trio.
__all__ = [
    "MAX_TASKS_RANK",
    "close_task_rest_v2",
    "fetch_all_tasks_rest_v2",
    "fetch_todoist_projects",
    "gemini_rank_tasks",
    "normalize_power_task",
    "rank_tasks_for_power_trio",
    "save_ranked_cache",
    "validate_and_fill_order",
    "split_substrings_csv",
    "gemini_the_plan_three_steps",
    "gemini_quick_execution",
    "gemini_tactical_micro_steps",
]


def split_substrings_csv(s: str) -> List[str]:
    if not s or not str(s).strip():
        return []
    import re as _re

    return [x.strip() for x in _re.split(r"[,;]", s) if x.strip()]


def gemini_the_plan_three_steps(
    genai_module: Any,
    model_name: str,
    task_title: str,
    task_description: str,
) -> str:
    model = genai_module.GenerativeModel(model_name)
    prompt = f"""Bias toward Action. Output EXACTLY three numbered lines (1. 2. 3.).

Task: {task_title}
Notes: {(task_description or "")[:500]}

Rules:
- Forbidden openings on any step: Research, Think about, Consider, Look into, Explore.
- Each step must start with a concrete imperative: prefer Open [Doc], Draft [Email], Schedule [Meeting]; otherwise Send, Call, Ship, Log, Pay, Run, Lift, etc.
- First move is always touchable (document, calendar, message, iron) — not cognition theater.

Return only the three numbered lines, no title."""
    resp = model.generate_content(prompt)
    return (resp.text or "").strip()


def gemini_quick_execution(
    genai_module: Any,
    model_name: str,
    task_title: str,
    task_description: str,
) -> str:
    model = genai_module.GenerativeModel(model_name)
    prompt = f"""Task: {task_title}
Notes: {(task_description or "")[:500]}

If this is clearly a communication task (email, DM, reply, send), return EXACTLY two sentences as the draft.
Otherwise return EXACTLY three short numbered steps (how-to). No preamble."""
    resp = model.generate_content(prompt)
    return (resp.text or "").strip()


def _extract_json_object(text: str) -> Any:
    t = (text or "").strip()
    if not t:
        return None
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", t)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                return None
    return None


def gemini_tactical_micro_steps(
    genai_module: Any,
    model_name: str,
    task_title: str,
    task_description: str,
) -> List[str]:
    """Three imperative micro-steps per Power Trio slot (Rugged Executive tone). Returns 0–3 strings."""
    model = genai_module.GenerativeModel(model_name)
    prompt = f"""You write in a Rugged Executive voice: direct, blunt, high-agency. No hedging, therapy talk, or filler.

Task: {task_title}
Notes: {(task_description or "")[:500]}

Return ONLY valid JSON with this exact shape:
{{"steps":["...","...","..."]}}

Rules for each string in "steps":
- Exactly 3 entries.
- Each is 2–6 words, imperative verb first (e.g. "Block 90m deep work", "Send the deck", "Kill the inbox tail").
- Physically doable today; no "consider", "think about", "research"."""

    try:
        from google.generativeai.types import GenerationConfig

        cfg = GenerationConfig(temperature=0.25, max_output_tokens=256, response_mime_type="application/json")
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
