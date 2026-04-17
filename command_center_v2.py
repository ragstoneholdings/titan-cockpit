"""
Sovereign Executive Command Center — Streamlit ops dashboard for Ragstone Holdings.

Primary workflow: weekly work calendar screenshots (Gemini), personal Apple/ICS, live Todoist, optional Google Calendar.
"""

from __future__ import annotations

import html
import io
import json
import os
import re
import time as time_module
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st

try:
    from streamlit_shortcuts import add_keyboard_shortcuts
except ImportError:  # pragma: no cover
    add_keyboard_shortcuts = None  # type: ignore

try:
    import pandas as pd
except ImportError:  # pragma: no cover
    pd = None  # type: ignore

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None  # type: ignore

# Optional Google Calendar (live API)
try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
except ImportError:  # pragma: no cover
    Credentials = None  # type: ignore
    Request = None  # type: ignore
    InstalledAppFlow = None  # type: ignore
    build = None  # type: ignore

# Optional Gemini
try:
    import google.generativeai as genai
except ImportError:  # pragma: no cover
    genai = None

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None  # type: ignore

from chief_of_staff.anchor_gemini import nominate_hard_anchor_index
from chief_of_staff.models import ChiefOfStaffConfig, DayReadiness, IdentityProtocols
from chief_of_staff.planning import (
    active_timed_anchor_list,
    anchors_revision_hash,
    build_day_readiness,
    build_preparation_brief_markdown,
    compute_deep_work_kill_zones,
    merged_timed_anchors,
    parse_marker_csv,
    select_integrity_anchor,
)
import focus_metrics
import identity_store
import power_trio
import protocol_ui
import todoist_service
from runway_store import (
    RunwayDayOverride,
    clear_runway_override_for_day,
    load_runway_override_for_day,
    save_runway_override_for_day,
)
from integrations.personal_calendar import (
    format_clock_local,
    icloud_caldav_ready,
    parse_icloud_calendars_events_and_hours,
    parse_ics_feed_events_and_hours,
)

# --- Paths & constants ---
ROOT = Path(__file__).resolve().parent
PROTOCOL_STATE_PATH = ROOT / "posture_protocol_state.json"
TOKEN_PATH = ROOT / "token.json"


def load_ragstone_env_files() -> None:
    """
    Load ``export KEY='...'`` lines from Ragstone env files into ``os.environ``.
    Lets Streamlit see API keys when the app is started without ``source`` in the terminal.
    """
    candidates = [
        Path.home() / ".ragstone" / "command_center.env",
        ROOT / ".env",
    ]
    for path in candidates:
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8-sig")
        except OSError:
            continue
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[7:].lstrip()
            if "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip()
            if not key:
                continue
            if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
                val = val[1:-1]
            if val:
                os.environ[key] = val


load_ragstone_env_files()


def _calendar_credentials_path() -> Path:
    p = os.environ.get("GOOGLE_CALENDAR_CREDENTIALS", "").strip()
    if p:
        return Path(p).expanduser()
    return ROOT / "credentials.json"


CREDENTIALS_PATH = _calendar_credentials_path()

CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
TODOIST_URGENT_PRIORITY = 4
# Default Next Focus filter when TODOIST_NEXT_FOCUS_FILTER is unset (override in env or secrets).
DEFAULT_TODOIST_NEXT_FOCUS_FILTER = "@next & @focus"
# `gemini-1.5-pro` returns 404 on current Gemini API; override via GEMINI_MODEL env or secrets.toml
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"

PROTOCOL_ITEMS = [
    {"id": "chin_tucks", "label": "Chin tucks"},
    {"id": "wall_slides", "label": "Wall slides"},
    {"id": "diaphragmatic_breathing", "label": "Diaphragmatic breathing"},
]
# posture_protocol_state.json v2: {"version": 2, "history": {...}, "neck_cm": {"YYYY-MM-DD": float, ...}}
PROTOCOL_HISTORY_TRIM_DAYS = 90

# Sidebar work window (12-hour UI → `time` for calculations)
DEFAULT_WORK_BLOCK_START = time(7, 30)
DEFAULT_WORK_BLOCK_END = time(17, 30)


def _time_from_ampm(h12: int, minute: int, ampm: str) -> time:
    h12 = int(h12)
    minute = int(minute)
    if ampm == "AM":
        h24 = 0 if h12 == 12 else h12
    else:
        h24 = 12 if h12 == 12 else h12 + 12
    return time(h24, minute)


def _h12_minute_ap_from_time(t: time) -> Tuple[int, int, str]:
    ap = "PM" if t.hour >= 12 else "AM"
    h12 = t.hour % 12 or 12
    return h12, t.minute, ap


def _init_work_hours_ampm_state() -> None:
    if "param_ws_h12" not in st.session_state:
        h, m, ap = _h12_minute_ap_from_time(DEFAULT_WORK_BLOCK_START)
        st.session_state.param_ws_h12 = h
        st.session_state.param_ws_min = m
        st.session_state.param_ws_ap = ap
    if "param_we_h12" not in st.session_state:
        h, m, ap = _h12_minute_ap_from_time(DEFAULT_WORK_BLOCK_END)
        st.session_state.param_we_h12 = h
        st.session_state.param_we_min = m
        st.session_state.param_we_ap = ap


def _ensure_integrity_wake_state() -> None:
    if "integ_ws_h12" not in st.session_state:
        h, m, ap = _h12_minute_ap_from_time(time(5, 0))
        st.session_state.integ_ws_h12 = h
        st.session_state.integ_ws_min = m
        st.session_state.integ_ws_ap = ap
    if "integ_post_m" not in st.session_state:
        st.session_state.integ_post_m = int(_env_or_secret("CHIEF_POSTURE_MINUTES", "30") or 30)
    if "integ_neck_m" not in st.session_state:
        st.session_state.integ_neck_m = int(_env_or_secret("CHIEF_NECK_MINUTES", "60") or 60)
    if "integ_ops_m" not in st.session_state:
        st.session_state.integ_ops_m = int(_env_or_secret("CHIEF_OPS_MINUTES", "30") or 30)


def _parse_optional_bedtime(s: str) -> Optional[datetime]:
    raw = (s or "").strip()
    if not raw:
        return None
    t: Optional[time] = None
    for fmt in ("%I:%M %p", "%H:%M", "%I %p"):
        try:
            if fmt == "%I %p":
                tt = datetime.strptime(raw.upper(), fmt).time()
            else:
                tt = datetime.strptime(raw, fmt).time()
            t = tt
            break
        except ValueError:
            continue
    if t is None:
        return None
    tzinfo = datetime.now().astimezone().tzinfo
    bed_day = date.today() - timedelta(days=1)
    return datetime.combine(bed_day, t).replace(tzinfo=tzinfo)


def _identity_protocols_from_sidebar_minutes() -> IdentityProtocols:
    pm = max(0, int(st.session_state.get("integ_post_m") or 0))
    nm = max(0, int(st.session_state.get("integ_neck_m") or 0))
    om = max(0, int(st.session_state.get("integ_ops_m") or 0))
    return IdentityProtocols(
        posture=timedelta(minutes=pm),
        neck=timedelta(minutes=nm),
        morning_ops=timedelta(minutes=om),
    )


def render_integrity_sidebar_block() -> None:
    _ensure_integrity_wake_state()
    st.divider()
    st.subheader("Integrity runway")
    st.caption("Default wake + protocol minutes + optional HARD overrides.")
    rs = st.columns(3)
    with rs[0]:
        st.selectbox("Wake hour", list(range(1, 13)), key="integ_ws_h12")
    with rs[1]:
        st.selectbox(
            "Wake min",
            list(range(0, 60)),
            key="integ_ws_min",
            format_func=lambda m: f"{int(m):02d}",
        )
    with rs[2]:
        st.selectbox("AM / PM", ["AM", "PM"], key="integ_ws_ap")
    st.number_input("Posture (min)", min_value=0, max_value=180, step=1, key="integ_post_m")
    st.number_input("Neck (min)", min_value=0, max_value=180, step=1, key="integ_neck_m")
    st.number_input("Morning Ops (min)", min_value=0, max_value=180, step=1, key="integ_ops_m")
    st.text_input(
        "Last night bedtime (optional)",
        key="integ_bed_text",
        placeholder="11:30 PM",
        help="Local time you went to bed last night.",
    )
    st.text_input(
        "Optional HARD overrides (comma-separated)",
        key="chief_markers",
        help="Optional: substrings in event titles; first match wins before AI/heuristics. Leave empty for full automation.",
    )


def render_power_trio_sidebar_block() -> None:
    st.divider()
    st.subheader("Power Trio (Todoist)")
    todoist_key = todoist_api_key()
    if not todoist_key:
        st.caption("Set `TODOIST_API_KEY` for Power Trio.")
        return
    if not requests:
        st.warning("Install `requests`.")
        return
    st.text_area(
        "Purpose / Titan identity",
        key="power_purpose",
        height=70,
    )
    st.text_area(
        "Ragstone Strategy",
        key="power_ragstone_strategy",
        height=70,
        help="Portfolio / execution thesis — fed to Gemini with Life Purpose and Google Ops.",
    )
    st.text_area(
        "Google Scaled Ops goals",
        key="power_scaled_ops",
        height=70,
    )
    st.text_input(
        "Identity project substrings (weekend boost)",
        key="power_id_substr",
    )
    st.text_input(
        "Google Ops project substrings (weekend demote)",
        key="power_ops_substr",
    )
    if st.button("Pull all tasks", key="sidebar_power_pull", width="stretch"):
        try:
            raw = todoist_service.fetch_all_tasks_rest_v2(todoist_key)
            pmap = todoist_service.fetch_todoist_projects(todoist_key)
            by_id: Dict[str, Any] = {}
            for t in raw:
                nt = todoist_service.normalize_power_task(t, pmap)
                tid = nt.get("id")
                if tid:
                    by_id[tid] = nt
            by_id, merge_msg = todoist_service.merge_tasks_from_cache_if_api_empty(by_id, len(raw))
            if merge_msg:
                st.warning(merge_msg)
            st.session_state["power_tasks_by_id"] = by_id
            st.session_state["power_ranked_ids"] = list(by_id.keys())
            st.session_state["power_rank_error"] = merge_msg or ""
            st.session_state["sheet_tasks"] = list(by_id.values())
            if not by_id:
                st.error(
                    "No tasks loaded (empty account or failed fetch). "
                    "If you expected tasks, check **TODOIST_API_KEY** (401/403 = bad token)."
                )
            else:
                st.success(f"Pulled **{len(by_id)}** active tasks.")
            st.rerun()
        except requests.exceptions.HTTPError as e:
            hint = todoist_service.todoist_auth_error_hint(e)
            st.session_state["power_rank_error"] = str(e)
            st.error(f"{e}{hint}")
        except Exception as e:
            st.session_state["power_rank_error"] = str(e)
            st.error(str(e))
    if st.button("Refocus (Gemini rank)", key="sidebar_power_rank", width="stretch"):
        by_id = dict(st.session_state.get("power_tasks_by_id") or {})
        if not by_id:
            st.warning("Pull all tasks first.")
        elif not configure_gemini():
            st.warning("Add a Gemini API key.")
        elif not genai:
            st.warning("Install google-generativeai.")
        else:
            try:
                purpose = str(st.session_state.get("power_purpose") or "")
                rstrat = str(st.session_state.get("power_ragstone_strategy") or "")
                scaled = str(st.session_state.get("power_scaled_ops") or "")
                id_sub = power_trio.split_substrings_csv(str(st.session_state.get("power_id_substr") or ""))
                op_sub = power_trio.split_substrings_csv(str(st.session_state.get("power_ops_substr") or ""))
                payload = [
                    {"id": tid, "content": v.get("content"), "project_name": v.get("project_name")}
                    for tid, v in by_id.items()
                ]
                recon_d = _session_date("dashboard_selected_date")
                is_weekend = recon_d.weekday() >= 5
                wd = recon_d.strftime("%A")
                ranked, rank_warn = power_trio.rank_tasks_for_power_trio(
                    genai,
                    gemini_model_name(),
                    by_id,
                    purpose,
                    rstrat,
                    scaled,
                    wd,
                    is_weekend,
                    id_sub,
                    op_sub,
                )
                st.session_state["power_ranked_ids"] = ranked
                st.session_state["power_rank_error"] = rank_warn or ""
                st.session_state["power_rank_anchor_date"] = recon_d.isoformat()
                st.session_state["sheet_tasks"] = [by_id[k] for k in ranked if k in by_id]
                power_trio.save_ranked_cache(ranked, by_id, day=recon_d)
                st.success(f"Ranked **{len(ranked)}** tasks.")
                if rank_warn:
                    st.warning(rank_warn)
                st.rerun()
            except Exception as e:
                st.session_state["power_rank_error"] = str(e)
                st.error(str(e))


