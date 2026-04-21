"""Tests for API middleware: rate limiter, request ID, CORS, health endpoint."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from tokenlens.api.app import create_app
from tokenlens.api.middleware import TokenBucket

# --- TokenBucket unit tests ---


class TestTokenBucket:
    def test_allows_requests_within_capacity(self):
        bucket = TokenBucket(rate=10.0, capacity=10.0)
        for _ in range(10):
            allowed, _ = bucket.consume("test-ip")
            assert allowed is True

    def test_rejects_when_exhausted(self):
        bucket = TokenBucket(rate=10.0, capacity=10.0)
        # Exhaust all tokens
        for _ in range(10):
            bucket.consume("test-ip")
        # Next should be rejected
        allowed, retry_after = bucket.consume("test-ip")
        assert allowed is False
        assert retry_after > 0

    def test_different_keys_independent(self):
        bucket = TokenBucket(rate=1.0, capacity=1.0)
        allowed1, _ = bucket.consume("ip-1")
        allowed2, _ = bucket.consume("ip-2")
        assert allowed1 is True
        assert allowed2 is True

    def test_refills_over_time(self):
        bucket = TokenBucket(rate=100.0, capacity=100.0)
        # Exhaust
        for _ in range(100):
            bucket.consume("test-ip")
        # Manually set last time to 1 second ago to simulate time passing
        tokens, last_time = bucket._buckets["test-ip"]
        bucket._buckets["test-ip"] = (tokens, last_time - 1.0)
        # Should now have refilled
        allowed, _ = bucket.consume("test-ip")
        assert allowed is True


# --- Integration tests with FastAPI app ---


@pytest.fixture
def app():
    """Create a test app instance."""
    return create_app()


@pytest.fixture
async def client(app):
    """Create an async test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestHealthEndpoint:
    @pytest.mark.asyncio
    async def test_health_returns_ok(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data

    @pytest.mark.asyncio
    async def test_health_version_matches(self, client):
        from tokenlens import __version__

        resp = await client.get("/health")
        assert resp.json()["version"] == __version__


class TestRequestIDMiddleware:
    @pytest.mark.asyncio
    async def test_response_has_request_id(self, client):
        resp = await client.get("/health")
        assert "x-request-id" in resp.headers
        # Should be a valid UUID format
        request_id = resp.headers["x-request-id"]
        assert len(request_id) == 36  # UUID format

    @pytest.mark.asyncio
    async def test_each_request_gets_unique_id(self, client):
        resp1 = await client.get("/health")
        resp2 = await client.get("/health")
        assert resp1.headers["x-request-id"] != resp2.headers["x-request-id"]


class TestCORSMiddleware:
    @pytest.mark.asyncio
    async def test_cors_headers_on_preflight(self, client):
        resp = await client.options(
            "/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.status_code == 200
        assert "access-control-allow-origin" in resp.headers


class TestRateLimiter:
    @pytest.mark.asyncio
    async def test_rate_limiter_allows_normal_traffic(self, client):
        # A few requests should be fine
        for _ in range(5):
            resp = await client.get("/health")
            assert resp.status_code == 200
