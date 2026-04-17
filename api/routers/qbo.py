"""QuickBooks Online — server-first status (OAuth stays on FastAPI when implemented)."""

from __future__ import annotations

from api.services import qbo_scaffold
from fastapi import APIRouter

router = APIRouter(prefix="/qbo", tags=["qbo"])


@router.get("/status")
def get_qbo_status() -> dict:
    """Expose scaffold state for iOS / tools; tokens and realm ID belong on the server."""
    return qbo_scaffold.qbo_placeholder()
