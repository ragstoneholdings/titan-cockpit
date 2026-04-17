"""Request identifier + single access-style log line (request id, method, path, status)."""

from __future__ import annotations

import logging
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_log = logging.getLogger("cockpit.request")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        rid = (request.headers.get("x-request-id") or "").strip() or str(uuid.uuid4())
        request.state.request_id = rid
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        try:
            status = response.status_code
        except Exception:
            status = -1
        path = request.url.path
        if path.startswith("/api/health") or path == "/favicon.ico":
            return response
        _log.info(
            "request id=%s %s %s status=%s",
            rid,
            request.method,
            path,
            status,
        )
        return response
