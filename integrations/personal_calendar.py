"""Personal calendar via ICS webcal URL or iCloud CalDAV (shared by Streamlit and API)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from integrations.env_loader import env_str
from integrations.google_calendar import day_bounds_local

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

try:
    from icalendar import Calendar as ICalendarMod
except ImportError:  # pragma: no cover
    ICalendarMod = None


def _icalendar_calendar_class() -> Optional[Any]:
    if ICalendarMod is not None:
        return ICalendarMod
    try:
        from icalendar import Calendar as IC

        return IC
    except ImportError:
        return None


def _icloud_caldav_libs() -> Tuple[Optional[Any], Optional[Any]]:
    try:
        import caldav as caldav_mod
        from icalendar import Calendar as ICal

        return caldav_mod, ICal
    except ImportError:
        return None, None


def icloud_caldav_ready() -> bool:
    """True if caldav + icalendar are importable (iCloud path)."""
    c, i = _icloud_caldav_libs()
    return c is not None and i is not None


def format_clock_local(dt: datetime) -> str:
    s = dt.strftime("%I:%M %p")
    if s.startswith("0"):
        s = s[1:]
    return s.replace("AM", "a.m.").replace("PM", "p.m.")


def _personal_event_title(comp: Any) -> str:
    return str(comp.get("summary") or "(no title)").strip() or "(no title)"


def _all_day_vevent_on_date(comp: Any, day: date) -> Optional[str]:
    if str(comp.get("transp") or "").upper() == "TRANSPARENT":
        return None
    ds = comp.get("dtstart")
    if not ds:
        return None
    s = ds.dt
    if isinstance(s, datetime):
        return None
    if not isinstance(s, date):
        return None
    de = comp.get("dtend")
    if de:
        e_raw = de.dt
        if isinstance(e_raw, datetime):
            end_excl = e_raw.date()
        else:
            end_excl = e_raw
    else:
        end_excl = s + timedelta(days=1)
    if s <= day < end_excl:
        return _personal_event_title(comp)
    return None


def _timed_vevent_display_bounds(
    comp: Any, win_start: datetime, win_end: datetime
) -> Optional[Tuple[datetime, datetime, str]]:
    if str(comp.get("transp") or "").upper() == "TRANSPARENT":
        return None
    ds = comp.get("dtstart")
    de = comp.get("dtend")
    if not ds or not de:
        return None
    start = ds.dt
    end = de.dt
    if not isinstance(start, datetime) or not isinstance(end, datetime):
        return None
    tz = win_start.tzinfo
    if start.tzinfo is None:
        start = start.replace(tzinfo=tz)
    else:
        start = start.astimezone(win_start.tzinfo)
    if end.tzinfo is None:
        end = end.replace(tzinfo=tz)
    else:
        end = end.astimezone(win_end.tzinfo)
    seg_b = min(end, win_end)
    seg_a = max(start, win_start)
    if seg_b <= seg_a:
        return None
    return start, end, _personal_event_title(comp)


def _sort_personal_day_events(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    def sk(r: Dict[str, Any]) -> Tuple[int, str]:
        if r.get("all_day"):
            return (0, str(r.get("title") or "").lower())
        return (1, str(r.get("start_iso") or ""))

    return sorted(rows, key=sk)


def parse_ics_feed_events_and_hours(url: str, day: date) -> Tuple[List[Dict[str, Any]], float, str]:
    if not requests:
        return [], 0.0, "Install requests."
    ICal = _icalendar_calendar_class()
    if not ICal:
        return [], 0.0, "Install icalendar."
    win_start, win_end = day_bounds_local(day)
    fetch_url = url.strip().replace("webcal://", "https://", 1)
    try:
        r = requests.get(fetch_url, timeout=45)
        r.raise_for_status()
        cal = ICal.from_ical(r.content)
    except Exception as e:  # noqa: BLE001
        return [], 0.0, str(e)
    rows: List[Dict[str, Any]] = []
    total_sec = 0.0
    seen_all_day: set[str] = set()
    for comp in cal.walk("VEVENT"):
        ad_title = _all_day_vevent_on_date(comp, day)
        if ad_title is not None:
            uid = str(comp.get("uid") or ad_title)
            if uid in seen_all_day:
                continue
            seen_all_day.add(uid)
            rows.append(
                {
                    "all_day": True,
                    "title": ad_title,
                    "start_iso": day.isoformat(),
                    "end_iso": day.isoformat(),
                    "cal": "",
                }
            )
            continue
        tb = _timed_vevent_display_bounds(comp, win_start, win_end)
        if not tb:
            continue
        start, end, title = tb
        seg_a = max(start, win_start)
        seg_b = min(end, win_end)
        total_sec += float((seg_b - seg_a).total_seconds())
        rows.append(
            {
                "all_day": False,
                "title": title,
                "start_iso": start.isoformat(),
                "end_iso": end.isoformat(),
                "cal": "",
            }
        )
    return _sort_personal_day_events(rows), min(total_sec / 3600.0, 24.0), ""


def parse_icloud_calendars_events_and_hours(
    apple_id: str,
    app_password: str,
    day: date,
    calendar_name_filter: str = "",
) -> Tuple[List[Dict[str, Any]], float, str]:
    caldav_mod, ICal = _icloud_caldav_libs()
    if not caldav_mod or not ICal:
        return [], 0.0, "Install caldav and icalendar (`pip install caldav icalendar`)."
    win_start, win_end = day_bounds_local(day)
    try:
        client = caldav_mod.DAVClient(
            url="https://caldav.icloud.com/",
            username=apple_id.strip(),
            password=app_password.strip(),
        )
        principal = client.principal()
        calendars = principal.calendars()
    except Exception as e:  # noqa: BLE001
        return [], 0.0, f"iCloud CalDAV: {e}"
    rows: List[Dict[str, Any]] = []
    total_sec = 0.0
    filt = calendar_name_filter.strip().lower()
    for cal in calendars:
        try:
            cal_name = str(cal.name or "")
        except Exception:
            cal_name = ""
        if filt and filt not in cal_name.lower():
            continue
        try:
            try:
                events = cal.date_search(start=win_start, end=win_end, expand=True)
            except TypeError:
                events = cal.date_search(start=win_start, end=win_end)
        except Exception:
            continue
        for ev in events:
            try:
                raw = ev.data
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8", errors="replace")
                ical = ICal.from_ical(raw)
                for comp in ical.walk("VEVENT"):
                    ad_title = _all_day_vevent_on_date(comp, day)
                    if ad_title is not None:
                        rows.append(
                            {
                                "all_day": True,
                                "title": ad_title,
                                "start_iso": day.isoformat(),
                                "end_iso": day.isoformat(),
                                "cal": cal_name,
                            }
                        )
                        continue
                    tb = _timed_vevent_display_bounds(comp, win_start, win_end)
                    if not tb:
                        continue
                    start, end, title = tb
                    seg_a = max(start, win_start)
                    seg_b = min(end, win_end)
                    total_sec += float((seg_b - seg_a).total_seconds())
                    rows.append(
                        {
                            "all_day": False,
                            "title": title,
                            "start_iso": start.isoformat(),
                            "end_iso": end.isoformat(),
                            "cal": cal_name,
                        }
                    )
            except Exception:
                continue
    return _sort_personal_day_events(rows), min(total_sec / 3600.0, 24.0), ""


def fetch_personal_calendar_events_from_env(day: date) -> Tuple[List[Dict[str, Any]], float, str]:
    """
    Same precedence as Streamlit: ICS URL if set, else iCloud credentials.
    Uses only os.environ / .env (for FastAPI). Streamlit uses _env_or_secret + these parsers.
    """
    ics_url = env_str("APPLE_CALENDAR_ICS_URL", "")
    apple_id = env_str("ICLOUD_APPLE_ID", "")
    app_pw = env_str("ICLOUD_APP_PASSWORD", "")
    cal_filter = env_str("ICLOUD_CALENDAR_NAME", "")
    if ics_url.strip():
        ev, h, err = parse_ics_feed_events_and_hours(ics_url, day)
        return ev, h, err
    if apple_id and app_pw:
        return parse_icloud_calendars_events_and_hours(apple_id, app_pw, day, cal_filter)
    return [], 0.0, "not_configured"
