"""Tests for auth, request ID, and upload limit middleware."""
import os
from unittest.mock import patch

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from middleware.auth import AuthMiddleware
from middleware.request_id import RequestIDMiddleware
from middleware.upload_limit import UploadLimitMiddleware


# ===========================================================================
# Helpers — build a minimal FastAPI app with middleware for testing
# ===========================================================================

def _make_app(api_keys=None, max_upload_bytes=None):
    """Create a test app with all three middleware layers."""
    app = FastAPI()

    app.add_middleware(AuthMiddleware, api_keys=api_keys)
    app.add_middleware(RequestIDMiddleware)
    if max_upload_bytes is not None:
        app.add_middleware(UploadLimitMiddleware, max_bytes=max_upload_bytes)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/test")
    def api_test(request: Request):
        return {
            "user": getattr(request.state, "user", None),
            "request_id": getattr(request.state, "request_id", None),
        }

    @app.post("/api/upload")
    async def upload(request: Request):
        body = await request.body()
        return {"size": len(body)}

    return app


# ===========================================================================
# Auth middleware
# ===========================================================================

class TestAuthMiddleware:
    """Test API key + X-User authentication."""

    def test_health_bypasses_auth(self):
        client = TestClient(_make_app(api_keys={"secret123"}))
        r = client.get("/health")
        assert r.status_code == 200

    def test_valid_key_passes(self):
        client = TestClient(_make_app(api_keys={"secret123"}))
        r = client.get("/api/test", headers={"Authorization": "Bearer secret123"})
        assert r.status_code == 200

    def test_invalid_key_returns_403(self):
        client = TestClient(_make_app(api_keys={"secret123"}))
        r = client.get("/api/test", headers={"Authorization": "Bearer wrong"})
        assert r.status_code == 403
        assert "Invalid API key" in r.json()["detail"]

    def test_missing_auth_header_returns_401(self):
        client = TestClient(_make_app(api_keys={"secret123"}))
        r = client.get("/api/test")
        assert r.status_code == 401

    def test_non_bearer_scheme_returns_401(self):
        client = TestClient(_make_app(api_keys={"secret123"}))
        r = client.get("/api/test", headers={"Authorization": "Basic abc"})
        assert r.status_code == 401
        assert "Bearer" in r.json()["detail"]

    def test_x_user_extracted(self):
        client = TestClient(_make_app(api_keys={"secret123"}))
        r = client.get(
            "/api/test",
            headers={"Authorization": "Bearer secret123", "X-User": "alice"},
        )
        assert r.status_code == 200
        assert r.json()["user"] == "alice"

    def test_x_user_defaults_to_unknown(self):
        client = TestClient(_make_app(api_keys={"secret123"}))
        r = client.get("/api/test", headers={"Authorization": "Bearer secret123"})
        assert r.json()["user"] == "unknown"

    def test_dev_mode_no_keys_skips_auth(self):
        """When no API keys configured, auth is disabled (dev mode)."""
        client = TestClient(_make_app(api_keys=set()))
        r = client.get("/api/test")
        assert r.status_code == 200
        assert r.json()["user"] == "dev"

    def test_dev_mode_x_user_still_extracted(self):
        client = TestClient(_make_app(api_keys=set()))
        r = client.get("/api/test", headers={"X-User": "bob"})
        assert r.json()["user"] == "bob"

    def test_multiple_keys(self):
        client = TestClient(_make_app(api_keys={"key1", "key2", "key3"}))
        for key in ["key1", "key2", "key3"]:
            r = client.get("/api/test", headers={"Authorization": f"Bearer {key}"})
            assert r.status_code == 200


# ===========================================================================
# Request ID middleware
# ===========================================================================

class TestRequestIDMiddleware:
    def test_generates_request_id(self):
        client = TestClient(_make_app(api_keys=set()))
        r = client.get("/api/test")
        assert "x-request-id" in r.headers
        assert len(r.headers["x-request-id"]) > 0

    def test_reuses_client_request_id(self):
        client = TestClient(_make_app(api_keys=set()))
        r = client.get("/api/test", headers={"X-Request-ID": "my-trace-123"})
        assert r.headers["x-request-id"] == "my-trace-123"

    def test_request_id_in_state(self):
        client = TestClient(_make_app(api_keys=set()))
        r = client.get("/api/test")
        assert r.json()["request_id"] is not None


# ===========================================================================
# Upload limit middleware
# ===========================================================================

class TestUploadLimitMiddleware:
    def test_small_upload_allowed(self):
        client = TestClient(_make_app(api_keys=set(), max_upload_bytes=1024))
        r = client.post("/api/upload", content=b"small data")
        assert r.status_code == 200

    def test_oversized_upload_rejected(self):
        client = TestClient(_make_app(api_keys=set(), max_upload_bytes=100))
        r = client.post(
            "/api/upload",
            content=b"x" * 200,
            headers={"Content-Length": "200"},
        )
        assert r.status_code == 413
        assert "too large" in r.json()["detail"].lower()

    def test_no_content_length_passes(self):
        """Requests without Content-Length header are not rejected."""
        client = TestClient(_make_app(api_keys=set(), max_upload_bytes=100))
        r = client.get("/api/test")
        assert r.status_code == 200
