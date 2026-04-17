"""Optional device token registration and APNs helpers (Phases 5–8)."""

from __future__ import annotations

import os
from datetime import date
from typing import Any, Dict, List, Optional

import device_push_store
from api.services.apns_send import broadcast_alert, send_apns_alert
from api.services.cockpit_assemble import assemble_cockpit_dict
from fastapi import APIRouter, Body, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter(prefix="/device", tags=["device"])


class DeviceRegisterBody(BaseModel):
    device_token_hex: str = Field(..., min_length=8, description="APNs device token (hex string)")
    platform: str = "ios"
    label: str = ""


class PushTestBody(BaseModel):
    title: str = Field(default="Titan Cockpit", max_length=120)
    body: str = Field(default="Test push from server.", max_length=500)


def _expected_cockpit_key() -> str:
    return (os.environ.get("COCKPIT_API_KEY") or "").strip()


def _require_cockpit_key_for_admin() -> None:
    """Reject admin push routes when ``COCKPIT_API_KEY`` is unset (avoid accidental open relays)."""

    if not _expected_cockpit_key():
        raise HTTPException(
            status_code=503,
            detail={"error": {"code": "admin_disabled", "message": "Set COCKPIT_API_KEY to use push endpoints"}},
        )


@router.post("/register")
def post_device_register(body: DeviceRegisterBody) -> Dict[str, Any]:
    return device_push_store.register_token(
        device_token_hex=body.device_token_hex,
        platform=body.platform,
        label=body.label,
    )


@router.get("/tokens")
def get_device_tokens(limit: Optional[int] = 20) -> Dict[str, Any]:
    """Listing requires auth when ``COCKPIT_API_KEY`` is set (middleware). Optional: ``COCKPIT_BLOCK_DEVICE_TOKENS_WITHOUT_KEY=1`` forbids listing if the key is unset."""

    if (os.environ.get("COCKPIT_BLOCK_DEVICE_TOKENS_WITHOUT_KEY") or "").strip().lower() in ("1", "true", "yes"):
        if not _expected_cockpit_key():
            raise HTTPException(
                status_code=403,
                detail={"error": {"code": "forbidden", "message": "Device token listing disabled without COCKPIT_API_KEY"}},
            )
    n = max(1, min(100, int(limit or 20)))
    return {"ok": True, "tokens": device_push_store.list_tokens(limit=n)}


@router.post("/push/test")
def post_push_test(body: Optional[PushTestBody] = Body(default=None)) -> Dict[str, Any]:
    """Send a visible push to all stored device tokens (requires ``COCKPIT_API_KEY``)."""

    _require_cockpit_key_for_admin()
    b = body or PushTestBody()
    rows = device_push_store.list_tokens(limit=100)
    tokens: List[str] = [str(r.get("device_token_hex") or "") for r in rows if r.get("device_token_hex")]
    tokens = [t for t in tokens if t.strip()]
    summary = broadcast_alert(title=b.title, body=b.body, tokens=tokens)
    return {"ok": bool(summary.get("ok")), **summary}


@router.post("/push/integrity-sentry")
def post_push_integrity_sentry(
    day: Optional[date] = Query(None, description="Recon date (default today)"),
) -> Dict[str, Any]:
    """
    Server rule (Phase 8): if cockpit integrity sentry is CRITICAL, send one alert to all devices.
    Requires ``COCKPIT_API_KEY`` and APNs env (see ``api/services/apns_send.py``).
    """

    _require_cockpit_key_for_admin()
    raw = assemble_cockpit_dict(day)
    state = str(raw.get("integrity_sentry_state") or "NOMINAL").upper()
    if state != "CRITICAL":
        return {
            "ok": True,
            "skipped": True,
            "integrity_sentry_state": state,
            "reason": "not_critical",
        }
    rows = device_push_store.list_tokens(limit=100)
    tokens = [str(r.get("device_token_hex") or "") for r in rows if r.get("device_token_hex")]
    tokens = [t for t in tokens if t.strip()]
    summary = broadcast_alert(
        title="Integrity sentry CRITICAL",
        body="Open Cockpit to resolve.",
        tokens=tokens,
    )
    return {"ok": True, "integrity_sentry_state": state, **summary}


@router.post("/push/alert-once")
def post_push_alert_once(body: PushTestBody) -> Dict[str, Any]:
    """Send to the most recently registered token only (minimal blast radius)."""

    _require_cockpit_key_for_admin()
    rows = device_push_store.list_tokens(limit=1)
    if not rows:
        return {"ok": False, "error": "no_device_tokens"}
    tok = str(rows[-1].get("device_token_hex") or "")
    ok, msg = send_apns_alert(device_token_hex=tok, title=body.title, body=body.body)
    return {"ok": ok, "message": msg, "token_prefix": tok[:16]}
