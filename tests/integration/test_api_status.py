"""Integration tests for status, events, and sessions endpoints."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from httpx import ASGITransport, AsyncClient

from tokenlens.api.app import create_app
from tokenlens.core.models import SessionRow, TokenEventRow

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def seeded_session(async_session: AsyncSession):
    """Seed test data into the database."""
    now = datetime.now(UTC)

    # Add token events
    for i in range(5):
        event = TokenEventRow(
            id=f"evt-{i}",
            tool="claude_code",
            model="claude-sonnet-4",
            user_id="test-user",
            session_id="sess-1",
            timestamp=now - timedelta(minutes=i * 10),
            input_tokens=1000 + i * 100,
            output_tokens=500 + i * 50,
            cost_usd=0.01 * (i + 1),
        )
        async_session.add(event)

    # Add a session
    session_row = SessionRow(
        id="sess-1",
        tool="claude_code",
        start_time=now - timedelta(hours=1),
        end_time=now - timedelta(minutes=5),
        total_input_tokens=5500,
        total_output_tokens=2750,
        total_cost_usd=0.15,
        turn_count=5,
        efficiency_score=72.5,
    )
    async_session.add(session_row)
    await async_session.commit()
    return async_session


class TestStatusEndpoint:
    @pytest.mark.asyncio
    async def test_status_returns_200(self, client):
        resp = await client.get("/api/v1/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "today_tokens" in data
        assert "per_tool" in data
        assert "burn_rate" in data
        assert "daemon_healthy" in data

    @pytest.mark.asyncio
    async def test_status_fields_types(self, client):
        resp = await client.get("/api/v1/status")
        data = resp.json()
        assert isinstance(data["today_tokens"], int)
        assert isinstance(data["per_tool"], dict)
        assert isinstance(data["active_sessions"], int)
        assert data["burn_rate"] in ("slow", "normal", "fast", "critical")


class TestEventsEndpoint:
    @pytest.mark.asyncio
    async def test_events_returns_paginated(self, client):
        resp = await client.get("/api/v1/events")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "meta" in data
        assert "page" in data["meta"]
        assert "per_page" in data["meta"]
        assert "total" in data["meta"]
        assert "total_pages" in data["meta"]

    @pytest.mark.asyncio
    async def test_events_pagination_params(self, client):
        resp = await client.get("/api/v1/events?page=1&per_page=10")
        assert resp.status_code == 200
        data = resp.json()
        assert data["meta"]["page"] == 1
        assert data["meta"]["per_page"] == 10

    @pytest.mark.asyncio
    async def test_events_filter_by_tool(self, client):
        resp = await client.get("/api/v1/events?tool=claude_code")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_events_invalid_page(self, client):
        resp = await client.get("/api/v1/events?page=0")
        assert resp.status_code == 422


class TestSessionsEndpoint:
    @pytest.mark.asyncio
    async def test_sessions_returns_paginated(self, client):
        resp = await client.get("/api/v1/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "meta" in data

    @pytest.mark.asyncio
    async def test_session_detail_not_found(self, client):
        resp = await client.get("/api/v1/sessions/nonexistent-id")
        assert resp.status_code == 404
