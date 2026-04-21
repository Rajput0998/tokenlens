"""Integration tests for predictions, efficiency, anomalies, settings, export."""

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


class TestPredictionsEndpoints:
    @pytest.mark.asyncio
    async def test_burnrate(self, client):
        resp = await client.get("/api/v1/predictions/burnrate")
        assert resp.status_code == 200
        data = resp.json()
        assert "forecast" in data

    @pytest.mark.asyncio
    async def test_limit(self, client):
        resp = await client.get("/api/v1/predictions/limit")
        assert resp.status_code == 200
        data = resp.json()
        assert "will_hit_limit" in data
        assert "daily_limit" in data

    @pytest.mark.asyncio
    async def test_budget(self, client):
        resp = await client.get("/api/v1/predictions/budget")
        assert resp.status_code == 200
        data = resp.json()
        assert "projected_monthly_cost" in data
        assert "is_over_budget" in data

    @pytest.mark.asyncio
    async def test_whatif(self, client):
        resp = await client.post(
            "/api/v1/predictions/whatif",
            json={"usage_pct_change": -0.2},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "baseline_monthly_cost" in data
        assert "projected_monthly_cost" in data
        assert "pct_change" in data

    @pytest.mark.asyncio
    async def test_profile(self, client):
        resp = await client.get("/api/v1/predictions/profile")
        assert resp.status_code == 200
        data = resp.json()
        assert "archetype" in data


class TestEfficiencyEndpoints:
    @pytest.mark.asyncio
    async def test_sessions(self, client):
        resp = await client.get("/api/v1/efficiency/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "meta" in data

    @pytest.mark.asyncio
    async def test_recommendations(self, client):
        resp = await client.get("/api/v1/efficiency/recommendations")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    @pytest.mark.asyncio
    async def test_trends(self, client):
        resp = await client.get("/api/v1/efficiency/trends")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestAnomaliesEndpoints:
    @pytest.mark.asyncio
    async def test_list_anomalies(self, client):
        resp = await client.get("/api/v1/anomalies")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "meta" in data

    @pytest.mark.asyncio
    async def test_anomaly_not_found(self, client):
        resp = await client.get("/api/v1/anomalies/nonexistent-id")
        assert resp.status_code == 404


class TestSettingsEndpoints:
    @pytest.mark.asyncio
    async def test_get_settings(self, client):
        resp = await client.get("/api/v1/settings")
        assert resp.status_code == 200
        data = resp.json()
        assert "settings" in data

    @pytest.mark.asyncio
    async def test_put_settings(self, client):
        resp = await client.put(
            "/api/v1/settings",
            json={"settings": {"alerts.thresholds.daily_token_limit": "600000"}},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "settings" in data

    @pytest.mark.asyncio
    async def test_get_adapters(self, client):
        resp = await client.get("/api/v1/settings/adapters")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestExportEndpoints:
    @pytest.mark.asyncio
    async def test_export_events_json(self, client):
        resp = await client.get("/api/v1/export/events?format=json")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_export_events_csv(self, client):
        resp = await client.get("/api/v1/export/events?format=csv")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_export_report_json(self, client):
        resp = await client.get("/api/v1/export/report?period=today&format=json")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_export_report_markdown(self, client):
        resp = await client.get("/api/v1/export/report?period=week&format=markdown")
        assert resp.status_code == 200
