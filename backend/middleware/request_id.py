"""Request ID middleware — generates a UUID per request for log tracing.

Adds `X-Request-ID` to the response headers. If the client sends an
`X-Request-ID` header, it is reused (useful for end-to-end tracing).

The request ID is stored in `request.state.request_id` for use in
application code.
"""
import logging
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Inject a unique request ID into every request/response."""

    async def dispatch(self, request: Request, call_next):
        # Reuse client-provided ID or generate a new one
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id

        # Log after inner middleware has run (so request.state.user is set by auth)
        logger.info(
            "[%s] %s %s → %s (user=%s)",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            getattr(request.state, "user", "?"),
        )

        return response
