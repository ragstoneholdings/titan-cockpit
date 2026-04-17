"""Google Calendar read-only client (token.json + OAuth credentials)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from integrations.paths import CALENDAR_SCOPES, TOKEN_PATH

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
except ImportError:  # pragma: no cover
    Credentials = None  # type: ignore
    Request = None  # type: ignore
    build = None  # type: ignore


def calendar_service_from_token() -> Optional[Any]:
    if not Credentials or not build or not TOKEN_PATH.is_file():
        return None
    try:
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), CALENDAR_SCOPES)
        if creds.expired and creds.refresh_token and Request:
            creds.refresh(Request())
            TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
        if not creds.valid:
            return None
        return build("calendar", "v3", credentials=creds, cache_discovery=False)
    except OSError:
        return None


def day_bounds_local(d: date) -> Tuple[datetime, datetime]:
    tzinfo = datetime.now().astimezone().tzinfo
    start = datetime.combine(d, datetime.min.time()).replace(tzinfo=tzinfo)
    end = start + timedelta(days=1)
    return start, end


def list_google_calendar_events_for_day(
    service: Any, day: date, calendar_id: str
) -> List[Dict[str, Any]]:
    start, end = day_bounds_local(day)
    events: List[Dict[str, Any]] = []
    page_token = None
    while True:
        kwargs: Dict[str, Any] = {
            "calendarId": calendar_id,
            "timeMin": start.isoformat(),
            "timeMax": end.isoformat(),
            "singleEvents": True,
            "orderBy": "startTime",
            "maxResults": 250,
        }
        if page_token:
            kwargs["pageToken"] = page_token
        result = service.events().list(**kwargs).execute()
        events.extend(result.get("items", []))
        page_token = result.get("nextPageToken")
        if not page_token:
            break
    return events
