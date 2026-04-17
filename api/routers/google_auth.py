"""Google OAuth for Calendar (writes token.json; same scopes as Streamlit)."""

from __future__ import annotations

import time
from typing import Optional
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from integrations.env_loader import env_str
from integrations.paths import CALENDAR_SCOPES, CREDENTIALS_PATH, TOKEN_PATH

router = APIRouter(prefix="/auth/google", tags=["auth"])

# CSRF + PKCE: state and code_verifier from the first /start leg must match /callback
# (google_auth_oauthlib generates a code_verifier for PKCE; a new Flow on callback has no memory of it).
_oauth_sessions: dict[str, tuple[float, str]] = {}  # state -> (expiry_monotonic, code_verifier)
_STATE_TTL_SEC = 600.0


def _redirect_uri() -> str:
    return env_str(
        "GOOGLE_OAUTH_REDIRECT_URI",
        "http://127.0.0.1:8000/api/auth/google/callback",
    )


def _frontend_success_url() -> str:
    base = env_str("COCKPIT_FRONTEND_URL", "http://localhost:5173").rstrip("/")
    return f"{base}/?calendar=connected"


def _frontend_error_url(msg: str) -> str:
    base = env_str("COCKPIT_FRONTEND_URL", "http://localhost:5173").rstrip("/")
    q = urlencode({"calendar_error": msg[:500]})
    return f"{base}/?{q}"


def _purge_expired_oauth() -> None:
    now = time.monotonic()
    dead = [s for s, (exp, _) in _oauth_sessions.items() if exp < now]
    for s in dead:
        _oauth_sessions.pop(s, None)


def _register_oauth_session(state: str, code_verifier: str) -> None:
    _purge_expired_oauth()
    _oauth_sessions[state] = (time.monotonic() + _STATE_TTL_SEC, code_verifier)


def _take_oauth_session(state: str) -> tuple[bool, str]:
    """
    Pop a pending OAuth session. Returns (ok, code_verifier).
    If ok is False, the state was missing or expired.
    """
    _purge_expired_oauth()
    item = _oauth_sessions.pop(state, None)
    if not item:
        return (False, "")
    exp, code_verifier = item
    if time.monotonic() > exp:
        return (False, "")
    return (True, code_verifier)


class GoogleAuthStatus(BaseModel):
    connected: bool
    credentials_file_present: bool
    message: str = ""


@router.get("/status", response_model=GoogleAuthStatus)
def google_auth_status() -> GoogleAuthStatus:
    if not CREDENTIALS_PATH.is_file():
        return GoogleAuthStatus(
            connected=False,
            credentials_file_present=False,
            message=f"Missing OAuth client file: {CREDENTIALS_PATH.name}",
        )
    if not TOKEN_PATH.is_file():
        return GoogleAuthStatus(
            connected=False,
            credentials_file_present=True,
            message="Not authorized yet — use Connect Google Calendar.",
        )
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials

        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), CALENDAR_SCOPES)
        if creds.expired and creds.refresh_token and Request:
            creds.refresh(Request())
            TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
        if creds.valid:
            return GoogleAuthStatus(connected=True, credentials_file_present=True, message="")
        return GoogleAuthStatus(
            connected=False,
            credentials_file_present=True,
            message="Stored token invalid — reconnect.",
        )
    except OSError as e:
        return GoogleAuthStatus(
            connected=False,
            credentials_file_present=True,
            message=str(e),
        )


@router.get("/start")
def google_oauth_start() -> RedirectResponse:
    if not CREDENTIALS_PATH.is_file():
        raise HTTPException(
            status_code=503,
            detail=f"Missing {CREDENTIALS_PATH.name}. Add a Web application OAuth client from Google Cloud Console.",
        )
    try:
        from google_auth_oauthlib.flow import Flow
    except ImportError as e:
        raise HTTPException(status_code=503, detail="Install google-auth-oauthlib.") from e

    redirect_uri = _redirect_uri()
    try:
        flow = Flow.from_client_secrets_file(
            str(CREDENTIALS_PATH),
            scopes=CALENDAR_SCOPES,
            redirect_uri=redirect_uri,
        )
    except (ValueError, KeyError) as e:
        raise HTTPException(
            status_code=503,
            detail=(
                f"Could not load OAuth client config: {e}. "
                "Use a 'Web application' client with redirect URI matching GOOGLE_OAUTH_REDIRECT_URI."
            ),
        ) from e

    authorization_url, state = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        include_granted_scopes="true",
    )
    # PKCE: must be replayed on token exchange (see /callback).
    cv = getattr(flow, "code_verifier", None) or ""
    _register_oauth_session(state, cv)
    return RedirectResponse(url=authorization_url, status_code=302)


@router.get("/callback")
def google_oauth_callback(
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
) -> RedirectResponse:
    if error:
        return RedirectResponse(url=_frontend_error_url(error), status_code=302)
    if not code or not state:
        return RedirectResponse(url=_frontend_error_url("missing_code_or_state"), status_code=302)
    ok, code_verifier = _take_oauth_session(state)
    if not ok:
        return RedirectResponse(url=_frontend_error_url("invalid_or_expired_state"), status_code=302)
    if not CREDENTIALS_PATH.is_file():
        return RedirectResponse(url=_frontend_error_url("missing_credentials_json"), status_code=302)

    try:
        from google_auth_oauthlib.flow import Flow
    except ImportError:
        return RedirectResponse(url=_frontend_error_url("missing_google_auth_oauthlib"), status_code=302)

    redirect_uri = _redirect_uri()
    try:
        flow = Flow.from_client_secrets_file(
            str(CREDENTIALS_PATH),
            scopes=CALENDAR_SCOPES,
            redirect_uri=redirect_uri,
        )
        if code_verifier:
            flow.code_verifier = code_verifier
        flow.fetch_token(code=code)
    except Exception as e:  # noqa: BLE001
        return RedirectResponse(url=_frontend_error_url(str(e)), status_code=302)

    creds = flow.credentials
    try:
        TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
    except OSError as e:
        return RedirectResponse(url=_frontend_error_url(f"write_token:{e}"), status_code=302)

    return RedirectResponse(url=_frontend_success_url(), status_code=302)
