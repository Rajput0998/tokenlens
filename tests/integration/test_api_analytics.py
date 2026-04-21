"""Integration tests for analytics endpoints."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from tokenlens.api.app import create_app


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestTimelineEndpoint:
    @pytest.mark.asyncio
    async def test_timeline_returns_list(self, client):
        resp = await client.get("/api/v1/analytics/timeline")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    @pytest.mark.asyncio
    async def test_timeline_with_period(self, client):
        resp = await client.get("/api/v1/analytics/timeline?period=1d")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_timeline_invalid_period(self, client):
        resp = await client.get("/api/v1/analytics/timeline?period=invalid")
        assert resp.status_code == 422


class TestHeatmapEndpoint:
    @pytest.mark.asyncio
    async def test_heatmap_returns_list(self, client):
        resp = await client.get("/api/v1/analytics/heatmap")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestToolsEndpoint:
    @pytest.mark.asyncio
    async def test_tools_returns_list(self, client):
        resp = await client.get("/api/v1/analytics/tools")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestModelsEndpoint:
    @pytest.mark.asyncio
    async def test_models_returns_list(self, client):
        resp = await client.get("/api/v1/analytics/models")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestSummaryEndpoint:
    @pytest.mark.asyncio
    async def test_summary_returns_periods(self, client):
        resp = await client.get("/api/v1/analytics/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert "today" in data
        assert "week" in data
        assert "month" in data
        assert "all_time" in data

    @pytest.mark.asyncio
    async def test_summary_period_has_fields(self, client):
        resp = await client.get("/api/v1/analytics/summary")
        data = resp.json()
        for period in ["today", "week", "month", "all_time"]:
            assert "tokens" in data[period]
            assert "cost" in data[period]
            assert "events" in data[period]
            assert "sessions" in data[period]
