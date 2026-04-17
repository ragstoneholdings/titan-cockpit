"""Gemini-assisted Hard Anchor nomination from a day's timed events."""

from __future__ import annotations

import json
import re
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from chief_of_staff.planning import to_local

GEMINI_ANCHOR_JOIN_TIMEOUT_SEC = 45


def _anchor_prompt_lines(anchors: List[Dict[str, Any]]) -> str:
    lines: List[str] = []
    for row in anchors:
        lines.append(
            json.dumps(
                {
                    "index": row["index"],
                    "start_local": row["start_local"],
                    "title": row["title"],
                },
                ensure_ascii=False,
            )
        )
    return "\n".join(lines)


def _gemini_nominate_inner(
    genai_module: Any,
    model_name: str,
    payload: List[Dict[str, Any]],
) -> Tuple[Optional[int], str]:
    model = genai_module.GenerativeModel(model_name)
    prompt = f"""You pick exactly ONE timed calendar event as the "Hard Anchor" for this local day —
the first immovable external commitment the user must prep for (syncs, exec reviews, firm-specific work).

Timed events (JSON lines, field "index" is 0-based position in chronological order):
{_anchor_prompt_lines(payload)}

Strong positive signals in the title (case-insensitive): Sync, Review, Ragstone, Google.
Prefer earlier-in-day anchors when multiple are equally strong.

Reply with ONLY valid JSON, no markdown:
{{"chosen_index": <int>, "reason": "<one short sentence>"}}"""
    try:
        resp = model.generate_content(prompt, generation_config={"temperature": 0.15})
    except TypeError:
        resp = model.generate_content(prompt)
    text = (getattr(resp, "text", None) or "").strip()
    m = re.search(r"\{[^{}]*\"chosen_index\"[^{}]*\}", text, re.DOTALL)
    if not m:
        m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None, text
    try:
        obj = json.loads(m.group())
        idx = obj.get("chosen_index")
        if isinstance(idx, bool) or idx is None:
            return None, text
        reason = str(obj.get("reason") or "").strip()
        return int(idx), reason or text
    except (json.JSONDecodeError, TypeError, ValueError):
        return None, text


def nominate_hard_anchor_index(
    genai_module: Any,
    model_name: str,
    anchors: List[Any],
) -> Tuple[Optional[int], str]:
    """
    Returns (chosen_index into anchors list, short reason or error snippet).
    Runs the model call in a thread with a join timeout.
    """
    if not genai_module or not anchors:
        return None, ""

    payload: List[Dict[str, Any]] = []
    for i, a in enumerate(anchors):
        st = getattr(a, "start", None)
        if not isinstance(st, datetime):
            continue
        loc = to_local(st)
        payload.append(
            {
                "index": i,
                "start_local": loc.strftime("%Y-%m-%d %H:%M"),
                "title": str(getattr(a, "title", "") or "(no title)"),
            }
        )

    result: List[Optional[Tuple[Optional[int], str]]] = [None]
    err: List[Optional[BaseException]] = [None]

    def target() -> None:
        try:
            result[0] = _gemini_nominate_inner(genai_module, model_name, payload)
        except BaseException as e:  # noqa: BLE001 — surface any API failure
            err[0] = e

    th = threading.Thread(target=target, daemon=True)
    th.start()
    th.join(timeout=GEMINI_ANCHOR_JOIN_TIMEOUT_SEC)
    if th.is_alive():
        return None, "Gemini anchor nomination timed out."
    if err[0] is not None:
        return None, str(err[0])
    out = result[0]
    if not out:
        return None, ""
    idx, text = out
    if idx is None:
        return None, text
    if idx < 0 or idx >= len(anchors):
        return None, text
    return idx, text
