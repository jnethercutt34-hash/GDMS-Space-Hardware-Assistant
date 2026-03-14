"""API key authentication middleware (pure ASGI — no BaseHTTPMiddleware).

Validates `Authorization: Bearer <key>` against keys in the API_KEYS env var.
Extracts `X-User` header (trusted, unvalidated) into `request.state.user`.

Bypass paths (no auth required):
  - /health
  - /docs, /redoc, /openapi.json  (Swagger UI)

Environment variables:
  API_KEYS: Comma-separated list of valid API keys.
            If empty or unset, auth is DISABLED (dev mode).

Trust model:
  X-User is honesty-based. The API key authenticates the *client application*,
  not the individual user. In production, the calling app (or gateway) is
  trusted to set X-User correctly. This is documented and intentional —
  upgrading to SSO/LDAP is tracked in the P2 roadmap.
"""
import logging
import os
from typing import Set

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)

# Paths that bypass auth entirely
_PUBLIC_PATHS: Set[str] = {"/health", "/docs", "/redoc", "/openapi.json"}


def _load_api_keys() -> Set[str]:
    """Load valid API keys from environment. Empty set = auth disabled."""
    raw = os.environ.get("API_KEYS", "").strip()
    if not raw:
        return set()
    return {k.strip() for k in raw.split(",") if k.strip()}


class AuthMiddleware:
    """Pure ASGI middleware for API key + X-User authentication."""

    def __init__(self, app: ASGIApp, api_keys: Set[str] | None = None):
        self.app = app
        self._api_keys = api_keys if api_keys is not None else _load_api_keys()
        if not self._api_keys:
            logger.warning(
                "API_KEYS not set — auth middleware is DISABLED (dev mode). "
                "Set API_KEYS in .env to enable."
            )

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        path = request.url.path

        # Always allow public paths
        if path in _PUBLIC_PATHS:
            scope.setdefault("state", {})["user"] = "anonymous"
            await self.app(scope, receive, send)
            return

        # If no keys configured, skip auth (dev mode)
        if not self._api_keys:
            scope.setdefault("state", {})["user"] = request.headers.get("X-User", "dev")
            await self.app(scope, receive, send)
            return

        # Validate Authorization header
        auth_header = request.headers.get("Authorization", "")
        if not auth_header:
            response = JSONResponse(
                status_code=401,
                content={"detail": "Missing Authorization header"},
            )
            await response(scope, receive, send)
            return

        if not auth_header.startswith("Bearer "):
            response = JSONResponse(
                status_code=401,
                content={"detail": "Authorization header must use Bearer scheme"},
            )
            await response(scope, receive, send)
            return

        token = auth_header[7:]
        if token not in self._api_keys:
            response = JSONResponse(
                status_code=403,
                content={"detail": "Invalid API key"},
            )
            await response(scope, receive, send)
            return

        # Extract user identity (honesty-based)
        scope.setdefault("state", {})["user"] = request.headers.get("X-User", "unknown")
        await self.app(scope, receive, send)
