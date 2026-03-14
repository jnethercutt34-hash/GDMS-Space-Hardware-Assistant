"""Upload size limit middleware.

Rejects requests with Content-Length > MAX_UPLOAD_BYTES (default 50MB).
Returns 413 Payload Too Large if exceeded.

Note: This checks the Content-Length header, which can be spoofed.
For streaming uploads without Content-Length, the actual body size
is checked by FastAPI/Starlette's default body limit (if configured).
"""
import logging
import os

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

_DEFAULT_MAX_BYTES = 50 * 1024 * 1024  # 50 MB


class UploadLimitMiddleware(BaseHTTPMiddleware):
    """Reject uploads exceeding the configured size limit."""

    def __init__(self, app, max_bytes: int | None = None):
        super().__init__(app)
        self._max_bytes = max_bytes or int(
            os.environ.get("MAX_UPLOAD_BYTES", _DEFAULT_MAX_BYTES)
        )

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self._max_bytes:
            mb = self._max_bytes / (1024 * 1024)
            logger.warning(
                "Rejected upload: %s bytes (limit %s MB) on %s %s",
                content_length, mb, request.method, request.url.path,
            )
            return JSONResponse(
                status_code=413,
                content={
                    "detail": f"Upload too large. Maximum size is {mb:.0f} MB."
                },
            )
        return await call_next(request)
