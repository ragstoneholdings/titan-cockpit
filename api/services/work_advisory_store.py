"""Persist work-calendar screenshot advisory by recon day (merged into cockpit landscape)."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent.parent

_WEEKDAY = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)


def _notes_imply_week_view(notes: str) -> bool:
    """True when bundle notes describe a week or multi-day grid (must use per-column dates on rows)."""
    n = (notes or "").lower()
    return (
        "week view" in n
        or "week of" in n
        or "week-of" in n
        or "multi-day" in n
        or "multi day" in n
        or "multiple day" in n
        or "several day" in n
        or "multi-column" in n
        or "multicolumn" in n
        or "multiple column" in n
        or "mon-fri" in n
        or "mon–fri" in n
        or "work week" in n
        or "5-day" in n
        or "five day" in n
    )


def filter_work_landscape_rows_for_bundle(day: date, rows: List[Dict[str, Any]], bundle_notes: str) -> List[Dict[str, Any]]:
    """
    Drop work screenshot rows that cannot belong to this recon day.
    Week-view bundles without per-row column_date_iso are untrusted (legacy misaligned saves).
    """
    weekish = _notes_imply_week_view(bundle_notes)
    out: List[Dict[str, Any]] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        if weekish and not str(r.get("column_date_iso") or "").strip():
            continue
        col = str(r.get("column_date_iso") or "").strip()
        if len(col) >= 10:
            col = col[:10]
        if col and col != day.isoformat():
            continue
        cw = r.get("column_weekday")
        if isinstance(cw, str) and cw.strip():
            w = cw.strip().title()
            if w in _WEEKDAY and _WEEKDAY.index(w) != day.weekday():
                continue
        out.append(r)
    return out
WORK_CALENDAR_ADVISORY_PATH = ROOT / "work_calendar_advisory.json"


def _atomic_write_json(path: Path, payload: Dict[str, Any]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def load_bundle() -> Dict[str, Any]:
    if not WORK_CALENDAR_ADVISORY_PATH.is_file():
        return {"version": 1, "by_date": {}}
    try:
        raw = json.loads(WORK_CALENDAR_ADVISORY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"version": 1, "by_date": {}}
    if not isinstance(raw, dict):
        return {"version": 1, "by_date": {}}
    by_date = raw.get("by_date")
    if not isinstance(by_date, dict):
        by_date = {}
    return {"version": int(raw.get("version") or 1), "by_date": by_date}


_TB_LINE_KEYS = ("fragmentation", "kill_zone", "priority")
_TB_PERIODS = ("morning", "afternoon", "evening")


def _normalize_tactical_line_block(raw: Any) -> Dict[str, str]:
    if not isinstance(raw, dict):
        return {k: "" for k in _TB_LINE_KEYS}
    return {k: str(raw.get(k) or "").strip()[:240] for k in _TB_LINE_KEYS}


def normalize_tactical_brief_to_periods(raw: Any) -> Dict[str, Dict[str, str]]:
    """
    Canonical shape: morning / afternoon / evening, each with fragmentation, kill_zone, priority.
    Legacy flat tactical_brief (three keys at top level) maps into morning only.
    """
    empty_block = {k: "" for k in _TB_LINE_KEYS}
    base = {p: dict(empty_block) for p in _TB_PERIODS}
    if not isinstance(raw, dict):
        return base
    if any(p in raw for p in _TB_PERIODS):
        for p in _TB_PERIODS:
            base[p] = _normalize_tactical_line_block(raw.get(p))
        return base
    base["morning"] = _normalize_tactical_line_block(raw)
    return base


def tactical_brief_has_content(periods: Any) -> bool:
    if not isinstance(periods, dict):
        return False
    if any(p in periods for p in _TB_PERIODS):
        for p in _TB_PERIODS:
            block = periods.get(p)
            if isinstance(block, dict) and any(
                str(block.get(k) or "").strip() for k in _TB_LINE_KEYS
            ):
                return True
        return False
    return any(str(periods.get(k) or "").strip() for k in _TB_LINE_KEYS)


def _normalize_tactical_brief_dict(raw: Any) -> Dict[str, Dict[str, str]]:
    """JSON-serializable nested tactical brief for disk / API."""
    return normalize_tactical_brief_to_periods(raw)


def _week_iso_keys_containing(day: date) -> List[str]:
    """Monday–Sunday ISO keys for the calendar week that contains `day`."""
    mon = day - timedelta(days=day.weekday())
    return [(mon + timedelta(days=i)).isoformat() for i in range(7)]


def _saved_at_sort_key(entry: Dict[str, Any]) -> str:
    """ISO timestamps sort lexicographically; empty sorts last when reversed."""
    return str(entry.get("saved_at") or "").strip()


def _normalize_raw_landscape_rows(rows: Any) -> List[Dict[str, Any]]:
    if not isinstance(rows, list):
        return []
    out: List[Dict[str, Any]] = []
    for r in rows:
        if isinstance(r, dict) and r.get("start_iso") and r.get("title") is not None:
            item: Dict[str, Any] = {
                "start_iso": str(r["start_iso"]),
                "title": str(r["title"]),
                "source": str(r.get("source") or "google"),
                "source_kind": str(r.get("source_kind") or "work_screenshot"),
            }
            if str(r.get("column_date_iso") or "").strip():
                item["column_date_iso"] = str(r["column_date_iso"]).strip()
            if isinstance(r.get("column_weekday"), str) and str(r["column_weekday"]).strip():
                item["column_weekday"] = str(r["column_weekday"]).strip().title()
            out.append(item)
    return out


def _landscape_rows_for_day_from_entry(day: date, entry: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = entry.get("landscape_rows")
    notes = str(entry.get("notes") or "")
    return filter_work_landscape_rows_for_bundle(day, _normalize_raw_landscape_rows(rows), notes)


def _meta_from_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "time_coaching": str(entry.get("time_coaching") or ""),
        "notes": str(entry.get("notes") or ""),
        "visibility": str(entry.get("visibility") or ""),
        "saved_at": entry.get("saved_at"),
    }
    tb = entry.get("tactical_brief")
    if tb is not None:
        out["tactical_brief"] = normalize_tactical_brief_to_periods(tb)
    return out


def load_advisory_meta_for_day(day: date) -> Optional[Dict[str, Any]]:
    """
    Work-calendar advisory text for this recon day.
    Week-view uploads are often stored under a single `by_date` key (e.g. the upload day) while
    rows carry `column_date_iso` for Tue–Fri — resolve from any bundle in the same ISO week.
    """
    bundle = load_bundle()
    by_date = bundle.get("by_date")
    if not isinstance(by_date, dict):
        return None
    week_keys = _week_iso_keys_containing(day)
    candidates: List[tuple[str, Dict[str, Any]]] = []
    for k in week_keys:
        e = by_date.get(k)
        if isinstance(e, dict):
            candidates.append((k, e))
    candidates.sort(key=lambda x: _saved_at_sort_key(x[1]), reverse=True)

    for _k, entry in candidates:
        if _landscape_rows_for_day_from_entry(day, entry):
            return _meta_from_entry(entry)

    for _k, entry in candidates:
        if _notes_imply_week_view(str(entry.get("notes") or "")):
            if tactical_brief_has_content(entry.get("tactical_brief")) or str(entry.get("time_coaching") or "").strip():
                return _meta_from_entry(entry)

    direct = by_date.get(day.isoformat())
    if isinstance(direct, dict):
        if tactical_brief_has_content(direct.get("tactical_brief")) or str(direct.get("time_coaching") or "").strip():
            return _meta_from_entry(direct)
    return None


def work_calendar_week_gap_hint(day: date, *, work_screenshot_row_count: int) -> str:
    """
    One-line hint when a week-style work bundle exists but every row is tagged to another
    calendar day (common Gemini mistake) so this recon day gets no work_screenshot rows.
    """
    if work_screenshot_row_count > 0:
        return ""
    bundle = load_bundle()
    by_date = bundle.get("by_date")
    if not isinstance(by_date, dict):
        return ""
    week_keys = _week_iso_keys_containing(day)
    candidates: List[tuple[str, Dict[str, Any]]] = []
    for k in week_keys:
        e = by_date.get(k)
        if isinstance(e, dict):
            candidates.append((k, e))
    candidates.sort(key=lambda x: _saved_at_sort_key(x[1]), reverse=True)
    for _k, entry in candidates:
        raw = _normalize_raw_landscape_rows(entry.get("landscape_rows"))
        if len(raw) < 2:
            continue
        notes = str(entry.get("notes") or "")
        if not _notes_imply_week_view(notes):
            continue
        cols: set[str] = set()
        for r in raw:
            c = str(r.get("column_date_iso") or "").strip()
            if len(c) >= 10:
                cols.add(c[:10])
        cols.discard("")
        if len(cols) != 1:
            continue
        only_col = next(iter(cols))
        if only_col == day.isoformat():
            continue
        filt = filter_work_landscape_rows_for_bundle(day, raw, notes)
        if filt:
            continue
        return (
            f"Work snapshot tags every block as {only_col}, not {day.isoformat()}. "
            "Re-run calendar analyze so each weekday column gets its own column_date_iso."
        )
    return ""


def load_landscape_rows_for_day(day: date) -> List[Dict[str, Any]]:
    """
    Work screenshot rows merged into the cockpit landscape for `day`.
    Scans all `by_date` bundles in the same Mon–Sun week (newest `saved_at` first) so week-view
    saves keyed to one day still hydrate Tue–Fri when rows carry `column_date_iso`.
    """
    bundle = load_bundle()
    by_date = bundle.get("by_date")
    if not isinstance(by_date, dict):
        return []
    week_keys = _week_iso_keys_containing(day)
    candidates: List[tuple[str, Dict[str, Any]]] = []
    for k in week_keys:
        e = by_date.get(k)
        if isinstance(e, dict):
            candidates.append((k, e))
    candidates.sort(key=lambda x: _saved_at_sort_key(x[1]), reverse=True)

    seen: set[tuple[str, str]] = set()
    merged: List[Dict[str, Any]] = []
    for _k, entry in candidates:
        for r in _landscape_rows_for_day_from_entry(day, entry):
            dedupe = (str(r.get("start_iso") or ""), str(r.get("title") or ""))
            if dedupe in seen:
                continue
            seen.add(dedupe)
            merged.append(r)
    merged.sort(key=lambda r: str(r.get("start_iso") or ""))
    return merged


def save_advisory_for_day(
    day: date,
    *,
    landscape_rows: List[Dict[str, Any]],
    raw_advisory: Dict[str, Any],
) -> None:
    bundle = load_bundle()
    by_date: Dict[str, Any] = dict(bundle["by_date"])
    entry_out: Dict[str, Any] = {
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "recon_day": day.isoformat(),
        "landscape_rows": landscape_rows,
        "time_coaching": raw_advisory.get("time_coaching") or "",
        "notes": raw_advisory.get("notes") or "",
        "visibility": raw_advisory.get("visibility") or "",
        "suggested_anchor": raw_advisory.get("suggested_anchor"),
        "advisory_events": raw_advisory.get("advisory_events") or [],
    }
    if raw_advisory.get("tactical_brief") is not None:
        entry_out["tactical_brief"] = _normalize_tactical_brief_dict(raw_advisory.get("tactical_brief"))
    by_date[day.isoformat()] = entry_out
    bundle["by_date"] = by_date
    _atomic_write_json(WORK_CALENDAR_ADVISORY_PATH, bundle)
