"""Project paths shared by API, Streamlit, and integrations."""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def data_root() -> Path:
    """Mutable JSON stores (Zapier trace, device tokens, power trio state, …).

    Set ``RAGSTONE_DATA_ROOT`` on production hosts to mount a persistent volume (e.g. ``/data``)
    while application code stays on the image under ``PROJECT_ROOT``.
    """

    raw = (os.environ.get("RAGSTONE_DATA_ROOT") or "").strip()
    if raw:
        p = Path(raw).expanduser().resolve()
        try:
            p.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        return p
    return PROJECT_ROOT


PROTOCOL_STATE_PATH = PROJECT_ROOT / "posture_protocol_state.json"
TOKEN_PATH = PROJECT_ROOT / "token.json"


def calendar_credentials_path() -> Path:
    p = os.environ.get("GOOGLE_CALENDAR_CREDENTIALS", "").strip()
    if p:
        return Path(p).expanduser()
    return PROJECT_ROOT / "credentials.json"


CREDENTIALS_PATH = calendar_credentials_path()

CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
