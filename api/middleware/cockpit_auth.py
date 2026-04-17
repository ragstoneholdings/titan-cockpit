"""Optional API key gate when ``COCKPIT_API_KEY`` is set (Phase 3 production)."""

from __future__ import annotations

import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


def _expected_key() -> str:
    return (os.environ.get("COCKPIT_API_KEY") or "").strip()


def _extract_key(request: Request) -> str:
    bearer = request.headers.get("authorization") or ""
    if bearer.lower().startswith("bearer "):
        return bearer[7:].strip()
    return (request.headers.get("x-cockpit-key") or "").strip()


class CockpitAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method == "OPTIONS":
            return await call_next(request)
        key = _expected_key()
        if not key:
            return await call_next(request)
        path = request.url.path
        if path == "/api/health" or path.rstrip("/") == "/api/health":
            return await call_next(request)
        if _extract_key(request) == key:
            return await call_next(request)
        return JSONResponse({"detail": "Unauthorized"}, status_code=401)
