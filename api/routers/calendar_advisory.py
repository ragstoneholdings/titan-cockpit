"""Calendar screenshot Advisory Panel (Gemini vision)."""

from __future__ import annotations

from datetime import date
from typing import Any, List, Optional

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from api.services.calendar_advisory_gemini import analyze_calendar_screenshots_advisory
from api.services.work_advisory_store import save_advisory_for_day

router = APIRouter(prefix="/calendar", tags=["calendar"])


@router.post("/screenshots/analyze")
async def post_screenshots_analyze(
    day: Optional[date] = Query(None, description="Recon date (defaults to today)"),
    files: List[UploadFile] = File(),
) -> dict[str, Any]:
    if not files:
        raise HTTPException(status_code=400, detail="Upload at least one image file.")
    d = day or date.today()
    blobs: List[bytes] = []
    for f in files:
        try:
            blobs.append(await f.read())
        except OSError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
    if not any(blobs):
        raise HTTPException(status_code=400, detail="Empty file upload.")
    try:
        payload, warn = analyze_calendar_screenshots_advisory(blobs, d)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Advisory failed: {e!s}") from e
    rows = payload.get("landscape_rows")
    if not isinstance(rows, list):
        rows = []
    try:
        save_advisory_for_day(
            d,
            landscape_rows=[r for r in rows if isinstance(r, dict)],
            raw_advisory=payload if isinstance(payload, dict) else {},
        )
    except OSError as save_exc:
        raise HTTPException(status_code=500, detail=f"Could not save advisory: {save_exc}") from save_exc
    return {"ok": True, "warning": warn, "advisory": payload}