def render_legacy_todoist_bucket_pull() -> None:
    """Optional v1 filter-based pull for Architect fallback."""
    st.caption("Legacy: today / overdue / Next Focus merge")
    focus_q = _env_or_secret(
        "TODOIST_NEXT_FOCUS_FILTER", DEFAULT_TODOIST_NEXT_FOCUS_FILTER
    ) or DEFAULT_TODOIST_NEXT_FOCUS_FILTER
    todoist_key = todoist_api_key()
    if not todoist_key or not requests:
        return
    if st.button("Legacy bucket pull", key="sidebar_todoist_legacy_pull", width="stretch"):
        try:
            today_raw = _fetch_todoist_tasks_filter_query(todoist_key, "today")
            overdue_raw = _fetch_todoist_tasks_filter_query(todoist_key, "overdue")
            focus_raw = _fetch_todoist_tasks_filter_query(todoist_key, focus_q)
            merged_raw = _merge_todoist_by_id(today_raw, overdue_raw, focus_raw)
            st.session_state["todoist_today_tasks"] = [
                normalize_todoist_api_task(t) for t in today_raw
            ]
            st.session_state["todoist_next_focus_tasks"] = [
                normalize_todoist_api_task(t) for t in focus_raw
            ]
            st.session_state["todoist_overdue_tasks"] = [
                normalize_todoist_api_task(t) for t in overdue_raw
            ]
            st.session_state["todoist_last_focus_filter"] = focus_q
            normalized = [normalize_todoist_api_task(t) for t in merged_raw]
            st.session_state["sheet_tasks"] = normalized
            st.rerun()
        except requests.HTTPError as e:
            body = (e.response.text or "")[:300] if e.response else ""
            st.error(f"Todoist HTTP error: {e} {body}")
        except requests.RequestException as e:
            st.error(str(e))


