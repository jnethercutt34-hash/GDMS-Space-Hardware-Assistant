"""Request ID middleware (pure ASGI — no BaseHTTPMiddleware).

Adds `X-Request-ID` to the response headers. If the client sends an
`X-Request-ID` header, it is reused (useful for end-to-end tracing).

The request ID is stored in `request.state.request_id` for use in
application code.
"""
import logging
import uuid

from fastapi import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger(__name__)


class RequestIDMiddleware:
    """Pure ASGI middleware — inject a unique request ID."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        scope.setdefault("state", {})["request_id"] = request_id

        async def send_with_request_id(message: Message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode()))
                message["headers"] = headers

                # Log after response status is known
                status = message.get("status", 0)
                user = scope.get("state", {}).get("user", "?")
                logger.info(
                    "[%s] %s %s → %s (user=%s)",
                    request_id, request.method, request.url.path, status, user,
                )
            await send(message)

        await self.app(scope, receive, send_with_request_id)
