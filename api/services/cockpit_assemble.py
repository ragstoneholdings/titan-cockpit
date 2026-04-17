"""Shared assembly of the cockpit HTTP payload (used by ``GET /api/cockpit`` and push triggers)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, Optional

from api.schemas.cockpit import CockpitResponse
from api.services.cockpit_snapshot import build_cockpit_response
from integrations.google_calendar import calendar_service_from_token, list_google_calendar_events_for_day
from integrations.personal_calendar import fetch_personal_calendar_events_from_env


def assemble_cockpit_response(
    day: Optional[date] = None,
    *,
    calendar_id: str = "primary",
    vanguard_deep: int = 0,
    vanguard_mixed: int = 0,
    vanguard_shallow: int = 0,
) -> CockpitResponse:
    """Build the same read model as ``GET /api/cockpit``."""

    d = day or date.today()
    svc = calendar_service_from_token()
    google_evs: list = []
    if svc:
        google_evs = list_google_calendar_events_for_day(svc, d, calendar_id)

    google_evs_tomorrow: list = []
    if d == date.today() and svc:
        google_evs_tomorrow = list_google_calendar_events_for_day(svc, d + timedelta(days=1), calendar_id)

    personal_rows, _personal_h, personal_err = fetch_personal_calendar_events_from_env(d)
    if personal_err == "not_configured":
        personal_note = (
            "Personal calendar not configured. Set APPLE_CALENDAR_ICS_URL or ICLOUD_APPLE_ID + "
            "ICLOUD_APP_PASSWORD (and optional ICLOUD_CALENDAR_NAME) in the environment."
        )
        personal_status: str = "not_configured"
    elif personal_err:
        personal_note = personal_err
        personal_status = "error"
    else:
        personal_note = ""
        personal_status = "ok"

    personal_rows_tomorrow: list = []
    if d == date.today():
        personal_rows_tomorrow, _, _ = fetch_personal_calendar_events_from_env(d + timedelta(days=1))

    payload = build_cockpit_response(
        d,
        google_events=google_evs,
        personal_rows=personal_rows,
        personal_calendar_note=personal_note,
        personal_calendar_status=personal_status,
        vanguard_deep=vanguard_deep,
        vanguard_mixed=vanguard_mixed,
        vanguard_shallow=vanguard_shallow,
        google_events_tomorrow=google_evs_tomorrow if d == date.today() else None,
        personal_rows_tomorrow=personal_rows_tomorrow if d == date.today() else None,
    )
    payload["google_calendar_connected"] = svc is not None
    payload["personal_calendar_status"] = personal_status
    return CockpitResponse(**payload)


def assemble_cockpit_dict(
    day: Optional[date] = None,
    *,
    calendar_id: str = "primary",
    vanguard_deep: int = 0,
    vanguard_mixed: int = 0,
    vanguard_shallow: int = 0,
) -> Dict[str, Any]:
    """Dict form for callers that inspect fields (e.g. integrity sentry)."""

    r = assemble_cockpit_response(
        day,
        calendar_id=calendar_id,
        vanguard_deep=vanguard_deep,
        vanguard_mixed=vanguard_mixed,
        vanguard_shallow=vanguard_shallow,
    )
    return r.model_dump()
