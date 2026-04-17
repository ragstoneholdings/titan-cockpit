"""Minimal APNs alert sender (HTTP/2, ES256 JWT from .p8). Env: APNS_KEY_ID, APNS_TEAM_ID, APNS_BUNDLE_ID, APNS_KEY_PATH."""

from __future__ import annotations

import logging
import os
import time
from typing import List, Optional, Tuple

_log = logging.getLogger(__name__)

try:
    import jwt  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover
    jwt = None  # type: ignore[assignment]


def _config() -> tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    kid = (os.environ.get("APNS_KEY_ID") or "").strip()
    team = (os.environ.get("APNS_TEAM_ID") or "").strip()
    topic = (os.environ.get("APNS_BUNDLE_ID") or "").strip()
    path = (os.environ.get("APNS_KEY_PATH") or "").strip()
    return (kid or None, team or None, topic or None, path or None)


def _jwt_bearer() -> Optional[str]:
    if jwt is None:
        return None
    kid, team, _, key_path = _config()
    if not kid or not team or not key_path:
        return None
    p = os.path.expanduser(key_path)
    try:
        raw = open(p, encoding="utf-8").read()
    except OSError as e:
        _log.warning("apns key read failed: %s", e)
        return None
    now = int(time.time())
    try:
        token = jwt.encode(
            {"iss": team, "iat": now},
            raw,
            algorithm="ES256",
            headers={"alg": "ES256", "kid": kid},
        )
    except Exception as e:  # pragma: no cover - signing issues
        _log.warning("apns jwt encode failed: %s", e)
        return None
    if isinstance(token, bytes):
        return token.decode("utf-8")
    return str(token)


def _base_url() -> str:
    if (os.environ.get("APNS_USE_SANDBOX") or "").strip().lower() in ("1", "true", "yes"):
        return "https://api.sandbox.push.apple.com"
    return "https://api.push.apple.com"


def send_apns_alert(*, device_token_hex: str, title: str, body: str, sound: str = "default") -> Tuple[bool, str]:
    """Return (success, message)."""

    _, _, topic, _ = _config()
    bearer = _jwt_bearer()
    if not topic or not bearer:
        return False, "apns_not_configured"
    tok = (device_token_hex or "").strip().replace(" ", "")
    if not tok:
        return False, "empty_device_token"
    try:
        import httpx
    except ImportError:  # pragma: no cover
        return False, "httpx_missing"

    url = f"{_base_url().rstrip('/')}/3/device/{tok}"
    payload = {"aps": {"alert": {"title": title, "body": body}, "sound": sound}}
    headers = {
        "authorization": f"bearer {bearer}",
        "apns-topic": topic,
        "apns-push-type": "alert",
        "apns-priority": "10",
    }
    try:
        with httpx.Client(http2=True, timeout=20.0) as client:
            r = client.post(url, json=payload, headers=headers)
    except Exception as e:
        return False, str(e)[:500]
    if 200 <= r.status_code < 300:
        return True, "ok"
    return False, f"apns_http_{r.status_code}: {r.text[:300]}"


def broadcast_alert(*, title: str, body: str, tokens: List[str]) -> dict:
    """Send to each device token; returns aggregate counts."""

    sent = 0
    errors: List[str] = []
    for t in tokens:
        ok, msg = send_apns_alert(device_token_hex=t, title=title, body=body)
        if ok:
            sent += 1
        else:
            errors.append(f"{t[:12]}…: {msg}")
    return {"ok": sent > 0, "sent": sent, "attempted": len(tokens), "errors": errors[:10]}
