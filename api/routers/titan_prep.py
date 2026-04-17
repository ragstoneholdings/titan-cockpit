"""Friday Titan Prep / week-ahead wardrobe pass (Gemini), grounded on calendar when available."""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query

from api.services.gemini_runtime import configure_genai_from_env, gemini_model_name
from api.services.titan_prep_week_digest import build_week_digest_for_titan_prep
from api.services.titan_sartorial_store import get_week, next_week_monday, save_week

router = APIRouter(prefix="/titan-prep", tags=["titan-prep"])

_MAX_DIGEST_LINES = 200


def _week_from_query(week_start: Optional[date]) -> date:
    return week_start or next_week_monday(date.today())


def _row_to_response(wk: date, row: dict[str, Any] | None) -> dict[str, Any]:
    if not row:
        return {
            "week_start": wk.isoformat(),
            "text": "",
            "generated_at": None,
            "model": "",
            "grounding_event_count": None,
        }
    raw_gec = row.get("grounding_event_count")
    try:
        grounding_event_count = int(raw_gec) if raw_gec is not None else None
    except (TypeError, ValueError):
        grounding_event_count = None
    return {
        "week_start": wk.isoformat(),
        "text": str(row.get("text") or ""),
        "generated_at": row.get("generated_at"),
        "model": str(row.get("model") or ""),
        "grounding_event_count": grounding_event_count,
    }


def build_titan_prep_prompt(*, today: date, week_monday: date, digest: str, digest_event_total: int) -> str:
    """Build Gemini user prompt (exposed for tests)."""
    digest = (digest or "").strip()
    has_digest = digest_event_total > 0 and bool(digest)
    trunc_note = ""
    if digest_event_total > _MAX_DIGEST_LINES:
        trunc_note = (
            f"\nNote: the digest was capped at {_MAX_DIGEST_LINES} lines; "
            f"the week had at least {digest_event_total} event rows.\n"
        )
    if has_digest:
        return f"""You are an executive chief of staff. Today is {today.isoformat()}.
The operator is preparing for the calendar week starting **{week_monday.isoformat()}** (Monday).

Below is a **read-only digest** of timed and all-day blocks from their connected calendars (Mon–Sun, local time). Each line is one block: date, time or all-day, source tag [google] or [personal], title.
{trunc_note}
--- CALENDAR DIGEST (only use these; do not invent meetings) ---
{digest}
--- END DIGEST ---

Answer in short sections with bullets (under 400 words). Rugged Executive tone: direct, no fluff, no therapy language.

1. **Full suit**: Which **listed** blocks likely require a full suit? Cite the **exact title** (or time + title). If attire is unclear from the title alone, say **Unknown — ask operator** instead of guessing.
2. **Sharp / L6 frame**: Which listed blocks are better served by sharp casual / creative executive presence? Same rule: cite titles; use **Unknown — ask operator** when unclear.
3. **Friday prep**: One short paragraph — what to prep Friday (gear, grooming, dry cleaning, bag) so Monday opens clean, **based only on what the digest implies** about the week ahead."""

    return f"""You are an executive chief of staff. Today is {today.isoformat()}.
The operator is preparing for the calendar week starting **{week_monday.isoformat()}** (Monday).

**No calendar rows were available** (Google OAuth not connected and/or no personal calendar feed for this range). Do **not** invent specific meetings or names.

Output (under 250 words), Rugged Executive tone: direct, no fluff, no therapy language:
1. State once that there was **no calendar data** for this pass.
2. A **generic** Friday prep checklist (suit steam, polish shoes, bag reset, dry cleaning buffer) that still helps Monday, without claiming any real events occurred."""


@router.get("")
def get_titan_prep(
    week_start: Optional[date] = Query(None, description="Target week Monday (default: next week)"),
) -> dict[str, Any]:
    wk = _week_from_query(week_start)
    row = get_week(wk)
    return _row_to_response(wk, row)


@router.post("/generate")
def post_titan_prep_generate(
    week_start: Optional[date] = Query(None, description="Target week Monday (default: next week)"),
    calendar_id: str = Query("primary", description="Google Calendar id (default primary)"),
) -> dict[str, Any]:
    genai, err = configure_genai_from_env()
    if genai is None:
        raise HTTPException(status_code=503, detail=err or "Gemini not configured.")
    wk = _week_from_query(week_start)
    digest, digest_event_total = build_week_digest_for_titan_prep(wk, calendar_id.strip() or "primary")
    prompt = build_titan_prep_prompt(
        today=date.today(),
        week_monday=wk,
        digest=digest,
        digest_event_total=digest_event_total,
    )
    model = genai.GenerativeModel(gemini_model_name())
    try:
        resp = model.generate_content(prompt)
        text = (resp.text or "").strip()
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(e)) from e
    save_week(
        wk,
        text,
        model=gemini_model_name(),
        grounding_event_count=digest_event_total,
    )
    row = get_week(wk) or {}
    out = _row_to_response(wk, row)
    out["text"] = text
    out["model"] = gemini_model_name()
    return out