def _fetch_todoist_tasks_filter_query(api_key: str, filter_query: str) -> List[Dict[str, Any]]:
    """Active tasks matching one Todoist filter string via GET /api/v1/tasks/filter (cursor-paginated)."""
    if not requests or not filter_query.strip():
        return []
    url = "https://api.todoist.com/api/v1/tasks/filter"
    headers = {"Authorization": f"Bearer {api_key}"}
    raw: List[Dict[str, Any]] = []
    cursor: Optional[str] = None
    for _ in range(100):
        params: Dict[str, str] = {"query": filter_query.strip(), "lang": "en"}
        if cursor:
            params["cursor"] = cursor
        r = requests.get(url, headers=headers, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        if not isinstance(data, dict):
            break
        batch = data.get("results")
        if not isinstance(batch, list):
            break
        raw.extend(t for t in batch if isinstance(t, dict))
        cursor = data.get("next_cursor")
        if not cursor:
            break
    return [t for t in raw if not t.get("checked") and not t.get("is_deleted")]


def _merge_todoist_by_id(*batches: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen: set[str] = set()
    out: List[Dict[str, Any]] = []
    for batch in batches:
        for t in batch:
            tid = str(t.get("id") or "").strip()
            if not tid or tid in seen:
                continue
            seen.add(tid)
            out.append(t)
    return out


def normalize_todoist_api_task(t: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "content": t.get("content", ""),
        "priority": int(t.get("priority") or 1),
        "description": (t.get("description") or "").strip(),
    }


def _env_or_secret(key: str, default: str = "") -> str:
    v = os.environ.get(key, "").strip()
    if v:
        return v
    try:
        return str(st.secrets.get(key) or "").strip() or default
    except Exception:
        return default


def todoist_api_key() -> str:
    k = os.environ.get("TODOIST_API_KEY", "").strip()
    if k:
        return k
    try:
        return str(st.secrets.get("TODOIST_API_KEY") or "").strip()
    except Exception:
        return ""


def _session_date(key: str) -> date:
    """Read a date from Streamlit session (date_input stores date or datetime)."""
    v = st.session_state.get(key)
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    return date.today()


def render_todoist_sidebar_controls() -> None:
    """Integrity runway params, Power Trio sync + rank, optional legacy bucket pull."""
    render_integrity_sidebar_block()
    render_power_trio_sidebar_block()
    render_legacy_todoist_bucket_pull()


def _ensure_sidebar_text_defaults() -> None:
    if "chief_markers" not in st.session_state:
        st.session_state.chief_markers = _env_or_secret("CHIEF_HARD_MARKERS", "")
    if "power_purpose" not in st.session_state:
        st.session_state.power_purpose = _env_or_secret("POWER_PURPOSE_STATEMENT", "")
    if "power_scaled_ops" not in st.session_state:
        st.session_state.power_scaled_ops = _env_or_secret("POWER_SCALED_OPS", "")
    if "power_id_substr" not in st.session_state:
        st.session_state.power_id_substr = _env_or_secret(
            "POWER_IDENTITY_PROJECT_SUBSTRINGS", "Ragstone,Home,Titan"
        )
    if "power_ops_substr" not in st.session_state:
        st.session_state.power_ops_substr = _env_or_secret(
            "POWER_GOOGLE_OPS_SUBSTRINGS", "Google,Work"
        )
    if "power_ragstone_strategy" not in st.session_state:
        st.session_state.power_ragstone_strategy = _env_or_secret("POWER_RAGSTONE_STRATEGY", "")
    if "integ_bed_text" not in st.session_state:
        st.session_state.integ_bed_text = ""


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


def run_calendar_oauth() -> None:
    if not InstalledAppFlow or not CREDENTIALS_PATH.is_file():
        raise FileNotFoundError(
            f"Missing {CREDENTIALS_PATH.name}. Add OAuth client JSON from Google Cloud Console."
        )
    flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), CALENDAR_SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent")
    TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")


def day_bounds_local(d: date) -> Tuple[datetime, datetime]:
    tzinfo = datetime.now().astimezone().tzinfo
    start = datetime.combine(d, datetime.min.time()).replace(tzinfo=tzinfo)
    end = start + timedelta(days=1)
    return start, end


def sum_event_hours_for_day(service: Any, day: date, calendar_id: str) -> float:
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
    total_seconds = 0.0
    for ev in events:
        if ev.get("transparency") == "transparent":
            continue
        start_info = ev.get("start", {})
        end_info = ev.get("end", {})
        if "date" in start_info:
            continue
        s = start_info.get("dateTime")
        e = end_info.get("dateTime")
        if not s or not e:
            continue
        try:
            s_dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            e_dt = datetime.fromisoformat(e.replace("Z", "+00:00"))
            delta = (e_dt - s_dt).total_seconds()
            if delta > 0:
                total_seconds += delta
        except ValueError:
            continue
    return total_seconds / 3600.0


def list_google_calendar_events_for_day(service: Any, day: date, calendar_id: str) -> List[Dict[str, Any]]:
    """Raw Google Calendar event dicts for `day` (timed + all-day + transparent filtered by caller)."""
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


def sum_ics_feed_hours_for_day(url: str, day: date) -> Tuple[float, str]:
    """Sum timed event hours overlapping local `day` from an ICS / webcal URL."""
    ev, h, err = parse_ics_feed_events_and_hours(url, day)
    if err:
        return 0.0, err
    n = sum(1 for x in ev if not x.get("all_day"))
    return h, f"{n} timed event(s) in window."


def sum_icloud_calendar_hours_for_day(
    apple_id: str,
    app_password: str,
    day: date,
    calendar_name_filter: str = "",
) -> Tuple[float, str]:
    """Sum timed hours on local `day` via iCloud CalDAV (app-specific password)."""
    ev, h, err = parse_icloud_calendars_events_and_hours(
        apple_id, app_password, day, calendar_name_filter
    )
    if err:
        return 0.0, err
    n = sum(1 for x in ev if not x.get("all_day"))
    return h, f"{n} timed event(s) counted."


def fetch_personal_calendar_events_and_hours_for_day(day: date) -> Tuple[List[Dict[str, Any]], float, str]:
    """Streamlit: ICS / iCloud via env or st.secrets; parsers live in integrations.personal_calendar."""
    ics_url = _env_or_secret("APPLE_CALENDAR_ICS_URL", "")
    apple_id = _env_or_secret("ICLOUD_APPLE_ID", "")
    app_pw = _env_or_secret("ICLOUD_APP_PASSWORD", "")
    cal_filter = _env_or_secret("ICLOUD_CALENDAR_NAME", "")
    if ics_url.strip():
        return parse_ics_feed_events_and_hours(ics_url, day)
    if apple_id and app_pw:
        return parse_icloud_calendars_events_and_hours(apple_id, app_pw, day, cal_filter)
    return [], 0.0, "not_configured"


def _format_personal_event_line(ev: Dict[str, Any]) -> str:
    if ev.get("all_day"):
        cal = ev.get("cal") or ""
        suffix = f" · _{cal}_" if cal else ""
        return f"**All day** · {ev.get('title', '')}{suffix}"
    try:
        s = datetime.fromisoformat(ev["start_iso"])
        e = datetime.fromisoformat(ev["end_iso"])
    except (KeyError, TypeError, ValueError):
        return ev.get("title", "")
    cal = ev.get("cal") or ""
    suffix = f" · _{cal}_" if cal else ""
    return f"{format_clock_local(s)}–{format_clock_local(e)} · **{ev.get('title', '')}**{suffix}"


def _personal_calendar_configured() -> bool:
    return bool(_env_or_secret("APPLE_CALENDAR_ICS_URL", "").strip()) or (
        bool(_env_or_secret("ICLOUD_APPLE_ID", "").strip()) and bool(_env_or_secret("ICLOUD_APP_PASSWORD", "").strip())
    )


def ensure_personal_calendar_day_view(day: date) -> None:
    """Load today’s personal events for the main-area card (does not change meeting hour fields)."""
    if not _personal_calendar_configured():
        return
    if st.session_state.get("_personal_cal_force_refresh"):
        st.session_state["_personal_cal_force_refresh"] = False
    elif st.session_state.get("personal_calendar_events_meta") == str(day):
        return
    with st.spinner("Loading personal calendar…"):
        ev, _h, err = fetch_personal_calendar_events_and_hours_for_day(day)
    st.session_state["personal_calendar_day_events"] = ev
    st.session_state["personal_calendar_events_load_error"] = err or ""
    st.session_state["personal_calendar_events_meta"] = str(day)


def _ensure_work_cal_week_monday_state() -> None:
    if "work_cal_week_monday" not in st.session_state:
        st.session_state.work_cal_week_monday = week_start_monday(date.today())


def render_work_calendar_sidebar_uploader() -> None:
    """Weekly work calendar screenshots (main area estimates the full week, today from that schedule)."""
    st.divider()
    st.subheader("Work calendar (weekly upload)")
    _ensure_work_cal_week_monday_state()
    st.caption(
        "Upload **once per week**: full-week view (wide shot or multiple captures). "
        "Pick any day in that week — the app uses **Monday–Sunday** for that week."
    )
    st.date_input(
        "Work week (any day in the week)",
        key="work_cal_week_monday",
    )
    wf = st.file_uploader(
        "Work calendar screenshots (week view)",
        type=["png", "jpg", "jpeg", "webp", "gif"],
        accept_multiple_files=True,
        key="sidebar_work_cal_upload",
    )
    if wf:
        st.session_state["calendar_image_bytes"] = [f.getvalue() for f in wf]
        st.caption(
            f"**{len(wf)}** file(s) stored — use **Estimate work week from screenshots** in the main view."
        )


def render_apple_calendar_sidebar_controls() -> None:
    """Personal Apple / iCloud or ICS feed → `meeting_hours_personal`."""
    st.divider()
    st.subheader("Apple / iCloud (personal)")
    st.caption(
        "App-specific password at [appleid.apple.com](https://appleid.apple.com) → Security, "
        "or a read-only **ICS** / webcal link from Calendar.app (Share). "
        "Optional filter: `ICLOUD_CALENDAR_NAME` (substring match)."
    )
    apple_id = _env_or_secret("ICLOUD_APPLE_ID", "")
    app_pw = _env_or_secret("ICLOUD_APP_PASSWORD", "")
    cal_filter = _env_or_secret("ICLOUD_CALENDAR_NAME", "")
    ics_url = _env_or_secret("APPLE_CALENDAR_ICS_URL", "")

    if not ((apple_id and app_pw) or ics_url.strip()):
        st.caption(
            "Set **`ICLOUD_APPLE_ID`** + **`ICLOUD_APP_PASSWORD`** or **`APPLE_CALENDAR_ICS_URL`** "
            "in env or `.streamlit/secrets.toml`."
        )
        return

    if ics_url.strip():
        if st.button("Pull personal hours (ICS)", key="sidebar_apple_ics", width="stretch"):
            try:
                ev, h, err = parse_ics_feed_events_and_hours(ics_url, _session_date("dashboard_selected_date"))
                if err:
                    st.error(err)
                else:
                    st.session_state.meeting_hours_personal = float(h)
                    st.session_state["personal_calendar_day_events"] = ev
                    st.session_state["personal_calendar_events_meta"] = str(
                        _session_date("dashboard_selected_date")
                    )
                    st.session_state.pop("personal_calendar_events_load_error", None)
                    n = sum(1 for x in ev if not x.get("all_day"))
                    st.success(f"Personal blocked: **{h:.2f}** h. _{n} timed event(s)._")
                st.rerun()
            except Exception as e:
                st.error(str(e))

    if apple_id and app_pw:
        if not icloud_caldav_ready():
            st.warning(
                "iCloud CalDAV needs **caldav** and **icalendar**. In this project’s folder run: "
                "`pip install -r requirements.txt` (or `.venv/bin/pip install caldav icalendar`), "
                "then use **Rerun** or restart Streamlit."
            )
        elif st.button("Pull personal hours (iCloud)", key="sidebar_apple_caldav", width="stretch"):
            try:
                ev, h, err = parse_icloud_calendars_events_and_hours(
                    apple_id,
                    app_pw,
                    _session_date("dashboard_selected_date"),
                    calendar_name_filter=cal_filter,
                )
                if err:
                    st.error(err)
                else:
                    st.session_state.meeting_hours_personal = float(h)
                    st.session_state["personal_calendar_day_events"] = ev
                    st.session_state["personal_calendar_events_meta"] = str(
                        _session_date("dashboard_selected_date")
                    )
                    st.session_state.pop("personal_calendar_events_load_error", None)
                    n = sum(1 for x in ev if not x.get("all_day"))
                    st.success(f"Personal blocked: **{h:.2f}** h. _{n} timed event(s)._")
                st.rerun()
            except Exception as e:
                st.error(str(e))


def render_google_calendar_sidebar_controls() -> None:
    """Optional Google Calendar → work blocked hours for the dashboard recon date."""
    st.divider()
    st.subheader("Google Calendar")
    st.caption("Optional — sets **work** blocked hours for the **recon date** (main date switcher).")
    cal_id = st.text_input("Calendar ID", value="primary", key="sidebar_cal_id")
    if Credentials is None or build is None:
        st.caption("Install Google Calendar client libraries to enable pull.")
        return
    service = calendar_service_from_token()
    if service is None:
        st.caption(f"Add `{CREDENTIALS_PATH.name}` to `{ROOT}`, then authorize once.")
        if CREDENTIALS_PATH.is_file() and st.button(
            "Authorize Calendar", key="sidebar_cal_auth", width="stretch"
        ):
            try:
                run_calendar_oauth()
                st.success("Authorized. Reload.")
                st.stop()
            except Exception as e:  # pragma: no cover
                st.error(str(e))
    else:
        if st.button(
            "Pull meeting hours (recon date)", key="sidebar_cal_pull", width="stretch"
        ):
            try:
                rd = _session_date("dashboard_selected_date")
                mh = sum_event_hours_for_day(service, rd, cal_id)
                st.session_state.meeting_hours_work = float(mh)
                st.session_state["google_hours_applied_for"] = rd.isoformat()
                st.success(
                    f"Work blocked **{rd.isoformat()}**: **{mh:.2f}** h (main total = work + personal)."
                )
                st.rerun()
            except Exception as e:
                st.error(str(e))


def gemini_api_key() -> Optional[str]:
    """Resolve API key: applied session copy, env, Streamlit secrets, then raw sidebar field."""
    try:
        applied = st.session_state.get("_gemini_applied")
        if applied and str(applied).strip():
            return str(applied).strip()
    except (AttributeError, TypeError):
        pass
    for env_name in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        v = os.environ.get(env_name, "").strip()
        if v:
            return v
    try:
        sec = st.secrets
        for k in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
            raw = sec.get(k)
            if raw is not None and str(raw).strip():
                return str(raw).strip()
        g = sec.get("google")
        if isinstance(g, dict) and g.get("api_key"):
            gk = str(g["api_key"]).strip()
            if gk:
                return gk
    except (FileNotFoundError, KeyError, TypeError, RuntimeError):
        pass
    try:
        pasted = st.session_state.get("user_gemini_api_key")
        if pasted and str(pasted).strip():
            return str(pasted).strip()
    except (AttributeError, TypeError):
        pass
    return None


def configure_gemini() -> bool:
    if not genai:
        return False
    key = gemini_api_key()
    if not key:
        return False
    genai.configure(api_key=key)
    return True


def gemini_model_name() -> str:
    v = os.environ.get("GEMINI_MODEL", "").strip()
    if v:
        return v
    try:
        m = st.secrets.get("GEMINI_MODEL")
        if m is not None and str(m).strip():
            return str(m).strip()
    except Exception:
        pass
    return DEFAULT_GEMINI_MODEL


def gemini_estimate_meeting_hours(image_bytes_list: List[bytes]) -> Tuple[float, str]:
    if not genai or not Image:
        return 0.0, "Gemini or Pillow not available."
    model = genai.GenerativeModel(gemini_model_name())
    prompt = """These images are screenshots of the user's **work** calendar for ONE day.
Estimate how many hours are blocked today by work meetings, calls, or fixed work appointments.
Ignore personal calendars if visible; ignore generic "Focus" or "Deep work" unless clearly external meetings.
Reply with ONLY valid JSON, no markdown:
{"meeting_hours": <number>, "note": "<one short sentence>"}"""
    parts: List[Any] = [prompt]
    for b in image_bytes_list:
        parts.append(Image.open(io.BytesIO(b)))
    resp = model.generate_content(parts)
    text = (resp.text or "").strip()
    m = re.search(r"\{[^{}]+\}", text, re.DOTALL)
    if m:
        try:
            obj = json.loads(m.group())
            h = float(obj.get("meeting_hours", 0))
            note = str(obj.get("note", "")).strip()
            return max(0.0, min(h, 24.0)), note
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    return 0.0, "Could not parse model output; enter hours manually."


def week_start_monday(d: date) -> date:
    """ISO week: Monday .. Sunday."""
    return d - timedelta(days=d.weekday())


def expected_week_day_keys(week_start_mon: date) -> List[str]:
    return [(week_start_mon + timedelta(days=i)).isoformat() for i in range(7)]


def _extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    """Parse first top-level JSON object from model text."""
    text = (text or "").strip()
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    out = json.loads(text[start : i + 1])
                    return out if isinstance(out, dict) else None
                except json.JSONDecodeError:
                    return None
    return None


def normalize_work_week_hours(
    raw_days: Any,
    week_start_mon: date,
) -> Dict[str, float]:
    """Merge model `days` map onto the seven expected ISO dates; cap 0..24."""
    expected = expected_week_day_keys(week_start_mon)
    out: Dict[str, float] = {k: 0.0 for k in expected}
    if not isinstance(raw_days, dict):
        return out
    for k, v in raw_days.items():
        ks = str(k).strip()[:10]
        if ks in out:
            try:
                out[ks] = max(0.0, min(24.0, float(v)))
            except (TypeError, ValueError):
                pass
    return out


def week_load_summary_line(hours_by_day: Dict[str, float], week_start_mon: date) -> str:
    """One line for Architect: peaks and light days."""
    if not hours_by_day:
        return ""
    keys = expected_week_day_keys(week_start_mon)
    parts: List[str] = []
    for k in keys:
        h = float(hours_by_day.get(k, 0.0))
        d = date.fromisoformat(k)
        parts.append((d, h))
    if not parts:
        return ""
    peak = max(parts, key=lambda x: x[1])
    light = min(parts, key=lambda x: x[1])
    return (
        f"Week load ({week_start_mon.isoformat()} week): "
        f"heaviest {peak[0].strftime('%a')} {peak[1]:.1f}h, "
        f"lightest {light[0].strftime('%a')} {light[1]:.1f}h."
    )


def gemini_analyze_work_calendar_week(
    image_bytes_list: List[bytes],
    week_start_mon: date,
) -> Tuple[Dict[str, float], str]:
    """Estimate work meeting/fixed-block hours per day for Mon–Sun week from screenshot(s)."""
    if not genai or not Image:
        return {}, "Gemini or Pillow not available."
    expected = expected_week_day_keys(week_start_mon)
    dates_line = ", ".join(expected)
    model = genai.GenerativeModel(gemini_model_name())
    prompt = f"""These images are screenshots of the user's **work** calendar showing a **full week** (or the full work week visible in one or more captures).
Estimate how many hours each **calendar day** is blocked by work meetings, calls, or fixed work appointments.
Week starts Monday {week_start_mon.isoformat()}. Include **exactly** these seven dates as keys in "days" (ISO date strings YYYY-MM-DD):
{dates_line}
Rules:
- Only **work** calendar load; ignore personal calendars if visible.
- Ignore generic "Focus" or "Deep work" unless clearly external meetings.
- Hours per day: 0–24 (sum of timed blocks that day overlapping that day).
Reply with ONLY valid JSON, no markdown:
{{"week_start": "{week_start_mon.isoformat()}", "days": {{"YYYY-MM-DD": <number>, ... (seven keys)}}, "note": "<one short sentence>"}}"""
    parts: List[Any] = [prompt]
    for b in image_bytes_list:
        parts.append(Image.open(io.BytesIO(b)))
    resp = model.generate_content(parts)
    text = (resp.text or "").strip()
    obj = _extract_json_object(text)
    if not obj:
        return {}, "Could not parse model output; enter hours manually."
    raw_days = obj.get("days")
    note = str(obj.get("note", "")).strip()
    merged = normalize_work_week_hours(raw_days, week_start_mon)
    return merged, note or "Weekly work estimate."


def gemini_architect_brief(
    tasks_summary: str,
    meeting_hours_work: float,
    meeting_hours_personal: float,
    meeting_hours_total: float,
    work_hours: float,
    arch_pct: float,
    week_load_summary: str = "",
) -> str:
    if not genai:
        return "Install google-generativeai and set a Gemini API key (env or secrets)."
    model = genai.GenerativeModel(gemini_model_name())
    week_ctx = (week_load_summary or "").strip()
    week_block = f"- Weekly work load context: {week_ctx}\n" if week_ctx else ""
    prompt = f"""You are a concise chief of staff for an executive in deep work mode.
Context for today:
- Work window (hours): {work_hours}
- Work meeting / fixed-block hours (today): {meeting_hours_work:.2f}
- Personal meeting / fixed-block hours: {meeting_hours_personal:.2f}
- Total meeting load: {meeting_hours_total:.2f}
- Estimated architecture / build time %: {arch_pct:.1f}%
{week_block}- Task snapshot: {tasks_summary or "(none)"}

Give 3-5 bullet points: protect architect time, sequence the morning, one ruthless cut if overloaded; when weekly context is present, tie advice to the shape of the week (heavy days vs recovery days).
Tone: direct, professional, no fluff."""
    resp = model.generate_content(prompt)
    return (resp.text or "").strip()


def _protocol_known_ids() -> set[str]:
    return {x["id"] for x in PROTOCOL_ITEMS}


def _normalize_protocol_day(d: Any) -> Dict[str, bool]:
    if not isinstance(d, dict):
        return {item["id"]: False for item in PROTOCOL_ITEMS}
    return {item["id"]: bool(d.get(item["id"], False)) for item in PROTOCOL_ITEMS}


def _is_legacy_protocol_flat(raw: Dict[str, Any]) -> bool:
    if "history" in raw or "version" in raw:
        return False
    known = _protocol_known_ids()
    keys = set(raw.keys())
    if not keys or not keys <= known:
        return False
    return all(isinstance(raw[k], bool) for k in keys)


def _load_protocol_bundle() -> Dict[str, Any]:
    """Load v2 `{version, history, neck_cm}`; v1 `{version, history}`; legacy flat → empty."""
    empty: Dict[str, Any] = {"version": 2, "history": {}, "neck_cm": {}}
    if not PROTOCOL_STATE_PATH.is_file():
        return empty
    try:
        raw = json.loads(PROTOCOL_STATE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return empty
    if not isinstance(raw, dict):
        return empty
    neck_cm: Dict[str, float] = {}
    raw_nc = raw.get("neck_cm")
    if isinstance(raw_nc, dict):
        for k, v in raw_nc.items():
            ks = str(k).strip()[:10]
            if not ks:
                continue
            try:
                neck_cm[ks] = float(v)
            except (TypeError, ValueError):
                continue
    if isinstance(raw.get("history"), dict):
        history: Dict[str, Dict[str, bool]] = {}
        for dk, dv in raw["history"].items():
            if isinstance(dk, str) and isinstance(dv, dict):
                history[dk] = _normalize_protocol_day(dv)
        return {"version": 2, "history": history, "neck_cm": neck_cm}
    if _is_legacy_protocol_flat(raw):
        return empty
    return empty


def _trim_protocol_history(history: Dict[str, Dict[str, bool]]) -> Dict[str, Dict[str, bool]]:
    cutoff = date.today() - timedelta(days=PROTOCOL_HISTORY_TRIM_DAYS)
    out: Dict[str, Dict[str, bool]] = {}
    for k, v in history.items():
        try:
            dk = date.fromisoformat(k)
        except (TypeError, ValueError):
            continue
        if dk >= cutoff:
            out[k] = v
    return out


def _save_protocol_bundle(
    history: Dict[str, Dict[str, bool]],
    neck_cm: Optional[Dict[str, float]] = None,
) -> None:
    trimmed = _trim_protocol_history(history)
    existing_neck: Dict[str, float] = {}
    if PROTOCOL_STATE_PATH.is_file():
        try:
            prev = json.loads(PROTOCOL_STATE_PATH.read_text(encoding="utf-8"))
            pnc = prev.get("neck_cm")
            if isinstance(pnc, dict):
                for k, v in pnc.items():
                    ks = str(k).strip()[:10]
                    if not ks:
                        continue
                    try:
                        existing_neck[ks] = float(v)
                    except (TypeError, ValueError):
                        continue
        except (json.JSONDecodeError, OSError):
            pass
    neck_out = dict(existing_neck)
    if neck_cm is not None:
        neck_out.update({str(k)[:10]: float(v) for k, v in neck_cm.items()})
    payload = {"version": 2, "history": trimmed, "neck_cm": neck_out}
    PROTOCOL_STATE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _week_dates_monday_sunday(d: date) -> List[date]:
    mon = d - timedelta(days=d.weekday())
    return [mon + timedelta(days=i) for i in range(7)]


def _ensure_protocol_session_for_today() -> None:
    """Hydrate history + today’s checkbox defaults; reset widget keys when the calendar day changes."""
    today = date.today()
    today_s = today.isoformat()
    if st.session_state.get("protocol_anchor_day") != today_s:
        bundle = _load_protocol_bundle()
        st.session_state.protocol_history = dict(bundle.get("history") or {})
        st.session_state.protocol_neck_cm = dict(bundle.get("neck_cm") or {})
        st.session_state.protocol_anchor_day = today_s
        for it in PROTOCOL_ITEMS:
            st.session_state.pop(f"proto_{it['id']}", None)
        snap = st.session_state.protocol_history.get(today_s, {})
        st.session_state.protocol_state = _normalize_protocol_day(snap)
    else:
        if "protocol_history" not in st.session_state:
            bundle = _load_protocol_bundle()
            st.session_state.protocol_history = dict(bundle.get("history") or {})
            st.session_state.protocol_neck_cm = dict(bundle.get("neck_cm") or {})
        if "protocol_neck_cm" not in st.session_state:
            st.session_state.protocol_neck_cm = dict(_load_protocol_bundle().get("neck_cm") or {})
        if "protocol_state" not in st.session_state:
            snap = st.session_state.protocol_history.get(today_s, {})
            st.session_state.protocol_state = _normalize_protocol_day(snap)


def render_protocol_week_summary(today: date) -> None:
    """Plotly heatmap + streak mood + optional neck_cm chart + week table."""
    history: Dict[str, Dict[str, bool]] = st.session_state.get("protocol_history") or {}
    neck_cm: Dict[str, float] = dict(st.session_state.get("protocol_neck_cm") or {})
    protocol_ui.render_protocol_week_dashboard(st, today, history, PROTOCOL_ITEMS, neck_cm)


def inject_theme_css() -> None:
    """Monolith V4 — Industrial Amber: Obsidian base, zinc slabs, Inter / Playfair typography."""
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:ital,wght@0,900;1,900&family=Playfair+Display:ital,wght@0,400..900;1,400..900&display=swap');

        :root {
            --titan-bg: #070708;
            --titan-amber: #f59e0b;
            --titan-zinc: #18181b;
            --titan-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
            --titan-divider: rgba(255, 255, 255, 0.05);
            --mntn-gold: #f59e0b;
            --mntn-gold-dim: rgba(245, 158, 11, 0.85);
            --mntn-fog: rgba(232, 238, 245, 0.72);
            --mntn-navy: #070708;
            --mntn-card: rgba(24, 24, 27, 0.88);
            --mntn-img: none;
        }

        html, body, [class*="css"] {
            font-family: 'Inter', system-ui, sans-serif;
            font-size: 15px;
            color-scheme: dark;
        }

        .stApp {
            background-color: #070708;
            background-image:
                linear-gradient(180deg, rgba(7, 7, 8, 0.98) 0%, rgba(12, 12, 14, 0.99) 45%, rgba(7, 7, 8, 1) 100%),
                radial-gradient(ellipse 120% 80% at 50% -20%, rgba(245, 158, 11, 0.06), transparent 55%);
            background-size: cover;
            background-position: center 20%;
            background-attachment: fixed;
            color: var(--mntn-fog);
        }

        .main .block-container {
            padding-top: 0 !important;
            padding-bottom: 3rem !important;
            padding-left: clamp(1rem, 4vw, 2.5rem) !important;
            padding-right: clamp(1rem, 4vw, 2.5rem) !important;
            max-width: 56rem;
        }

        [data-testid="stHeader"] { background: transparent !important; }
        [data-testid="stDecoration"] { display: none; }

        [data-testid="stSidebar"] {
            background: rgba(24, 24, 27, 0.94) !important;
            border-right: 1px solid var(--titan-divider);
            backdrop-filter: blur(16px);
        }
        [data-testid="stSidebar"] .block-container {
            padding-top: 1.5rem !important;
        }
        [data-testid="stSidebar"] label, [data-testid="stSidebar"] p, [data-testid="stSidebar"] span,
        [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
            color: var(--mntn-fog) !important;
        }

        section.main { counter-reset: mntn-sec; }

        div[data-testid="stVerticalBlock"] > div[data-testid="element-container"] {
            margin-bottom: 0.35rem;
        }

        /* App h1 (rare) */
        h1:not(.mntn-hero__headline) {
            font-family: 'Playfair Display', Georgia, serif !important;
            font-weight: 500 !important;
            color: #fff !important;
            letter-spacing: 0.02em !important;
            border-bottom: 1px solid rgba(247, 212, 145, 0.25);
            padding-bottom: 0.5rem;
        }

        h2 {
            font-family: 'Inter', system-ui, sans-serif !important;
            font-size: 0.72rem !important;
            font-weight: 900 !important;
            font-style: italic !important;
            text-transform: uppercase !important;
            letter-spacing: -0.045em !important;
            color: var(--titan-amber) !important;
            margin-top: 0.5rem !important;
        }
        h2::before {
            content: "";
            display: block;
            width: 2.5rem;
            height: 2px;
            background: var(--titan-amber);
            margin-bottom: 0.65rem;
        }

        h3 {
            font-family: 'Playfair Display', Georgia, serif !important;
            font-weight: 500 !important;
            color: #fff !important;
            font-size: 1.05rem !important;
            letter-spacing: 0.02em !important;
        }

        [data-testid="stMarkdownContainer"] p,
        [data-testid="stMarkdownContainer"] li,
        [data-testid="stMarkdownContainer"] td {
            color: rgba(232, 238, 245, 0.88) !important;
            line-height: 1.65;
        }
        [data-testid="stMarkdownContainer"] strong { color: #fff !important; }
        [data-testid="stMarkdownContainer"] a {
            color: var(--mntn-gold) !important;
            text-decoration: none;
            border-bottom: 1px solid rgba(247, 212, 145, 0.35);
        }

        /* Section panels + giant numerals (only for h2 without .mntn-no-sec-num) */
        div[data-testid="stVerticalBlock"] > div:has(> div[data-testid="stMarkdown"] h2) {
            position: relative;
            overflow: visible;
            z-index: 1;
            margin-bottom: 2.75rem;
            margin-top: 0.5rem;
            padding: 2rem 1.5rem 1.75rem 2rem;
            background: var(--titan-zinc);
            border: 1px solid var(--titan-divider);
            border-radius: 10px;
            backdrop-filter: blur(14px);
            box-shadow: var(--titan-shadow);
        }
        div[data-testid="stVerticalBlock"] > div:has(> div[data-testid="stMarkdown"] h2:not(.mntn-no-sec-num)) {
            counter-increment: mntn-sec;
        }
        div[data-testid="stVerticalBlock"] > div:has(> div[data-testid="stMarkdown"] h2:not(.mntn-no-sec-num))::before {
            content: counter(mntn-sec, decimal-leading-zero);
            position: absolute;
            left: 0.15rem;
            top: 0.2rem;
            font-family: 'Montserrat', sans-serif;
            font-weight: 700;
            font-size: clamp(3.5rem, 14vw, 7rem);
            line-height: 1;
            color: rgba(232, 238, 245, 0.2);
            z-index: 0;
            pointer-events: none;
        }
        div[data-testid="stVerticalBlock"] > div:has(> div[data-testid="stMarkdown"] h2) > div {
            position: relative;
            z-index: 1;
        }

        div[data-testid="stVerticalBlock"] > div:has(> div[data-testid="stMarkdown"] h2):nth-of-type(even) {
            margin-left: clamp(0px, 5vw, 3rem);
        }
        div[data-testid="stVerticalBlock"] > div:has(> div[data-testid="stMarkdown"] h2):nth-of-type(odd) {
            margin-right: clamp(0px, 5vw, 2rem);
        }

        .ragstone-kicker {
            font-family: 'Montserrat', sans-serif;
            color: var(--mntn-gold-dim);
            font-size: 0.62rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.28em;
        }

        .ragstone-warning {
            border-left: 2px solid var(--mntn-gold);
            background: rgba(247, 212, 145, 0.08);
            padding: 0.65rem 1rem;
            border-radius: 0 8px 8px 0;
            margin: 0.75rem 0;
            color: var(--mntn-fog) !important;
            font-size: 0.875rem;
        }

        .ragstone-danger {
            border-left: 2px solid #e85d4c;
            background: rgba(232, 93, 76, 0.1);
            padding: 0.65rem 1rem;
            border-radius: 0 8px 8px 0;
            margin: 0.75rem 0;
            color: var(--mntn-fog) !important;
            font-size: 0.875rem;
        }

        .ragstone-metric {
            font-family: 'Playfair Display', serif;
            font-size: 2.15rem;
            font-weight: 600;
            color: #fff;
            letter-spacing: 0.03em;
        }

        /* Hero (full-bleed) */
        .mntn-hero {
            position: relative;
            width: 100vw;
            max-width: 100vw;
            left: 50%;
            right: 50%;
            margin-left: -50vw;
            margin-right: -50vw;
            min-height: 42vh;
            margin-bottom: 2.5rem;
            background-image:
                linear-gradient(180deg, rgba(7, 7, 8, 0.2) 0%, rgba(24, 24, 27, 0.75) 55%, rgba(7, 7, 8, 0.96) 100%),
                radial-gradient(ellipse 80% 60% at 50% 0%, rgba(245, 158, 11, 0.09), transparent 60%);
            background-size: cover;
            background-position: center 35%;
            display: flex;
            flex-direction: column;
            justify-content: flex-end;
            padding: 1.25rem clamp(1.25rem, 5vw, 3.5rem) 2.75rem;
            box-sizing: border-box;
            box-shadow: var(--titan-shadow);
            border-bottom: 1px solid var(--titan-divider);
            z-index: 4;
        }
        .mntn-nav {
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 1.25rem clamp(1.25rem, 5vw, 3.5rem);
            font-family: 'Inter', system-ui, sans-serif;
            font-size: 0.65rem;
            font-weight: 900;
            font-style: italic;
            letter-spacing: -0.03em;
            text-transform: uppercase;
            color: rgba(255,255,255,0.92);
        }
        .mntn-logo { font-size: 0.85rem; letter-spacing: 0.35em; }
        .mntn-nav-links { opacity: 0.85; }
        .mntn-nav-account { opacity: 0.75; font-size: 0.65rem; }
        .mntn-hero__content { max-width: 42rem; }
        .mntn-hero__tag {
            display: flex;
            align-items: center;
            gap: 0.65rem;
            font-family: 'Montserrat', sans-serif;
            font-size: 0.65rem;
            font-weight: 600;
            letter-spacing: 0.28em;
            text-transform: uppercase;
            color: var(--titan-amber);
            margin: 0 0 0.75rem 0;
        }
        .mntn-hero__tagline {
            display: inline-block;
            width: 2.5rem;
            height: 2px;
            background: var(--mntn-gold);
        }
        .mntn-hero__headline {
            font-family: 'Playfair Display', Georgia, serif !important;
            font-size: clamp(1.85rem, 5.5vw, 2.85rem) !important;
            font-weight: 500 !important;
            line-height: 1.15 !important;
            color: #fff !important;
            margin: 0 0 1rem 0 !important;
            letter-spacing: 0.02em !important;
            border: none !important;
        }
        .mntn-hero__hint {
            font-family: 'Montserrat', sans-serif;
            font-size: 0.68rem;
            letter-spacing: 0.22em;
            text-transform: uppercase;
            color: rgba(255,255,255,0.45);
            margin: 0;
        }
        .mntn-hero__side {
            position: absolute;
            bottom: 2.5rem;
            font-family: 'Montserrat', sans-serif;
            font-size: 0.58rem;
            letter-spacing: 0.25em;
            text-transform: uppercase;
            color: rgba(255,255,255,0.35);
            writing-mode: vertical-rl;
            transform: rotate(180deg);
        }
        .mntn-hero__side--left { left: clamp(0.75rem, 3vw, 2rem); }
        .mntn-hero__side--right {
            right: clamp(0.75rem, 3vw, 2rem);
            writing-mode: vertical-rl;
            transform: none;
            text-align: center;
        }
        .mntn-dots { display: block; margin-top: 0.5rem; letter-spacing: 0.15em; }

        .stTextInput input, .stNumberInput input, textarea, [data-baseweb="textarea"] textarea {
            background: rgba(24, 24, 27, 0.92) !important;
            color: var(--mntn-fog) !important;
            border: 1px solid var(--titan-divider) !important;
            border-radius: 8px !important;
        }
        .stSlider [data-baseweb="slider"] { background-color: rgba(255, 255, 255, 0.1); }

        .stButton > button {
            font-family: 'Inter', system-ui, sans-serif !important;
            font-weight: 700 !important;
            letter-spacing: 0.12em !important;
            text-transform: uppercase !important;
            font-size: 0.6rem !important;
            font-style: italic !important;
            background: transparent !important;
            color: var(--titan-amber) !important;
            border: 1px solid rgba(245, 158, 11, 0.45) !important;
            border-radius: 8px !important;
        }
        .stButton > button:hover {
            background: rgba(245, 158, 11, 0.12) !important;
            border-color: var(--titan-amber) !important;
            color: #fff !important;
        }

        [data-testid="stFileUploader"] section {
            border: 1px dashed rgba(247, 212, 145, 0.25) !important;
            border-radius: 10px !important;
            background: rgba(6, 14, 28, 0.5) !important;
        }
        [data-testid="stImage"] img {
            border-radius: 10px !important;
            box-shadow: 0 20px 50px rgba(0, 0, 0, 0.45) !important;
        }

        hr {
            border: none;
            border-top: 1px solid rgba(255, 255, 255, 0.08);
            margin: 1.5rem 0;
        }

        .stCaption, [data-testid="stCaptionContainer"] {
            color: rgba(232, 238, 245, 0.55) !important;
            font-size: 0.78rem !important;
        }

        div[data-testid="stAlert"] {
            border-radius: 8px !important;
            background: rgba(6, 14, 28, 0.75) !important;
            border: 1px solid rgba(255, 255, 255, 0.08) !important;
            color: var(--mntn-fog) !important;
        }

        .streamlit-expanderHeader {
            background: rgba(255, 255, 255, 0.04) !important;
            border-radius: 8px !important;
        }

        label { color: rgba(232, 238, 245, 0.85) !important; }

        [data-testid="stSidebar"] h2::before {
            display: none !important;
        }
        [data-testid="stSidebar"] h2 {
            color: var(--mntn-fog) !important;
            font-size: 0.75rem !important;
            letter-spacing: 0.12em !important;
        }
        [data-testid="stSidebar"] h3 {
            font-family: 'Montserrat', sans-serif !important;
            font-size: 0.68rem !important;
            font-weight: 600 !important;
            text-transform: uppercase !important;
            letter-spacing: 0.16em !important;
            color: var(--mntn-gold-dim) !important;
        }

        .power-slot {
            font-family: 'Inter', system-ui, sans-serif !important;
            font-size: 0.62rem !important;
            font-weight: 900 !important;
            font-style: italic !important;
            letter-spacing: -0.03em !important;
            text-transform: uppercase !important;
            color: var(--titan-amber) !important;
            margin: 0 0 0.35rem 0 !important;
        }
        .power-title {
            font-family: 'Playfair Display', Georgia, serif !important;
            font-size: 1.15rem !important;
            font-weight: 600 !important;
            color: #fff !important;
            margin: 0 0 0.5rem 0 !important;
            line-height: 1.25 !important;
        }

        .focus-score-metric {
            font-family: 'Playfair Display', Georgia, serif !important;
            font-size: 2.1rem !important;
            font-weight: 600 !important;
            color: #f7d491 !important;
            margin: 0.15rem 0 0.35rem 0 !important;
        }
        .focus-score-metric.focus-score--danger {
            color: #ff6b6b !important;
            text-shadow: 0 0 18px rgba(255, 80, 80, 0.35);
        }
        .focus-score-caption {
            font-size: 0.72rem !important;
            letter-spacing: 0.14em !important;
            text-transform: uppercase !important;
            color: rgba(232, 238, 245, 0.55) !important;
            margin: 0 0 0.25rem 0 !important;
        }

        .protocol-monolith {
            border-radius: 10px;
            padding: 0.65rem 0.85rem;
            margin: 0.5rem 0 0.75rem 0;
            border: 1px solid rgba(247, 212, 145, 0.12);
        }
        .protocol-dashboard--cold.protocol-monolith {
            background: rgba(10, 16, 28, 0.55);
            border-color: rgba(120, 140, 170, 0.2);
        }
        .protocol-dashboard--hot.protocol-monolith {
            background: rgba(28, 22, 10, 0.45);
            border-color: rgba(247, 212, 145, 0.28);
            box-shadow: 0 0 24px rgba(247, 212, 145, 0.08);
        }
        .protocol-streak-line {
            margin: 0 !important;
            font-size: 0.88rem !important;
            color: rgba(232, 238, 245, 0.82) !important;
        }
        .protocol-streak-label {
            font-size: 0.65rem !important;
            letter-spacing: 0.18em !important;
            text-transform: uppercase !important;
            color: rgba(247, 212, 145, 0.75) !important;
            margin-right: 0.35rem !important;
        }
        .protocol-dashboard--cold .protocol-streak-line {
            color: rgba(170, 186, 210, 0.88) !important;
        }

        .recon-date-nav-label {
            font-size: 0.65rem !important;
            letter-spacing: 0.2em !important;
            text-transform: uppercase !important;
            color: rgba(247, 212, 145, 0.55) !important;
            margin: 0.25rem 0 0.15rem 0 !important;
        }

        .efficiency-hero-label {
            font-size: 0.68rem !important;
            letter-spacing: 0.16em !important;
            text-transform: uppercase !important;
            color: rgba(232, 238, 245, 0.5) !important;
            margin: 0.35rem 0 0.1rem 0 !important;
        }
        .efficiency-hero {
            font-family: 'Playfair Display', Georgia, serif !important;
            font-size: 2.35rem !important;
            font-weight: 600 !important;
            color: #f7d491 !important;
            margin: 0 0 0.2rem 0 !important;
            line-height: 1.1 !important;
        }
        .efficiency-hero--danger {
            color: #ff6b6b !important;
            text-shadow: 0 0 20px rgba(255, 70, 70, 0.35);
        }
        .efficiency-hero-sub {
            font-size: 0.78rem !important;
            color: rgba(160, 176, 198, 0.9) !important;
            margin: 0 0 0.75rem 0 !important;
        }

        .protocol-well-recessed {
            box-shadow: inset 0 1px 0 rgba(255,255,255,0.04), inset 0 -2px 12px rgba(0,0,0,0.45) !important;
            background: rgba(4, 7, 12, 0.92) !important;
            border-color: rgba(80, 96, 120, 0.25) !important;
        }

        div[data-testid="element-container"]:has(p.power-slot) {
            box-shadow: var(--titan-shadow) !important;
            border-radius: 12px !important;
            border: 1px solid var(--titan-divider) !important;
            background: linear-gradient(165deg, rgba(24, 24, 27, 0.98), rgba(7, 7, 8, 0.99)) !important;
            position: relative;
            z-index: 2;
        }
        .titan-monolith-stack {
            position: relative;
            z-index: 3;
        }
        @keyframes titanTrioSlide {
            from { transform: translateX(14px); opacity: 0.5; }
            to { transform: translateX(0); opacity: 1; }
        }
        .titan-trio-slide div[data-testid="element-container"]:has(p.power-slot) {
            animation: titanTrioSlide 0.3s ease-out !important;
        }
        .identity-alert {
            border-left: 3px solid #dc2626;
            background: rgba(127, 29, 29, 0.35);
            padding: 0.65rem 1rem;
            border-radius: 0 8px 8px 0;
            margin: 0.75rem 0;
            color: #fecaca !important;
            font-size: 0.88rem;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.45);
        }
        [data-testid="stSidebar"] .purpose-pillar-slab {
            background: var(--titan-zinc) !important;
            border-left: 3px solid rgba(245, 158, 11, 0.35) !important;
            padding: 0.85rem 1rem !important;
            margin: 0 0 1rem 0 !important;
            border-radius: 2px !important;
            box-shadow: var(--titan-shadow) !important;
        }
        [data-testid="stSidebar"] .purpose-pillar-label {
            font-size: 0.62rem !important;
            letter-spacing: 0.2em !important;
            text-transform: uppercase !important;
            color: rgba(180, 192, 210, 0.55) !important;
            font-weight: 700 !important;
            margin-bottom: 0.45rem !important;
        }
        [data-testid="stSidebar"] .purpose-pillar-text {
            font-family: 'Playfair Display', Georgia, serif !important;
            font-size: 0.78rem !important;
            line-height: 1.55 !important;
            letter-spacing: 0.12em !important;
            font-weight: 500 !important;
            font-style: italic !important;
            color: rgba(228, 234, 244, 0.9) !important;
            margin: 0 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _runway_override_triple(day: date) -> Optional[Tuple[str, str, str]]:
    o = load_runway_override_for_day(day)
    if not o:
        return None
    return (o.start_iso, o.title, o.source)


def _clear_gemini_anchor_cache_for_day(day: date) -> None:
    prefix = f"anchor_ai:{day.isoformat()}:"
    for k in list(st.session_state.keys()):
        if isinstance(k, str) and k.startswith(prefix):
            st.session_state.pop(k, None)


def _ensure_gemini_index_for_day(
    day: date,
    google_evs: List[Dict[str, Any]],
    pev: List[Dict[str, Any]],
    cal_id: str,
) -> Tuple[Optional[int], str]:
    active = active_timed_anchor_list(google_evs, pev)
    if not active:
        return None, ""
    h = anchors_revision_hash(active)
    base = f"anchor_ai:{day.isoformat()}:{cal_id}:{h}"
    if base + ":idx" in st.session_state:
        return int(st.session_state[base + ":idx"]), str(st.session_state.get(base + ":reason") or "")
    if configure_gemini() and genai:
        idx, reason = nominate_hard_anchor_index(genai, gemini_model_name(), active)
        if idx is not None:
            st.session_state[base + ":idx"] = idx
            st.session_state[base + ":reason"] = reason or ""
            return idx, reason or ""
    return None, ""


def render_purpose_pillar_sidebar() -> None:
    """Life-purpose slab at top of sidebar (identity.json)."""
    if st.session_state.get("purpose_pillar_editing"):
        st.caption("Purpose Pillar — edit")
        st.text_area(
            "Purpose text",
            value=identity_store.load_identity_purpose(),
            height=130,
            key="purpose_pillar_edit_area",
            label_visibility="collapsed",
        )
        b1, b2 = st.columns(2)
        with b1:
            if st.button("Save", key="purpose_pillar_save", width="stretch"):
                raw = str(st.session_state.get("purpose_pillar_edit_area") or "").strip()
                identity_store.save_identity_purpose(raw)
                st.session_state.purpose_pillar_editing = False
                st.rerun()
        with b2:
            if st.button("Cancel", key="purpose_pillar_cancel", width="stretch"):
                st.session_state.purpose_pillar_editing = False
                st.rerun()
        return

    purpose = identity_store.load_identity_purpose()
    escaped = html.escape(purpose)
    st.markdown(
        f'<div class="purpose-pillar-slab">'
        f'<div class="purpose-pillar-label">Purpose Pillar</div>'
        f'<p class="purpose-pillar-text">{escaped}</p></div>',
        unsafe_allow_html=True,
    )
    if st.button("Edit", key="purpose_pillar_edit_btn"):
        st.session_state.purpose_pillar_editing = True
        st.rerun()


def _render_kill_zone_caption(zones: List[Tuple[datetime, datetime]], tzinfo) -> None:
    if not zones:
        return
    parts: List[str] = []
    for zs, ze in zones[:12]:
        a = zs.astimezone(tzinfo) if zs.tzinfo else zs.replace(tzinfo=tzinfo)
        b = ze.astimezone(tzinfo) if ze.tzinfo else ze.replace(tzinfo=tzinfo)
        parts.append(
            f"{a.strftime('%I:%M %p').lstrip('0')}–{b.strftime('%I:%M %p').lstrip('0')}"
        )
    st.caption("Deep Work kill zones (2h+ gaps): " + " · ".join(parts))


def _maybe_identity_runway_alert(day: date, rec: DayReadiness, tzinfo) -> None:
    if day != date.today() or rec.integrity_wake is None:
        return
    iw = rec.integrity_wake
    if iw.tzinfo is None:
        iw = iw.replace(tzinfo=tzinfo)
    else:
        iw = iw.astimezone(tzinfo)
    now = datetime.now(tzinfo)
    if now <= iw + timedelta(minutes=15):
        return
    proto = st.session_state.get("protocol_state") or {}
    proto_ok = all(bool(proto.get(x["id"], False)) for x in PROTOCOL_ITEMS)
    if proto_ok:
        return
    st.markdown(
        '<div class="identity-alert"><strong>Identity alert</strong> — Past integrity wake +15m and the '
        "posture protocol is not confirmed. Execute and log the stack.</div>",
        unsafe_allow_html=True,
    )


def inject_tactical_dim_css() -> None:
    """Penalty: 3× Tactical Compression in a row dims the chrome ~20%."""
    if int(st.session_state.get("tactical_compression_streak") or 0) < 3:
        return
    st.markdown(
        "<style>"
        "section.main .block-container, [data-testid=\"stSidebar\"] .block-container "
        "{ opacity: 0.8 !important; filter: brightness(0.82); }"
        "</style>",
        unsafe_allow_html=True,
    )


def _maybe_run_titan_janitor() -> None:
    if st.session_state.get("_titan_janitor_ran"):
        return
    key = todoist_api_key()
    if not key or not requests:
        st.session_state["_titan_janitor_ran"] = True
        return
    try:
        _, _, _ = todoist_service.janitor_close_stale_open_tasks(key)
    except Exception:
        pass
    st.session_state["_titan_janitor_ran"] = True


def render_tomorrow_runway_panel() -> None:
    """EOD-style preview: proposed anchor + integrity wake for calendar tomorrow."""
    tom = date.today() + timedelta(days=1)
    try:
        eod_h = max(0, min(23, int(os.environ.get("RUNWAY_EOD_HOUR", "17"))))
    except ValueError:
        eod_h = 17
    expanded = datetime.now().hour >= eod_h
    with st.expander("Tomorrow — Proposed Runway", expanded=expanded):
        svc = calendar_service_from_token()
        cal_id = str(st.session_state.get("sidebar_cal_id") or "primary").strip() or "primary"
        g_evs: List[Dict[str, Any]] = []
        if svc:
            g_evs = list_google_calendar_events_for_day(svc, tom, cal_id)
        p_evs, _h, p_err = fetch_personal_calendar_events_and_hours_for_day(tom)
        if p_err and p_err != "not_configured":
            st.caption(f"_Personal calendar:_ {p_err}")

        markers = parse_marker_csv(str(st.session_state.get("chief_markers") or ""))
        cfg = ChiefOfStaffConfig(hard_title_markers=markers)
        if st.button("Refresh AI anchor (tomorrow)", key="tomorrow_anchor_refresh"):
            _clear_gemini_anchor_cache_for_day(tom)
            st.rerun()
        gem_idx, gem_note = _ensure_gemini_index_for_day(tom, g_evs, p_evs, cal_id)
        ov = _runway_override_triple(tom)
        anchor = select_integrity_anchor(
            g_evs,
            p_evs,
            cfg,
            runway_override=ov,
            gemini_chosen_index=gem_idx,
        )

        protocols = _identity_protocols_from_sidebar_minutes()
        wake_t = _time_from_ampm(
            int(st.session_state.integ_ws_h12),
            int(st.session_state.integ_ws_min),
            str(st.session_state.integ_ws_ap),
        )
        tzinfo = datetime.now().astimezone().tzinfo
        default_wake = datetime.combine(tom, wake_t).replace(tzinfo=tzinfo)
        rec = build_day_readiness(
            anchor,
            protocols,
            default_wake,
            timedelta(hours=7.5),
            None,
        )
        st.markdown(rec.notification_markdown)
        if gem_note:
            st.caption(f"_AI anchor:_ {gem_note}")

        merged = merged_timed_anchors(g_evs, p_evs)
        lock = load_runway_override_for_day(tom)
        if lock:
            st.caption(f"_Locked anchor for {tom.isoformat()}:_ {lock.title}")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Accept proposal as lock", key="tomorrow_lock_accept", disabled=anchor is None):
                if anchor is not None:
                    save_runway_override_for_day(
                        tom,
                        RunwayDayOverride(
                            start_iso=anchor.start.isoformat(),
                            title=anchor.title,
                            source=anchor.source,
                        ),
                    )
                    st.success("Saved lock for tomorrow.")
                    st.rerun()
        with c2:
            if st.button("Clear lock", key="tomorrow_lock_clear"):
                clear_runway_override_for_day(tom)
                st.rerun()

        if merged:
            labels = []
            for a in merged:
                loc = a.start
                if loc.tzinfo is None:
                    loc = loc.replace(tzinfo=tzinfo)
                else:
                    loc = loc.astimezone(tzinfo)
                labels.append(f"{loc.strftime('%a %I:%M %p').lstrip('0')} · {a.title} ({a.source})")
            pick = st.selectbox(
                "Pick a different timed anchor to lock",
                options=list(range(len(merged))),
                format_func=lambda i: labels[int(i)],
                key="tomorrow_pick_anchor_idx",
            )
            if st.button("Save selected as lock", key="tomorrow_lock_pick"):
                a = merged[int(pick)]
                save_runway_override_for_day(
                    tom,
                    RunwayDayOverride(
                        start_iso=a.start.isoformat(),
                        title=a.title,
                        source=a.source,
                    ),
                )
                st.success("Lock updated.")
                st.rerun()


def render_integrity_runway_section(day: date) -> None:
    """Executive Shift / Integrity Wake-Up, or Preparation Brief when day is in the future."""
    wall_today = date.today()
    forward = day > wall_today
    # Skip giant CSS section numerals so Power Trio stays "03" (Integrity is a sub-runway, not a top chapter).
    st.markdown(
        '<h2 class="mntn-no-sec-num">Integrity Runway</h2>',
        unsafe_allow_html=True,
    )
    if forward:
        st.caption("**Preparation Brief** — Forward Recon (future day)")
    _ensure_integrity_wake_state()
    try:
        ir_box = st.container(border=True)
    except TypeError:
        ir_box = st.container()
    markers = parse_marker_csv(str(st.session_state.get("chief_markers") or ""))
    cfg = ChiefOfStaffConfig(hard_title_markers=markers)
    google_evs: List[Dict[str, Any]] = []
    svc = calendar_service_from_token()
    cal_id = str(st.session_state.get("sidebar_cal_id") or "primary").strip() or "primary"
    if svc:
        google_evs = list_google_calendar_events_for_day(svc, day, cal_id)
    pev = list(st.session_state.get("personal_calendar_day_events") or [])
    tzinfo = datetime.now().astimezone().tzinfo
    zones = compute_deep_work_kill_zones(google_evs, pev, day)

    if st.button("Refresh AI anchor", key=f"integrity_ref_ai_{day.isoformat()}"):
        _clear_gemini_anchor_cache_for_day(day)
        st.rerun()
    gem_idx, gem_note = _ensure_gemini_index_for_day(day, google_evs, pev, cal_id)
    override_t = _runway_override_triple(day)

    if forward:
        brief = build_preparation_brief_markdown(
            day,
            google_evs or None,
            pev or None,
            cfg,
            runway_override=override_t,
            gemini_chosen_index=gem_idx,
        )
        with ir_box:
            st.markdown(brief)
            if gem_note:
                st.caption(f"_AI anchor:_ {gem_note}")
            _render_kill_zone_caption(zones, tzinfo)
        return

    protocols = _identity_protocols_from_sidebar_minutes()
    wake_t = _time_from_ampm(
        int(st.session_state.integ_ws_h12),
        int(st.session_state.integ_ws_min),
        str(st.session_state.integ_ws_ap),
    )
    default_wake = datetime.combine(day, wake_t).replace(tzinfo=tzinfo)
    bed = _parse_optional_bedtime(str(st.session_state.get("integ_bed_text") or ""))
    anchor = select_integrity_anchor(
        google_evs,
        pev,
        cfg,
        runway_override=override_t,
        gemini_chosen_index=gem_idx,
    )
    rec = build_day_readiness(
        anchor,
        protocols,
        default_wake,
        timedelta(hours=7.5),
        bed,
    )
    with ir_box:
        st.markdown(rec.notification_markdown)
        if gem_note:
            st.caption(f"_AI anchor:_ {gem_note}")
        _render_kill_zone_caption(zones, tzinfo)
        _maybe_identity_runway_alert(day, rec, tzinfo)
        sf1, sf2 = st.columns(2)
        with sf1:
            if st.button("Full Protocol shift", key=f"integ_shift_full_{day.isoformat()}"):
                st.session_state["tactical_compression_streak"] = 0
                st.session_state[f"integrity_shift_{day.isoformat()}"] = "full"
                st.rerun()
        with sf2:
            if st.button("Tactical Compression", key=f"integ_shift_tac_{day.isoformat()}"):
                st.session_state["tactical_compression_streak"] = int(
                    st.session_state.get("tactical_compression_streak") or 0
                ) + 1
                st.session_state[f"integrity_shift_{day.isoformat()}"] = "tactical"
                st.rerun()


def _architect_task_rows() -> List[Dict[str, Any]]:
    ranked = list(st.session_state.get("power_ranked_ids") or [])
    by_id: Dict[str, Any] = dict(st.session_state.get("power_tasks_by_id") or {})
    out: List[Dict[str, Any]] = []
    for tid in ranked[:24]:
        t = by_id.get(tid)
        if t:
            out.append(t)
    if out:
        return out
    return list(st.session_state.get("sheet_tasks") or [])


def render_power_trio_section(selected_date: date) -> None:
    """Exactly three sliding-window cards: Combat / Momentum / Admin."""
    if float(st.session_state.get("_power_trio_anim_until") or 0) > time_module.monotonic():
        st.markdown(
            "<style>"
            "div[data-testid='element-container']:has(p.power-slot) { "
            "animation: titanTrioSlide 0.3s ease-out !important; }"
            "</style>",
            unsafe_allow_html=True,
        )
    st.markdown("## Power Trio")
    st.caption("Three tasks. Execute. No project list trance.")
    forward_readonly = selected_date > date.today()
    if forward_readonly:
        st.info("**Forward Recon** — read-only: Gemini and **Executed** are disabled for future days.")
    _perr = str(st.session_state.get("power_rank_error") or "").strip()
    if _perr:
        st.warning(_perr)
    todoist_key = todoist_api_key()
    ranked = list(st.session_state.get("power_ranked_ids") or [])
    by_id: Dict[str, Any] = dict(st.session_state.get("power_tasks_by_id") or {})
    if not todoist_key:
        st.info("Set `TODOIST_API_KEY` and use **Pull all tasks** in the sidebar.")
        return
    if not ranked or not by_id:
        st.info("Sidebar: **Pull all tasks**, then **Refocus (Gemini rank)**.")
        return
    window_ids = ranked[:3]
    labels = ("Combat", "Momentum", "Admin / Ops")
    for slot, tid in enumerate(window_ids):
        task = by_id.get(tid)
        if not task:
            continue
        title = str(task.get("content") or "(no title)")
        proj = str(task.get("project_name") or "")
        try:
            box = st.container(border=True)
        except TypeError:
            box = st.container()
        with box:
            st.markdown(f'<p class="power-slot">{labels[slot]}</p>', unsafe_allow_html=True)
            st.markdown(f'<p class="power-title">{html.escape(title)}</p>', unsafe_allow_html=True)
            if proj:
                st.caption(proj)
            c1, c2 = st.columns(2)
            with c1:
                if slot == 0:
                    if st.button(
                        "Break it down",
                        key=f"pwr_plan_{slot}_{tid}",
                        help="The Plan — 3 steps",
                        disabled=forward_readonly,
                    ):
                        if configure_gemini() and genai:
                            try:
                                st.session_state[f"_plan_{tid}"] = power_trio.gemini_the_plan_three_steps(
                                    genai,
                                    gemini_model_name(),
                                    title,
                                    str(task.get("description") or ""),
                                )
                            except Exception as e:
                                st.session_state[f"_plan_{tid}"] = f"Error: {e}"
                        else:
                            st.session_state[f"_plan_{tid}"] = "Set Gemini API key."
                else:
                    if st.button(
                        "Strike",
                        key=f"pwr_qe_{slot}_{tid}",
                        help="Quick execution",
                        disabled=forward_readonly,
                    ):
                        if configure_gemini() and genai:
                            try:
                                st.session_state[f"_qe_{tid}"] = power_trio.gemini_quick_execution(
                                    genai,
                                    gemini_model_name(),
                                    title,
                                    str(task.get("description") or ""),
                                )
                            except Exception as e:
                                st.session_state[f"_qe_{tid}"] = f"Error: {e}"
                        else:
                            st.session_state[f"_qe_{tid}"] = "Set Gemini API key."
            with c2:
                if st.button("Executed", key=f"pwr_done_{slot}_{tid}", disabled=forward_readonly):
                    try:
                        todoist_service.close_task_rest_v2(todoist_key, tid)
                        st.session_state["_power_trio_anim_until"] = time_module.monotonic() + 0.35
                        if slot == 0:
                            st.session_state.vanguard_executed_deep = (
                                int(st.session_state.get("vanguard_executed_deep") or 0) + 1
                            )
                        elif slot == 1:
                            st.session_state.vanguard_executed_mixed = (
                                int(st.session_state.get("vanguard_executed_mixed") or 0) + 1
                            )
                        else:
                            st.session_state.vanguard_executed_shallow = (
                                int(st.session_state.get("vanguard_executed_shallow") or 0) + 1
                            )
                        ranked_new = todoist_service.sliding_trio_after_complete(ranked, tid)
                        by_id.pop(tid, None)
                        st.session_state["power_ranked_ids"] = ranked_new
                        st.session_state["power_tasks_by_id"] = by_id
                        st.session_state.pop(f"_plan_{tid}", None)
                        st.session_state.pop(f"_qe_{tid}", None)
                        st.session_state["sheet_tasks"] = [
                            by_id[k] for k in ranked_new if k in by_id
                        ]
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))
            pl = st.session_state.get(f"_plan_{tid}")
            if pl:
                st.markdown("**The Plan**")
                st.markdown(str(pl))
            qe = st.session_state.get(f"_qe_{tid}")
            if qe:
                st.markdown("**Strike output**")
                st.markdown(str(qe))


def render_todoist_bucket_cards() -> None:
    """Three-column snapshot when tasks were last pulled from the Todoist API."""
    today = list(st.session_state.get("todoist_today_tasks", []))
    nxt = list(st.session_state.get("todoist_next_focus_tasks", []))
    overdue = list(st.session_state.get("todoist_overdue_tasks", []))
    focus_q = str(st.session_state.get("todoist_last_focus_filter") or "").strip()
    if not focus_q:
        focus_q = DEFAULT_TODOIST_NEXT_FOCUS_FILTER
    st.markdown("### Todoist")
    st.caption("Buckets update when you **Pull tasks from Todoist** in the sidebar.")
    cols = st.columns(3)
    buckets: List[Tuple[str, List[Dict[str, Any]], str]] = [
        ("Overdue", overdue, "Past due"),
        ("Today", today, "Due today"),
        ("Next Focus", nxt, focus_q),
    ]
    for col, (title, bucket, subtitle) in zip(cols, buckets):
        with col:
            try:
                box = st.container(border=True)
            except TypeError:  # pragma: no cover — older Streamlit
                box = st.container()
            with box:
                st.markdown(f"**{title}**")
                st.caption(f"{len(bucket)} · {subtitle}")
                if not bucket:
                    st.markdown('<p style="opacity:0.45;margin:0.5rem 0;">—</p>', unsafe_allow_html=True)
                else:
                    ranked = sorted(bucket, key=lambda x: -int(x.get("priority") or 1))
                    for t in ranked[:25]:
                        pr = int(t.get("priority") or 1)
                        content = str(t.get("content") or "").strip() or "(no title)"
                        if pr == TODOIST_URGENT_PRIORITY:
                            st.markdown(f"- **{content}** `[P1]`")
                        else:
                            st.markdown(f"- [{pr}] {content}")
                    if len(bucket) > 25:
                        st.caption(f"… +{len(bucket) - 25} more")


def _maybe_rerank_power_trio_for_date(selected_date: date) -> None:
    """Re-rank in-memory Todoist tasks for weekday/weekend rules when recon date changes."""
    by_id: Dict[str, Any] = dict(st.session_state.get("power_tasks_by_id") or {})
    if not by_id:
        return
    if str(st.session_state.get("power_rank_anchor_date") or "") == selected_date.isoformat():
        return
    purpose = str(st.session_state.get("power_purpose") or "")
    rstrat = str(st.session_state.get("power_ragstone_strategy") or "")
    scaled = str(st.session_state.get("power_scaled_ops") or "")
    id_sub = power_trio.split_substrings_csv(str(st.session_state.get("power_id_substr") or ""))
    op_sub = power_trio.split_substrings_csv(str(st.session_state.get("power_ops_substr") or ""))
    wd = selected_date.strftime("%A")
    is_weekend = selected_date.weekday() >= 5
    if configure_gemini() and genai:
        ranked, rank_warn = power_trio.rank_tasks_for_power_trio(
            genai,
            gemini_model_name(),
            by_id,
            purpose,
            rstrat,
            scaled,
            wd,
            is_weekend,
            id_sub,
            op_sub,
        )
    else:
        ranked = todoist_service.sort_known_ids_by_priority(by_id, list(by_id.keys()))
        ranked = power_trio.validate_and_fill_order(ranked, list(by_id.keys()))
        rank_warn = ""
    st.session_state["power_ranked_ids"] = ranked
    st.session_state["power_rank_error"] = rank_warn or ""
    st.session_state["power_rank_anchor_date"] = selected_date.isoformat()
    power_trio.save_ranked_cache(ranked, by_id, day=selected_date)
    st.session_state["sheet_tasks"] = [by_id[k] for k in ranked if k in by_id]


def render_dashboard_date_nav() -> date:
    """Minimal prev / date / next strip for Forward Recon."""
    if "dashboard_selected_date" not in st.session_state:
        st.session_state["dashboard_selected_date"] = date.today()
    st.markdown('<p class="recon-date-nav-label">Recon date</p>', unsafe_allow_html=True)
    c_prev, c_mid, c_next = st.columns([0.35, 3.3, 0.35])
    with c_prev:
        if st.button("◀", key="recon_nav_prev", help="Previous day"):
            d0 = _session_date("dashboard_selected_date")
            st.session_state["dashboard_selected_date"] = d0 - timedelta(days=1)
            st.rerun()
    with c_mid:
        st.date_input(
            "Selected date",
            key="dashboard_selected_date",
            label_visibility="collapsed",
            help="Drives Vanguard, calendars, Google hours sync, Integrity, and Power Trio ranking context.",
        )
    with c_next:
        if st.button("▶", key="recon_nav_next", help="Next day"):
            d0 = _session_date("dashboard_selected_date")
            st.session_state["dashboard_selected_date"] = d0 + timedelta(days=1)
            st.rerun()
    if add_keyboard_shortcuts:
        try:
            add_keyboard_shortcuts(
                {
                    "recon_nav_prev": "arrowleft",
                    "recon_nav_next": "arrowright",
                }
            )
        except Exception:
            pass
    st.caption("_Temporal: **←** / **→** refresh recon state for the selected date (same as ◀ ▶)._")
    return _session_date("dashboard_selected_date")


def main() -> None:
    st.set_page_config(
        page_title="Titan Cockpit V4 — Command Center",
        page_icon="◆",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    if "dashboard_selected_date" not in st.session_state:
        st.session_state["dashboard_selected_date"] = date.today()
    if "tactical_compression_streak" not in st.session_state:
        st.session_state.tactical_compression_streak = 0
    inject_theme_css()
    inject_tactical_dim_css()
    load_ragstone_env_files()
    _ensure_sidebar_text_defaults()
    _maybe_run_titan_janitor()

    st.markdown(
        """
        <div class="mntn-hero">
            <header class="mntn-nav">
                <span class="mntn-logo">TITAN COCKPIT</span>
                <span class="mntn-nav-links">Monolith V4 · Hardened</span>
                <span class="mntn-nav-account">Industrial Amber</span>
            </header>
            <div class="mntn-hero__side mntn-hero__side--left">Execute</div>
            <div class="mntn-hero__side mntn-hero__side--right">Hold<span class="mntn-dots">· · ·</span></div>
            <div class="mntn-hero__content">
                <p class="mntn-hero__tag"><span class="mntn-hero__tagline"></span>Execution over information</p>
                <h1 class="mntn-hero__headline">No clutter. No flinching.</h1>
                <p class="mntn-hero__hint">Obsidian baseline · Integrity → Trio → Janitor</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(
        "Sidebar: parameters, **Gemini**, **Todoist**, weekly calendar uploads, Apple/ICS, Google Calendar. "
        "**Recon date** drives runway math and Power Trio context."
    )

    selected_date = render_dashboard_date_nav()

    with st.sidebar:
        render_purpose_pillar_sidebar()
        st.divider()
        st.subheader("Parameters")
        _init_work_hours_ampm_state()
        st.caption("Work day start (12-hour)")
        rs = st.columns(3)
        with rs[0]:
            st.selectbox("Hour", list(range(1, 13)), key="param_ws_h12")
        with rs[1]:
            st.selectbox(
                "Minute",
                list(range(0, 60)),
                key="param_ws_min",
                format_func=lambda m: f"{int(m):02d}",
            )
        with rs[2]:
            st.selectbox("AM / PM", ["AM", "PM"], key="param_ws_ap")
        st.caption("Work day end (12-hour)")
        re = st.columns(3)
        with re[0]:
            st.selectbox("Hour", list(range(1, 13)), key="param_we_h12")
        with re[1]:
            st.selectbox(
                "Minute",
                list(range(0, 60)),
                key="param_we_min",
                format_func=lambda m: f"{int(m):02d}",
            )
        with re[2]:
            st.selectbox("AM / PM", ["AM", "PM"], key="param_we_ap")
        work_start = _time_from_ampm(
            st.session_state.param_ws_h12,
            st.session_state.param_ws_min,
            st.session_state.param_ws_ap,
        )
        work_end = _time_from_ampm(
            st.session_state.param_we_h12,
            st.session_state.param_we_min,
            st.session_state.param_we_ap,
        )
        arch_warn = st.slider("Architecture floor % (warn below)", 5, 50, 20)
        st.divider()
        st.caption("**Gemini**")
        gemini_pw = st.text_input(
            "Paste API key",
            type="password",
            key="user_gemini_api_key",
            label_visibility="visible",
            help="After pasting, click **Apply key** (password fields often clear on rerun until you do).",
        )
        bcol1, bcol2 = st.columns(2)
        with bcol1:
            if st.button("Apply key", help="Stores key for this browser session"):
                if gemini_pw and gemini_pw.strip():
                    st.session_state["_gemini_applied"] = gemini_pw.strip()
                    st.success("Key saved for this session.")
                else:
                    st.warning("Paste a key first, then Apply.")
        with bcol2:
            if st.button("Clear key"):
                st.session_state.pop("_gemini_applied", None)
                st.session_state.pop("user_gemini_api_key", None)
        if gemini_api_key():
            st.success("Gemini ready.")
        else:
            home_env = Path.home() / ".ragstone" / "command_center.env"
            st.caption(
                f"No key detected. **(1)** Paste above → **Apply key**. **(2)** Or set "
                f"`GEMINI_API_KEY` inside `{home_env}` (non-empty between quotes) and refresh. "
                f"**(3)** Or edit `.streamlit/secrets.toml` in this project."
            )

        st.divider()
        render_todoist_sidebar_controls()
        render_work_calendar_sidebar_uploader()
        render_apple_calendar_sidebar_controls()
        render_google_calendar_sidebar_controls()

    ws = datetime.combine(selected_date, work_start)
    we = datetime.combine(selected_date, work_end)
    if we <= ws:
        we = we + timedelta(days=1)
    total_work_hours = (we - ws).total_seconds() / 3600.0

    for _vk, _vd in (
        ("vanguard_executed_deep", 0),
        ("vanguard_executed_mixed", 0),
        ("vanguard_executed_shallow", 0),
    ):
        if _vk not in st.session_state:
            st.session_state[_vk] = _vd

    # --- 1. Protocol (always wall-clock today for logging) ---
    st.markdown("## 5:00 AM — Posture & Neck Protocol")
    st.caption("Non-negotiable. Identity integrity before inbox.")
    if selected_date != date.today():
        st.caption(
            "_Recon date is **not** today — protocol checkboxes and logs still apply to **today’s** calendar._"
        )

    _ensure_protocol_session_for_today()
    today_proto = date.today()
    today_proto_s = today_proto.isoformat()

    cols = st.columns(len(PROTOCOL_ITEMS))
    for i, item in enumerate(PROTOCOL_ITEMS):
        with cols[i]:
            checked = st.checkbox(
                item["label"],
                value=st.session_state.protocol_state.get(item["id"], False),
                key=f"proto_{item['id']}",
            )
            st.session_state.protocol_state[item["id"]] = checked

    if st.button("Log today's protocol"):
        snap = _normalize_protocol_day(st.session_state.protocol_state)
        hist = dict(st.session_state.protocol_history)
        hist[today_proto_s] = snap
        _save_protocol_bundle(hist, dict(st.session_state.get("protocol_neck_cm") or {}))
        st.session_state.protocol_history = hist
        st.success("Today's protocol logged. It appears in the week view below.")
        st.rerun()

    n_neck, n_neck_btn = st.columns([3, 1])
    with n_neck:
        st.number_input(
            "Log neck circumference (cm) — optional, local JSON only",
            min_value=0.0,
            max_value=80.0,
            step=0.1,
            key="protocol_neck_input_cm",
            help="Saved to posture_protocol_state.json under neck_cm (v2). Not sent anywhere.",
        )
    with n_neck_btn:
        st.write("")
        st.write("")
        if st.button("Save neck log", key="protocol_neck_save_btn"):
            v = float(st.session_state.get("protocol_neck_input_cm") or 0.0)
            if v <= 0:
                st.warning("Enter a value greater than 0.")
            else:
                nc = dict(st.session_state.get("protocol_neck_cm") or {})
                nc[today_proto_s] = v
                st.session_state.protocol_neck_cm = nc
                _save_protocol_bundle(dict(st.session_state.protocol_history), nc)
                st.success(f"Saved **{v:.1f}** cm for {today_proto_s}.")
                st.rerun()

    st.caption("Check off what you completed, then **Log today's protocol**. Partial days are allowed.")

    if not all(st.session_state.protocol_state.get(x["id"], False) for x in PROTOCOL_ITEMS):
        st.markdown(
            '<div class="ragstone-warning"><strong>Standing order:</strong> Complete the protocol before '
            "Morning Ops (08:00). No shortcuts.</div>",
            unsafe_allow_html=True,
        )

    render_protocol_week_summary(today_proto)

    st.divider()

    # --- 2. Vanguard — daily view (Focus + calendars + architect ratio) ---
    st.markdown("## Vanguard — daily view")
    st.caption(
        "**Focus Score** updates when Power Trio tasks are **Executed** "
        "(Combat = deep, Momentum = mixed, Admin = shallow). "
        "Upload a **weekly** work calendar in the **sidebar**; Gemini estimates hours **per day**; "
        "**Recon date** drives work slices, Google hours sync, and ranking context. "
        "Personal schedule from **Apple / ICS** when configured."
    )

    _vd = int(st.session_state.get("vanguard_executed_deep") or 0)
    _vm = int(st.session_state.get("vanguard_executed_mixed") or 0)
    _vs = int(st.session_state.get("vanguard_executed_shallow") or 0)
    _fpct = focus_metrics.focus_score_percent(_vd, _vm, _vs)
    _focus_danger = _fpct < focus_metrics.FOCUS_DANGER_THRESHOLD and (_vd + _vm + _vs) > 0
    _fcls = "focus-score-metric focus-score--danger" if _focus_danger else "focus-score-metric"
    st.markdown('<p class="focus-score-caption">Focus score (session executions)</p>', unsafe_allow_html=True)
    st.markdown(f'<p class="{_fcls}">{_fpct:.0f}%</p>', unsafe_allow_html=True)
    st.caption(f"Combat / Momentum / Admin counts: **{_vd}** deep · **{_vm}** mixed · **{_vs}** shallow.")

    if "meeting_hours_work" not in st.session_state:
        st.session_state.meeting_hours_work = 0.0
    if "meeting_hours_personal" not in st.session_state:
        st.session_state.meeting_hours_personal = 0.0
    if "work_calendar_hours_by_day" not in st.session_state:
        st.session_state.work_calendar_hours_by_day = {}
    if st.session_state.get("_meeting_hours_legacy_migrated") is None:
        if "meeting_hours_input" in st.session_state:
            legacy = float(st.session_state.get("meeting_hours_input") or 0)
            if legacy > 0 and float(st.session_state.get("meeting_hours_work") or 0) == 0:
                st.session_state.meeting_hours_work = legacy
            st.session_state.pop("meeting_hours_input", None)
        st.session_state["_meeting_hours_legacy_migrated"] = True

    ensure_personal_calendar_day_view(selected_date)

    svc_cal = calendar_service_from_token()
    cal_id_gc = str(st.session_state.get("sidebar_cal_id") or "primary").strip() or "primary"
    if svc_cal:
        gh_applied = str(st.session_state.get("google_hours_applied_for") or "")
        if gh_applied != selected_date.isoformat():
            try:
                st.session_state.meeting_hours_work = float(
                    sum_event_hours_for_day(svc_cal, selected_date, cal_id_gc)
                )
            except Exception:
                pass
            st.session_state["google_hours_applied_for"] = selected_date.isoformat()

    _maybe_rerank_power_trio_for_date(selected_date)

    _hmap = dict(st.session_state.get("work_calendar_hours_by_day") or {})
    _wss = str(st.session_state.get("work_calendar_week_start") or "").strip()
    if _hmap and _wss:
        try:
            _wmon = date.fromisoformat(_wss[:10])
        except ValueError:
            _wmon = None
        if _wmon is not None and week_start_monday(selected_date) == _wmon:
            _td = selected_date.isoformat()
            if _td in _hmap:
                _applied_for = str(st.session_state.get("_week_hours_applied_for") or "")
                if _applied_for != _td:
                    st.session_state.meeting_hours_work = float(_hmap[_td])
                    st.session_state._week_hours_applied_for = _td

    _ensure_work_cal_week_monday_state()
    week_anchor: date = st.session_state.work_cal_week_monday
    if isinstance(week_anchor, datetime):
        week_anchor = week_anchor.date()
    week_start = week_start_monday(week_anchor)

    b1, b2 = st.columns(2)
    with b1:
        if st.button("Estimate **work week** from screenshots (Gemini)"):
            imgs = list(st.session_state.get("calendar_image_bytes") or [])
            if not imgs:
                st.warning("Upload work calendar screenshots in the **sidebar** first.")
            elif not configure_gemini():
                st.warning(
                    "Add your Gemini key in the **sidebar** (password field) or uncomment it in "
                    "`~/.ragstone/command_center.env`, then try again."
                )
            elif not Image:
                st.warning("Install Pillow: pip install pillow")
            else:
                with st.spinner("Reading work week…"):
                    by_day, note = gemini_analyze_work_calendar_week(imgs, week_start)
                    st.session_state.work_calendar_hours_by_day = by_day
                    st.session_state.work_calendar_week_start = week_start.isoformat()
                    st.session_state.work_calendar_week_note = note
                    st.session_state.work_calendar_week_uploaded_at = datetime.now().isoformat()
                    recon_s = selected_date.isoformat()
                    st.session_state.meeting_hours_work = float(by_day.get(recon_s, 0.0))
                    st.session_state._week_hours_applied_for = recon_s
                    st.session_state["calendar_ai_note"] = note
                st.success(
                    f"Week **{week_start.isoformat()}** estimated. "
                    f"Recon day (**{recon_s}**) work blocked: **{st.session_state.meeting_hours_work:.2f}** h. _{note}_"
                )
    with b2:
        st.caption("Or set work and personal hours manually below. Legacy single-day estimate in expander.")

    with st.expander("Legacy: single-day screenshot estimate"):
        st.caption("If you only have a one-day shot, use this (does not fill the weekly grid).")
        if st.button("Estimate **one day** from screenshots (Gemini)", key="main_legacy_day_est"):
            imgs = list(st.session_state.get("calendar_image_bytes") or [])
            if not imgs:
                st.warning("Upload screenshots in the sidebar first.")
            elif not configure_gemini() or not Image:
                st.warning("Need Gemini key and Pillow.")
            else:
                with st.spinner("Reading one day…"):
                    h, note = gemini_estimate_meeting_hours(imgs)
                    st.session_state.meeting_hours_work = float(h)
                    st.session_state["calendar_ai_note"] = note
                st.success(f"Work blocked (single day): **{h:.2f}** h. _{note}_")

    wc, pc = st.columns(2)
    with wc:
        st.number_input(
            "Work — meeting / fixed-block hours (recon day)",
            min_value=0.0,
            max_value=24.0,
            step=0.25,
            key="meeting_hours_work",
            help="From screenshots, Google Calendar pull, or manual entry.",
        )
        try:
            work_day_card = st.container(border=True)
        except TypeError:  # pragma: no cover — older Streamlit
            work_day_card = st.container()
        with work_day_card:
            st.markdown("**Work calendar — week view**")
            st.caption("Screenshots from the sidebar (weekly upload; re-upload there to replace).")
            ib_work = st.session_state.get("calendar_image_bytes") or []
            if ib_work:
                wcols = st.columns(min(3, len(ib_work)))
                for i, b in enumerate(ib_work):
                    with wcols[i % len(wcols)]:
                        st.image(b, width="stretch")
            else:
                st.markdown("_No screenshots yet — use **Work calendar (upload)** in the sidebar._")

    with pc:
        st.number_input(
            "Personal — meeting / fixed-block hours (recon day)",
            min_value=0.0,
            max_value=24.0,
            step=0.25,
            key="meeting_hours_personal",
            help="From Apple / ICS pull in the sidebar or manual entry.",
        )
        try:
            personal_day_card = st.container(border=True)
        except TypeError:  # pragma: no cover — older Streamlit
            personal_day_card = st.container()
        with personal_day_card:
            st.markdown("**Personal — recon day**")
            hdr_l, hdr_r = st.columns([3, 1])
            with hdr_l:
                st.caption(selected_date.strftime("%A · %b %d, %Y"))
            with hdr_r:
                if _personal_calendar_configured() and st.button(
                    "Refresh",
                    key="main_refresh_personal_day_view",
                    help="Reload recon day’s events from Apple/ICS",
                ):
                    st.session_state["_personal_cal_force_refresh"] = True
                    st.rerun()
            perr = str(st.session_state.get("personal_calendar_events_load_error") or "")
            pev = list(st.session_state.get("personal_calendar_day_events") or [])
            if not _personal_calendar_configured():
                st.markdown(
                    "_Set **APPLE_CALENDAR_ICS_URL** or **ICLOUD_APPLE_ID** + **ICLOUD_APP_PASSWORD** in secrets "
                    "to load your personal day view._"
                )
            elif perr:
                st.warning(perr)
            elif not pev:
                st.markdown(
                    "_No events in this day’s window, or data not loaded yet — use **Pull personal hours** in the sidebar._"
                )
            else:
                for row in pev:
                    st.markdown(f"- {_format_personal_event_line(row)}")

    meeting_hours_work = float(st.session_state.get("meeting_hours_work") or 0)
    meeting_hours_personal = float(st.session_state.get("meeting_hours_personal") or 0)
    meeting_hours = min(meeting_hours_work + meeting_hours_personal, 24.0)
    _available_sel = max(total_work_hours - meeting_hours, 0.0)
    arch_pct = (_available_sel / total_work_hours * 100.0) if total_work_hours > 0 else 0.0
    eff_danger = arch_pct < arch_warn and meeting_hours > 0
    eff_cls = "efficiency-hero efficiency-hero--danger" if eff_danger else "efficiency-hero"
    st.markdown(
        f'<p class="efficiency-hero-label">Efficiency (recon day)</p>'
        f'<p class="{eff_cls}">{arch_pct:.1f}%</p>'
        f'<p class="efficiency-hero-sub">Work window {total_work_hours:.2f} h · '
        f"meetings {meeting_hours:.2f} h (work {meeting_hours_work:.2f} · personal {meeting_hours_personal:.2f})</p>",
        unsafe_allow_html=True,
    )
    if meeting_hours <= 0:
        st.info("Set work and/or personal hours for a real efficiency read.")
    if meeting_hours > 0 and eff_danger:
        st.markdown(
            f'<div class="ragstone-danger"><strong>Warning:</strong> Build time for Ragstone is below '
            f"{arch_warn}% (~{arch_pct:.1f}%) on this model. Defend the calendar.</div>",
            unsafe_allow_html=True,
        )

    wh_by = dict(st.session_state.get("work_calendar_hours_by_day") or {})
    ws_iso = str(st.session_state.get("work_calendar_week_start") or "").strip()
    if wh_by and ws_iso:
        try:
            ws_d = date.fromisoformat(ws_iso[:10])
        except ValueError:
            ws_d = selected_date
        st.markdown("**Work week — Gemini (hours / day)**")
        st.caption(
            f"Week starting **{ws_d.isoformat()}** (Mon–Sun). "
            f"**Recon** **{selected_date.isoformat()}** drives the work-hour field above when this week matches."
        )
        personal_h_grid = float(st.session_state.get("meeting_hours_personal") or 0.0)
        rows: List[Dict[str, Any]] = []
        for i in range(7):
            d = ws_d + timedelta(days=i)
            ds = d.isoformat()
            h = float(wh_by.get(ds, 0.0))
            ph = personal_h_grid if d == selected_date else 0.0
            block = min(h + ph, 24.0)
            eff = (
                max(total_work_hours - block, 0.0) / total_work_hours * 100.0
                if total_work_hours > 0
                else 0.0
            )
            rows.append(
                {
                    "Day": d.strftime("%a"),
                    "Date": ds,
                    "Work blocked (h)": round(h, 2),
                    "Efficiency %": round(eff, 1),
                }
            )
        if pd is not None:
            try:
                dfw = pd.DataFrame(rows)
                styler = dfw.style.apply(
                    lambda row: [
                        (
                            "background: rgba(247,212,145,0.18); font-weight: 700; "
                            "box-shadow: inset 0 0 0 2px rgba(247,212,145,0.55);"
                            if str(row["Date"]) == selected_date.isoformat()
                            else ""
                        )
                        for _ in row.index
                    ],
                    axis=1,
                ).background_gradient(
                    subset=["Efficiency %"],
                    cmap="bone",
                    vmin=0,
                    vmax=100,
                )
                st.markdown(styler.hide(axis="index").to_html(), unsafe_allow_html=True)
            except Exception:
                st.dataframe(dfw, hide_index=True, width="stretch")
        else:
            st.table(rows)

    if st.session_state.get("calendar_ai_note"):
        st.caption(f"_Last Gemini note (work screenshots):_ {st.session_state['calendar_ai_note']}")

    st.divider()

    # --- 2b. Integrity Runway (Google → personal anchor) ---
    render_integrity_runway_section(selected_date)

    render_tomorrow_runway_panel()

    st.divider()

    # --- 3. Power Trio (Todoist) ---
    render_power_trio_section(selected_date)

    tasks: List[Dict[str, Any]] = _architect_task_rows()

    st.divider()

    # --- 4. Architect reasoning ---
    st.markdown("## Architect reasoning (Gemini)")
    if configure_gemini():
        task_snip = ", ".join(str(t.get("content", "")) for t in tasks[:12]) if tasks else ""
        _wh = dict(st.session_state.get("work_calendar_hours_by_day") or {})
        _ws = str(st.session_state.get("work_calendar_week_start") or "").strip()
        week_summary = ""
        if _wh and _ws:
            try:
                week_summary = week_load_summary_line(_wh, date.fromisoformat(_ws[:10]))
            except ValueError:
                week_summary = ""
        if st.button("Generate briefing"):
            with st.spinner("Reasoning…"):
                try:
                    brief = gemini_architect_brief(
                        task_snip,
                        meeting_hours_work,
                        meeting_hours_personal,
                        meeting_hours,
                        total_work_hours,
                        arch_pct,
                        week_load_summary=week_summary,
                    )
                    st.markdown(brief)
                except Exception as e:
                    st.error(str(e))
    else:
        st.caption("Set `GEMINI_API_KEY` in your env file or `.streamlit/secrets.toml` (see sidebar).")


if __name__ == "__main__":
    main()
