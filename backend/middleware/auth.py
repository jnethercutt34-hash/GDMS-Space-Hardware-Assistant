"""API key authentication middleware.

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
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# Paths that bypass auth entirely
_PUBLIC_PATHS: Set[str] = {"/health", "/docs", "/redoc", "/openapi.json"}


def _load_api_keys() -> Set[str]:
    """Load valid API keys from environment. Empty set = auth disabled."""
    raw = os.environ.get("API_KEYS", "").strip()
    if not raw:
        return set()
    return {k.strip() for k in raw.split(",") if k.strip()}


class AuthMiddleware(BaseHTTPMiddleware):
    """Starlette middleware for API key + X-User authentication."""

    def __init__(self, app, api_keys: Set[str] | None = None):
        super().__init__(app)
        self._api_keys = api_keys if api_keys is not None else _load_api_keys()
        if not self._api_keys:
            logger.warning(
                "API_KEYS not set — auth middleware is DISABLED (dev mode). "
                "Set API_KEYS in .env to enable."
            )

    async def dispatch(self, request: Request, call_next):
        # Always allow public paths
        if request.url.path in _PUBLIC_PATHS:
            request.state.user = "anonymous"
            return await call_next(request)

        # If no keys configured, skip auth (dev mode)
        if not self._api_keys:
            request.state.user = request.headers.get("X-User", "dev")
            return await call_next(request)

        # Validate Authorization header
        auth_header = request.headers.get("Authorization", "")
        if not auth_header:
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing Authorization header"},
            )

        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Authorization header must use Bearer scheme"},
            )

        token = auth_header[7:]  # len("Bearer ") == 7
        if token not in self._api_keys:
            return JSONResponse(
                status_code=403,
                content={"detail": "Invalid API key"},
            )

        # Extract user identity (honesty-based)
        request.state.user = request.headers.get("X-User", "unknown")

        return await call_next(request)
