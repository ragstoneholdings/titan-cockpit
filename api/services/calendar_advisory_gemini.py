"""Gemini vision — work calendar screenshots → structured advisory + landscape rows."""

from __future__ import annotations

import io
import json
import logging
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

from google.generativeai.types import GenerationConfig

from api.services.advisory_time import landscape_rows_from_advisory_events
from api.services.gemini_runtime import configure_genai_from_env, gemini_model_name
from api.services.work_advisory_store import (
    _notes_imply_week_view,
    normalize_tactical_brief_to_periods,
    tactical_brief_has_content,
)

logger = logging.getLogger(__name__)

_MAX_VISION_EDGE_PX = 2048

_WEEKDAY = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)


def _weekday_date_in_iso_week(recon_day: date, weekday_name: str) -> Optional[date]:
    """Calendar date for `weekday_name` in the same Mon–Sun ISO week as `recon_day`."""
    name = weekday_name.strip().title()
    if name not in _WEEKDAY:
        return None
    idx = _WEEKDAY.index(name)
    mon = recon_day - timedelta(days=recon_day.weekday())
    return mon + timedelta(days=idx)


def _events_imply_distinct_weekday_columns(events: List[Dict[str, Any]]) -> bool:
    """True when the model named ≥2 different weekdays (often repeats one column_date_iso by mistake)."""
    seen: set[str] = set()
    for e in events:
        cw = str(e.get("column_weekday") or "").strip().title()
        if cw in _WEEKDAY:
            seen.add(cw)
    return len(seen) >= 2


def _flatten_advisory_events_by_date(raw: Any, _recon_day: date) -> List[Dict[str, Any]]:
    """
    Model may return `advisory_events_by_date`: { \"YYYY-MM-DD\": [ event, ... ], ... }.
    Keys are the printed column dates; server fills column_date_iso / column_weekday on each row.
    Week filtering happens later in `_filter_advisory_events_same_iso_week` / recon-day filters.
    """
    if not isinstance(raw, dict) or not raw:
        return []
    out: List[Dict[str, Any]] = []
    for key, val in raw.items():
        ds_key = str(key).strip()
        if len(ds_key) >= 10:
            ds_key = ds_key[:10]
        try:
            d = date.fromisoformat(ds_key)
        except ValueError:
            logger.warning("calendar advisory: skip invalid advisory_events_by_date key %r", key)
            continue
        wname = _WEEKDAY[d.weekday()]
        if isinstance(val, dict):
            val = [val]
        if not isinstance(val, list):
            logger.warning(
                "calendar advisory: skip advisory_events_by_date value for %s (expected array or object)",
                ds_key,
            )
            continue
        for ev in val:
            if not isinstance(ev, dict):
                continue
            e2 = dict(ev)
            e2["column_date_iso"] = d.isoformat()
            e2["column_weekday"] = wname
            out.append(e2)
    return out


def _apply_advisory_events_by_date(data: Dict[str, Any], recon_day: date) -> bool:
    """
    If `advisory_events_by_date` flattens to at least one row, merge into `advisory_events`.
    Rows from buckets win; remaining flat `advisory_events` entries are appended (deduped by title+time).
    Returns True when bucketed rows were merged.
    """
    raw = data.get("advisory_events_by_date")
    flat = _flatten_advisory_events_by_date(raw, recon_day)
    if not flat:
        return False
    legacy = [e for e in (data.get("advisory_events") or []) if isinstance(e, dict)]
    if legacy:
        seen = {(str(e.get("title") or ""), str(e.get("start_local_guess") or "")) for e in flat}
        for e in legacy:
            k = (str(e.get("title") or ""), str(e.get("start_local_guess") or ""))
            if k not in seen:
                flat.append(e)
                seen.add(k)
    data["advisory_events"] = flat
    return True


