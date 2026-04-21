"""Integration tests for WebSocket endpoints and alert engine."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from tokenlens.alerts.engine import AlertEngine
from tokenlens.api.app import create_app


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestAlertEngine:
    def test_threshold_50_percent(self):
        engine = AlertEngine()
        alerts = engine.check_thresholds(
            current_tokens=250_000,
            daily_limit=500_000,
            current_cost=0,
            monthly_budget=50.0,
        )
        assert len(alerts) >= 1
        assert any(a["threshold_pct"] == 50 for a in alerts)

    def test_threshold_dedup(self):
        engine = AlertEngine()
        # First call generates alert
        alerts1 = engine.check_thresholds(
            current_tokens=250_000,
            daily_limit=500_000,
            current_cost=0,
            monthly_budget=50.0,
        )
        # Second call should be deduped
        alerts2 = engine.check_thresholds(
            current_tokens=260_000,
            daily_limit=500_000,
            current_cost=0,
            monthly_budget=50.0,
        )
        assert len(alerts1) > 0
        assert len(alerts2) == 0

    def test_multiple_thresholds(self):
        engine = AlertEngine()
        alerts = engine.check_thresholds(
            current_tokens=475_000,
            daily_limit=500_000,
            current_cost=0,
            monthly_budget=50.0,
        )
        # Should trigger 50, 75, 90 thresholds
        pcts = {a["threshold_pct"] for a in alerts}
        assert 50 in pcts
        assert 75 in pcts
        assert 90 in pcts

    def test_cost_threshold(self):
        engine = AlertEngine()
        alerts = engine.check_thresholds(
            current_tokens=0,
            daily_limit=500_000,
            current_cost=40.0,
            monthly_budget=50.0,
        )
        # 80% of budget
        pcts = {a["threshold_pct"] for a in alerts if a["category"] == "cost_threshold"}
        assert 50 in pcts
        assert 75 in pcts

    def test_anomaly_alert(self):
        engine = AlertEngine()
        anomaly_result = {
            "is_anomaly": True,
            "classification": "Usage burst",
            "severity": "critical",
            "description": "Token usage is unusually high.",
            "score": -0.5,
        }
        alerts = engine.check_anomaly(anomaly_result)
        assert len(alerts) == 1
        assert alerts[0]["category"] == "anomaly"
        assert alerts[0]["severity"] == "critical"

    def test_anomaly_no_alert_when_normal(self):
        engine = AlertEngine()
        alerts = engine.check_anomaly({"is_anomaly": False})
        assert len(alerts) == 0

    def test_predictive_alert(self):
        engine = AlertEngine()
        alerts = engine.check_predictive(hours_to_limit=1.5)
        assert len(alerts) == 1
        assert alerts[0]["category"] == "predictive"

    def test_predictive_no_alert_when_far(self):
        engine = AlertEngine()
        alerts = engine.check_predictive(hours_to_limit=5.0)
        assert len(alerts) == 0

    def test_model_switch_detection(self):
        engine = AlertEngine()
        alerts = engine.check_model_switch(
            current_model="claude-opus-4",
            previous_model="claude-sonnet-4",
            session_id="sess-1",
        )
        assert len(alerts) == 1
        assert alerts[0]["category"] == "model_switch"

    def test_model_switch_no_alert_same_model(self):
        engine = AlertEngine()
        alerts = engine.check_model_switch(
            current_model="claude-sonnet-4",
            previous_model="claude-sonnet-4",
        )
        assert len(alerts) == 0

    def test_reset_dedup(self):
        engine = AlertEngine()
        engine.check_thresholds(250_000, 500_000, 0, 50.0)
        engine.reset_dedup()
        # After reset, should fire again
        alerts = engine.check_thresholds(250_000, 500_000, 0, 50.0)
        assert len(alerts) > 0


class TestWebSocketLive:
    @pytest.mark.asyncio
    async def test_ws_live_endpoint_exists(self, client):
        """Verify the /ws/live endpoint is registered (connection test)."""
        # We can't easily test WebSocket with httpx, but we can verify
        # the app has the route registered
        from tokenlens.api.app import create_app

        app = create_app()
        routes = [r.path for r in app.routes]
        assert "/ws/live" in routes

    @pytest.mark.asyncio
    async def test_ws_alerts_endpoint_exists(self, client):
        """Verify the /ws/alerts endpoint is registered."""
        from tokenlens.api.app import create_app

        app = create_app()
        routes = [r.path for r in app.routes]
        assert "/ws/alerts" in routes
