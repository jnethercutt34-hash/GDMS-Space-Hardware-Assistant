"""Upload size limit middleware (pure ASGI — no BaseHTTPMiddleware).

Rejects requests with Content-Length > MAX_UPLOAD_BYTES (default 50MB).
Returns 413 Payload Too Large if exceeded.
"""
import logging
import os

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)

_DEFAULT_MAX_BYTES = 50 * 1024 * 1024  # 50 MB


class UploadLimitMiddleware:
    """Pure ASGI middleware — reject oversized uploads."""

    def __init__(self, app: ASGIApp, max_bytes: int | None = None):
        self.app = app
        self._max_bytes = max_bytes or int(
            os.environ.get("MAX_UPLOAD_BYTES", _DEFAULT_MAX_BYTES)
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self._max_bytes:
            mb = self._max_bytes / (1024 * 1024)
            logger.warning(
                "Rejected upload: %s bytes (limit %s MB) on %s %s",
                content_length, mb, request.method, request.url.path,
            )
            response = JSONResponse(
                status_code=413,
                content={
                    "detail": f"Upload too large. Maximum size is {mb:.0f} MB."
                },
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)