def _normalize_week_column_dates(
    recon_day: date, events: List[Dict[str, Any]], week_viewish: bool
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Align `column_date_iso` with `column_weekday` when the model repeats one printed date
    across multiple weekday columns, or when the printed date's weekday disagrees with
    `column_weekday`. Returns (events, rows_adjusted_count).
    """
    if not events:
        return events, 0

    first_iso: Optional[str] = None
    same_iso = True
    for e in events:
        c = str(e.get("column_date_iso") or "").strip()
        if len(c) >= 10:
            c = c[:10]
        else:
            same_iso = False
            first_iso = None
            break
        if first_iso is None:
            first_iso = c
        elif c != first_iso:
            same_iso = False
            break

    weekdays_seen: set[str] = set()
    for e in events:
        cw = str(e.get("column_weekday") or "").strip().title()
        if cw in _WEEKDAY:
            weekdays_seen.add(cw)

    force_remap = bool(same_iso and first_iso is not None and len(weekdays_seen) >= 2)

    adjusted = 0
    out: List[Dict[str, Any]] = []
    for e in events:
        e2 = dict(e)
        cw = str(e2.get("column_weekday") or "").strip().title()
        if cw not in _WEEKDAY:
            out.append(e2)
            continue
        target = _weekday_date_in_iso_week(recon_day, cw)
        if target is None:
            out.append(e2)
            continue

        col = str(e2.get("column_date_iso") or "").strip()
        d0: Optional[date] = None
        if len(col) >= 10:
            col = col[:10]
            try:
                d0 = date.fromisoformat(col)
            except ValueError:
                d0 = None

        should_set = False
        if d0 is None:
            should_set = week_viewish
        elif force_remap:
            should_set = True
        elif d0.weekday() != target.weekday():
            should_set = True

        prev_iso = str(e2.get("column_date_iso") or "").strip()[:10]
        if should_set and prev_iso != target.isoformat():
            e2["column_date_iso"] = target.isoformat()
            adjusted += 1
        out.append(e2)
    return out, adjusted


def _strip_markdown_fence(text: str) -> str:
    t = (text or "").strip()
    if not t.startswith("```"):
        return t
    lines = t.split("\n")
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _extract_json_object(text: str) -> Dict[str, Any]:
    """
    Parse the first top-level JSON object from model text.

    Uses json.JSONDecoder.raw_decode so `}` inside string values does not truncate the object
    (the legacy brace-counter incorrectly closed on braces inside strings).
    """
    text = _strip_markdown_fence((text or "").strip())
    if not text:
        return {}
    start = text.find("{")
    if start < 0:
        return {}
    try:
        obj, _end = json.JSONDecoder().raw_decode(text, start)
        return obj if isinstance(obj, dict) else {}
    except json.JSONDecodeError:
        return {}


def _safe_gemini_response_text(resp: Any) -> Tuple[str, Dict[str, Any]]:
    """Read model JSON text without assuming `response.text` works (SDK can raise)."""
    meta: Dict[str, Any] = {
        "text_source": None,
        "finish_reason": None,
        "parts_n": 0,
        "text_exc": None,
        "parts_exc": None,
    }
    try:
        t = resp.text  # type: ignore[union-attr]
        if isinstance(t, str) and t.strip():
            meta["text_source"] = "resp.text"
            return t.strip(), meta
    except Exception as e:
        meta["text_exc"] = f"{type(e).__name__}: {e}"[:400]
    try:
        cands = getattr(resp, "candidates", None) or []
        if not cands:
            return "", meta
        c0 = cands[0]
        meta["finish_reason"] = repr(getattr(c0, "finish_reason", None))
        content = getattr(c0, "content", None)
        parts = list(getattr(content, "parts", []) or [])
        meta["parts_n"] = len(parts)
        chunks: List[str] = []
        for p in parts:
            pt = getattr(p, "text", None)
            if isinstance(pt, str) and pt:
                chunks.append(pt)
        joined = "\n".join(chunks).strip()
        if joined:
            meta["text_source"] = "parts_join"
            return joined, meta
    except Exception as e:
        meta["parts_exc"] = f"{type(e).__name__}: {e}"[:400]
    return "", meta


def _pil_image_for_gemini(raw: bytes) -> Any:
    from PIL import Image

    im = Image.open(io.BytesIO(raw))
    im = im.convert("RGB")
    w, h = im.size
    m = max(w, h)
    if m > _MAX_VISION_EDGE_PX:
        scale = _MAX_VISION_EDGE_PX / m
        nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
        try:
            resample = Image.Resampling.LANCZOS
        except AttributeError:
            resample = Image.LANCZOS  # type: ignore[attr-defined]
        im = im.resize((nw, nh), resample)
    return im


def _blocked_reason(resp: Any) -> str:
    try:
        pf = getattr(resp, "prompt_feedback", None)
        if pf and getattr(pf, "block_reason", None):
            return str(pf.block_reason)
    except Exception:
        pass
    return ""


def _filter_advisory_events_for_recon_day(recon_day: date, events: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
    """
    Drop events whose optional column metadata proves they belong to another calendar day.
    When the model omits metadata, keep the row (backward compatible).
    """
    ds = recon_day.isoformat()
    kept: List[Dict[str, Any]] = []
    dropped = 0
    for e in events:
        if not isinstance(e, dict):
            continue
        col = str(e.get("column_date_iso") or "").strip()
        if col and col != ds:
            dropped += 1
            continue
        cw = e.get("column_weekday")
        if isinstance(cw, str) and cw.strip():
            w = cw.strip().title()
            if w in _WEEKDAY and _WEEKDAY.index(w) != recon_day.weekday():
                dropped += 1
                continue
        kept.append(e)
    return kept, dropped


def _filter_advisory_events_same_iso_week(
    recon_day: date, events: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Week / multi-day screenshot: keep events whose printed column date falls in the same
    Mon–Sun ISO week as `recon_day` (the upload anchor). Drops events outside that week or
    with unparseable column_date_iso. Events without column_date_iso are dropped (week view
    requires per-column dates).
    """
    week0 = recon_day - timedelta(days=recon_day.weekday())
    week6 = week0 + timedelta(days=6)
    kept: List[Dict[str, Any]] = []
    dropped = 0
    for e in events:
        if not isinstance(e, dict):
            continue
        col = str(e.get("column_date_iso") or "").strip()
        if len(col) >= 10:
            col = col[:10]
        if len(col) == 10:
            try:
                cd = date.fromisoformat(col)
            except ValueError:
                dropped += 1
                continue
            if week0 <= cd <= week6:
                kept.append(e)
            else:
                dropped += 1
        else:
            dropped += 1
    return kept, dropped


def analyze_calendar_screenshots_advisory(
    image_bytes_list: List[bytes],
    recon_day: date,
) -> Tuple[Dict[str, Any], str]:
    """
    Vision OCR + reasoning. Returns (payload, warning).

    `payload` includes: recon_day, advisory_events, suggested_anchor, notes,
    visibility, time_coaching, is_advisory_only, landscape_rows (normalized server-side).
    """
    genai, err = configure_genai_from_env()
    if genai is None:
        return _failure_payload(recon_day, err or "Gemini not configured."), err or ""
    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        return _failure_payload(recon_day, "Install Pillow for image analysis."), "Install Pillow."

    ds = recon_day.isoformat()
    weekday = _WEEKDAY[recon_day.weekday()]
    human = f"{recon_day.strftime('%B')} {recon_day.day}, {recon_day.year}"
    is_weekend = recon_day.weekday() >= 5

    prompt = f"""You read **work calendar screenshot(s)**. The user selected this recon date in the app:

**Target calendar day:** {ds} ({weekday}) — {human}

Your job:
1. **Identify the UI:** single-day agenda, one column, OR **week / multi-day** (multiple date columns visible).
2. **List timed calendar blocks** (meetings, holds, focus blocks):
   - **Week / multi-day (preferred):** Use **`advisory_events_by_date`**: an object whose **keys** are printed dates `YYYY-MM-DD` (one key per visible day column) and **values** are arrays of events **only** for that column. Inner events may omit `column_date_iso` (the key is authoritative). Example: `"2026-04-13": [{{"title":"Standup","start_local_guess":"09:00",...}}], "2026-04-14": [...]`. This structure prevents mixing days.
   - **Single-day or one visible column for {ds}:** Either one key in `advisory_events_by_date` **or** use flat `advisory_events` for blocks that belong **only** to **{ds}**.
   - **Legacy flat list:** If you do not use `advisory_events_by_date`, put everything in `advisory_events` and each event MUST use that column's **printed** `column_date_iso` and `column_weekday`; `start_local_guess` is the time in **that** column. Never copy **{ds}** onto another column's events.
3. **Tactical brief (mandatory):** Fill `tactical_brief` with **morning**, **afternoon**, and **evening** objects. Each object has exactly three one-line fields. Voice: **Rugged Executive** — strategic thought partner: blunt tradeoffs, calendar politics, what to kill vs defend. No therapy tone, no apologies, no generic productivity advice.
   - **morning** (`fragmentation`, `kill_zone`, `priority`): opening the day — first commitments, commute, who gets your first real block.
   - **afternoon** (`fragmentation`, `kill_zone`, `priority`): execution window — energy, politics, defend vs kill.
   - **evening** (`fragmentation`, `kill_zone`, `priority`): close — carryovers, tomorrow setup, what not to drag home.
   Each field: `fragmentation` = cost (named meetings/holds, times); `kill_zone` = one block worth defending (times + title) or sacrifice to create one; `priority` = single slip that owns that part of the day + prep move before it.
   **Forbidden:** vague lines unless tied to a **named** calendar block or time.
4. Set `time_coaching` to **""** (empty string). Narrative prose is deprecated; all coaching goes in `tactical_brief`.

Rules:
- Weekend: if the crop is Mon–Fri only and **{weekday}** is Sat/Sun, set `visibility` to `recon_day_not_in_frame` and **do not** invent events for **{ds}**.
- If **{ds}** is visible and has no meetings, `advisory_events` may be empty and `visibility` is `recon_day_visible`.
- Times are **local**. Prefer 24-hour **HH:MM** in `start_local_guess` / `end_local_guess`; 12-hour with AM/PM is OK.
- `confidence` per event: 0–1 (OCR certainty).
- **Week / multi-day views (critical):** Do **not** read times from the wrong day column. Each event's `column_date_iso` / `column_weekday` must match the **printed header** of the column that block sits under — **not** the upload recon day unless they match. If you cannot read a column's printed date, **omit** that block. **Never** label a Tuesday-column block with Monday's date. **Never** set every event's `column_weekday` to Monday when multiple weekday columns are visible — each column has its own weekday name.

Return **only** a JSON object (no markdown) with this shape:
{{
  "recon_day": "{ds}",
  "visibility": "recon_day_visible" | "recon_day_not_in_frame" | "unclear",
  "advisory_events_by_date": {{ "YYYY-MM-DD": [ {{"start_local_guess": "HH:MM", "end_local_guess": "HH:MM or null", "title": "string", "confidence": 0.0}} ] }},
  "advisory_events": [
    {{"start_local_guess": "HH:MM", "end_local_guess": "HH:MM or null", "title": "string", "confidence": 0.0, "column_date_iso": "YYYY-MM-DD printed for that day column", "column_weekday": "Monday|...|Sunday"}}
  ],
  "suggested_anchor": {{"title": "string or null", "start_local_guess": "HH:MM or null", "reason": "short"}},
  "tactical_brief": {{
    "morning": {{"fragmentation": "one line", "kill_zone": "one line", "priority": "one line"}},
    "afternoon": {{"fragmentation": "one line", "kill_zone": "one line", "priority": "one line"}},
    "evening": {{"fragmentation": "one line", "kill_zone": "one line", "priority": "one line"}}
  }},
  "time_coaching": "",
  "notes": "One sentence: what part of the calendar UI you saw (e.g. Visible: week of Apr 6-12).",
  "is_advisory_only": true
}}

Context: {"weekend crop often hides Sat/Sun — say so in notes if relevant." if is_weekend else "Standard weekday work calendar."}"""

    model = genai.GenerativeModel(gemini_model_name())
    # Do not force response_mime_type=application/json with vision: it often yields empty or
    # invalid JSON vs. the same prompt without MIME coercion. We parse JSON from text instead.
    generation_config = GenerationConfig(
        temperature=0.2,
        max_output_tokens=8192,
    )

    parts: List[Any] = [prompt]
    for b in image_bytes_list:
        parts.append(_pil_image_for_gemini(b))

    try:
        resp = model.generate_content(parts, generation_config=generation_config)
    except Exception as e:
        logger.exception("calendar advisory vision call failed")
        err_s = f"{type(e).__name__}: {e}"
        return _failure_payload(
            recon_day,
            f"Vision call failed: {err_s[:400]}",
            extra_reason=err_s[:200],
        ), err_s[:500]

    if getattr(resp, "candidates", None) is None or len(resp.candidates) == 0:
        br = _blocked_reason(resp)
        msg = f"No model response (blocked or empty). {br}".strip()
        return _failure_payload(recon_day, msg), msg[:500]

    text, _text_meta = _safe_gemini_response_text(resp)
    data = _extract_json_object(text)
    if not data:
        logger.warning(
            "calendar advisory: unparseable JSON (text_len=%s finish=%s parts=%s)",
            len(text or ""),
            _text_meta.get("finish_reason"),
            _text_meta.get("parts_n"),
        )
        return {
            "recon_day": ds,
            "visibility": "unclear",
            "advisory_events": [],
            "suggested_anchor": {"title": None, "start_local_guess": None, "reason": "Unparseable JSON."},
            "time_coaching": "",
            "tactical_brief": {
                "morning": {"fragmentation": "", "kill_zone": "", "priority": ""},
                "afternoon": {"fragmentation": "", "kill_zone": "", "priority": ""},
                "evening": {"fragmentation": "", "kill_zone": "", "priority": ""},
            },
            "notes": (text or "")[:500],
            "is_advisory_only": True,
            "landscape_rows": [],
        }, "Unparseable JSON from model."

    data.setdefault("advisory_events", [])
    data.setdefault("suggested_anchor", {"title": None, "start_local_guess": None, "reason": ""})
    data.setdefault("notes", "")
    data.setdefault("time_coaching", "")
    data.setdefault(
        "tactical_brief",
        {
            "morning": {"fragmentation": "", "kill_zone": "", "priority": ""},
            "afternoon": {"fragmentation": "", "kill_zone": "", "priority": ""},
            "evening": {"fragmentation": "", "kill_zone": "", "priority": ""},
        },
    )
    data.setdefault("visibility", "unclear")
    data.setdefault("is_advisory_only", True)
    if not isinstance(data.get("suggested_anchor"), dict):
        data["suggested_anchor"] = {"title": None, "start_local_guess": None, "reason": ""}
    if not isinstance(data.get("advisory_events"), list):
        data["advisory_events"] = []

    data["recon_day"] = ds

    if _apply_advisory_events_by_date(data, recon_day):
        data["notes"] = (
            str(data.get("notes") or "").strip()
            + " [Server: merged advisory_events_by_date into per-row dates.]"
        ).strip()
        logger.info("calendar advisory: applied advisory_events_by_date bucketed events")

    events = [e for e in data["advisory_events"] if isinstance(e, dict)]
    notes_s = str(data.get("notes") or "")
    distinct_col_dates: set[str] = set()
    for e in events:
        c = str(e.get("column_date_iso") or "").strip()
        if len(c) >= 10:
            distinct_col_dates.add(c[:10])
    # Notes may omit "week of…" even when the model tagged multiple day columns correctly.
    # Also treat as week-style when the model named ≥2 weekdays but repeated one column_date_iso.
    week_viewish = (
        _notes_imply_week_view(notes_s)
        or len(distinct_col_dates) >= 2
        or _events_imply_distinct_weekday_columns(events)
    )
    events, col_fix_n = _normalize_week_column_dates(recon_day, events, week_viewish)
    if col_fix_n:
        data["notes"] = (
            str(data.get("notes") or "").strip()
            + " [Server: column_date_iso aligned to column_weekday within recon week.]"
        ).strip()
        logger.info("calendar advisory: aligned %s event column_date_iso from weekday labels", col_fix_n)
        distinct_col_dates = set()
        for e in events:
            c = str(e.get("column_date_iso") or "").strip()
            if len(c) >= 10:
                distinct_col_dates.add(c[:10])
        week_viewish = (
            _notes_imply_week_view(notes_s)
            or len(distinct_col_dates) >= 2
            or _events_imply_distinct_weekday_columns(events)
        )
    strict_warn = ""
    if week_viewish and events:
        with_col = sum(1 for e in events if str(e.get("column_date_iso") or "").strip())
        if with_col == 0:
            events = []
            strict_warn = (
                "Week view detected but no column_date_iso on any event — nothing saved. "
                "Re-analyze; the model must print each event's column date."
            )
            data["notes"] = (
                str(data.get("notes") or "")
                + " [Server: events discarded until column_date_iso is present for week/multi-day views.]"
            )
    data["advisory_events"] = events

    if week_viewish:
        events_f, dropped = _filter_advisory_events_same_iso_week(recon_day, events)
        if dropped:
            data["advisory_events"] = events_f
            extra = (
                f" Dropped {dropped} screenshot event(s) whose column_date_iso was outside "
                f"the ISO week of {ds} or missing."
            )
            data["notes"] = str(data.get("notes") or "") + extra
        warn = strict_warn
        if dropped:
            extra = f"{dropped} event(s) trimmed: outside recon week's column dates."
            warn = f"{warn} {extra}".strip() if warn else extra
    else:
        events_f, dropped = _filter_advisory_events_for_recon_day(recon_day, events)
        if dropped:
            data["advisory_events"] = events_f
            extra = (
                f" Dropped {dropped} screenshot event(s) whose printed column date/weekday "
                f"did not match recon day {ds}."
            )
            data["notes"] = str(data.get("notes") or "") + extra
        warn = strict_warn
        if dropped:
            extra = f"{dropped} event(s) removed: column date/weekday did not match {ds}."
            warn = f"{warn} {extra}".strip() if warn else extra
    data["landscape_rows"] = landscape_rows_from_advisory_events(recon_day, events_f)

    tb = normalize_tactical_brief_to_periods(data.get("tactical_brief"))
    data["tactical_brief"] = tb
    if tactical_brief_has_content(tb):
        data["time_coaching"] = ""

    data.pop("advisory_events_by_date", None)

    return data, warn


def _failure_payload(
    recon_day: date,
    notes: str,
    *,
    extra_reason: str = "",
) -> Dict[str, Any]:
    ds = recon_day.isoformat()
    return {
        "recon_day": ds,
        "visibility": "unclear",
        "advisory_events": [],
        "suggested_anchor": {
            "title": None,
            "start_local_guess": None,
            "reason": extra_reason or notes[:200],
        },
        "time_coaching": "",
        "tactical_brief": {
            "morning": {"fragmentation": "", "kill_zone": "", "priority": ""},
            "afternoon": {"fragmentation": "", "kill_zone": "", "priority": ""},
            "evening": {"fragmentation": "", "kill_zone": "", "priority": ""},
        },
        "notes": notes,
        "is_advisory_only": True,
        "landscape_rows": [],
    }
