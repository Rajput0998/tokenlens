"""FastAPI middleware: CORS, request ID, rate limiter."""

from __future__ import annotations

import time
import uuid
from typing import TYPE_CHECKING

from fastapi import Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

if TYPE_CHECKING:
    from fastapi import FastAPI


# --- Token Bucket Rate Limiter ---


class TokenBucket:
    """In-memory token bucket for rate limiting."""

    def __init__(self, rate: float = 100.0, capacity: float = 100.0) -> None:
        self.rate = rate  # tokens per second
        self.capacity = capacity
        self._buckets: dict[str, tuple[float, float]] = {}  # ip -> (tokens, last_time)

    def consume(self, key: str) -> tuple[bool, float]:
        """Try to consume a token. Returns (allowed, retry_after_seconds)."""
        now = time.time()
        tokens, last_time = self._buckets.get(key, (self.capacity, now))

        # Refill tokens based on elapsed time
        elapsed = now - last_time
        tokens = min(self.capacity, tokens + elapsed * self.rate)

        if tokens >= 1.0:
            tokens -= 1.0
            self._buckets[key] = (tokens, now)
            return True, 0.0
        else:
            # Calculate time until next token
            retry_after = (1.0 - tokens) / self.rate
            self._buckets[key] = (tokens, now)
            return False, retry_after


_rate_limiter = TokenBucket(rate=100.0, capacity=100.0)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Token bucket rate limiter: 100 req/s per client IP."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        client_ip = request.client.host if request.client else "unknown"
        allowed, retry_after = _rate_limiter.consume(client_ip)

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too Many Requests"},
                headers={"Retry-After": str(int(retry_after) + 1)},
            )

        return await call_next(request)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attach a unique X-Request-ID to every response."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


def setup_middleware(app: FastAPI) -> None:
    """Configure all middleware on the FastAPI app."""
    from tokenlens.core.config import settings

    # CORS
    origins = settings.get(
        "api.cors_origins",
        ["http://localhost:5173", "http://localhost:7890"],
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request ID
    app.add_middleware(RequestIDMiddleware)

    # Rate limiter
    app.add_middleware(RateLimitMiddleware)
