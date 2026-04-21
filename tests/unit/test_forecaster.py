"""Tests for BurnRateForecaster and BudgetForecaster."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from tokenlens.ml.budget import BudgetForecaster
from tokenlens.ml.forecaster import BurnRateForecaster


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_hourly_data(days: int, base_tokens: float = 1000.0) -> pd.DataFrame:
    """Generate synthetic hourly token data for testing."""
    hours = days * 24
    start = datetime(2025, 1, 1, tzinfo=UTC)
    rows = []
    for h in range(hours):
        rows.append({
            "ds": start + timedelta(hours=h),
            "y": base_tokens + np.random.default_rng(h).normal(0, 100),
            "tool": "claude_code",
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 20.1 — BurnRateForecaster cold start states
# ---------------------------------------------------------------------------


class TestForecasterColdStart:
    """Test cold start: <1 day → None, 1-6 days → linear, ≥7 days → ExponentialSmoothing."""

    def test_less_than_one_day_returns_none(self) -> None:
        forecaster = BurnRateForecaster()
        data = _make_hourly_data(0)  # empty
        result = forecaster.train(data)
        assert result is None

    def test_half_day_returns_none(self) -> None:
        forecaster = BurnRateForecaster()
        start = datetime(2025, 1, 1, tzinfo=UTC)
        data = pd.DataFrame([
            {"ds": start + timedelta(hours=h), "y": 100.0, "tool": "claude_code"}
            for h in range(12)
        ])
        result = forecaster.train(data)
        assert result is None

    def test_three_days_returns_linear(self) -> None:
        forecaster = BurnRateForecaster()
        data = _make_hourly_data(3)
        result = forecaster.train(data)
        assert result is not None
        assert result["model_type"] == "linear"

    def test_seven_days_returns_exponential_smoothing(self) -> None:
        forecaster = BurnRateForecaster()
        data = _make_hourly_data(10)
        result = forecaster.train(data)
        assert result is not None
        assert result["model_type"] in ("exponential_smoothing", "prophet")


# ---------------------------------------------------------------------------
# 20.1 — Linear extrapolation formula
# ---------------------------------------------------------------------------


class TestLinearExtrapolation:
    """Test linear formula: (total_today / hours_elapsed) × 24."""

    def test_linear_hourly_rate(self) -> None:
        forecaster = BurnRateForecaster()
        start = datetime(2025, 1, 1, tzinfo=UTC)
        # 48 hours of data, 100 tokens per hour = 4800 total
        data = pd.DataFrame([
            {"ds": start + timedelta(hours=h), "y": 100.0, "tool": "claude_code"}
            for h in range(48)
        ])
        result = forecaster.train(data)
        assert result is not None
        assert result["model_type"] == "linear"
        # hourly_rate = 4800 / 47 ≈ 102.13 (47 hours elapsed between first and last)
        assert result["hourly_rate"] == pytest.approx(4800 / 47, rel=0.01)


# ---------------------------------------------------------------------------
# 20.1 — Forecast structure
# ---------------------------------------------------------------------------


class TestForecastStructure:
    """Test forecast output has correct structure (24 entries, confidence bands)."""

    def test_linear_forecast_has_24_entries(self) -> None:
        forecaster = BurnRateForecaster()
        model = {
            "model_type": "linear",
            "hourly_rate": 100.0,
            "total_tokens": 2400.0,
            "hours_elapsed": 24.0,
            "trained_at": datetime.now(UTC),
        }
        result = forecaster.predict(model, {"tool": "claude_code"})
        assert len(result["forecast"]) == 24
        assert result["model_type"] == "linear"
        assert result["tool"] == "claude_code"

    def test_forecast_entries_have_bands(self) -> None:
        forecaster = BurnRateForecaster()
        model = {
            "model_type": "linear",
            "hourly_rate": 100.0,
            "total_tokens": 2400.0,
            "hours_elapsed": 24.0,
            "trained_at": datetime.now(UTC),
        }
        result = forecaster.predict(model, {"tool": "claude_code"})
        entry = result["forecast"][0]
        assert "hour" in entry
        assert "predicted_tokens" in entry
        assert "lower_80" in entry
        assert "upper_80" in entry
        assert "lower_95" in entry
        assert "upper_95" in entry

    def test_collecting_data_status(self) -> None:
        forecaster = BurnRateForecaster()
        result = forecaster.predict(None, {"tool": "claude_code"})
        assert result["status"] == "collecting_data"
        assert result["forecast"] == []


# ---------------------------------------------------------------------------
# 20.1 — Limit prediction
# ---------------------------------------------------------------------------


class TestLimitPrediction:
    """Test _predict_limit_hit."""

    def test_limit_hit_detected(self) -> None:
        forecaster = BurnRateForecaster()
        forecast = [{"predicted_tokens": 500.0, "hour": datetime.now(UTC)} for _ in range(24)]
        result = forecaster._predict_limit_hit(forecast, 5000)
        assert result["will_hit_limit"] is True
        assert result["estimated_time"] is not None

    def test_limit_not_hit(self) -> None:
        forecaster = BurnRateForecaster()
        forecast = [{"predicted_tokens": 100.0, "hour": datetime.now(UTC)} for _ in range(24)]
        result = forecaster._predict_limit_hit(forecast, 500000)
        assert result["will_hit_limit"] is False
        assert result["estimated_time"] is None


# ---------------------------------------------------------------------------
# 20.2 — BudgetForecaster
# ---------------------------------------------------------------------------


class TestBudgetForecaster:
    """Test budget cost derivation and recommendations."""

    def test_project_monthly_cost(self) -> None:
        bf = BudgetForecaster()
        forecast = [{"predicted_tokens": 1000.0} for _ in range(24)]
        pricing = {"claude-sonnet-4": {"input": 3.0, "output": 15.0}}
        result = bf.project_monthly_cost(forecast, pricing, model="claude-sonnet-4")
        # daily_tokens = 24000, avg_price = (3+15)/2 / 1M = 9/1M
        # daily_cost = 24000 * 9/1M = 0.216
        # monthly = 0.216 * 30 = 6.48
        assert result["projected_monthly_cost"] == pytest.approx(6.48, rel=0.01)

    def test_daily_recommendation(self) -> None:
        bf = BudgetForecaster()
        # budget=50, spent=20, 10 days remaining → (50-20)/10 = 3.0
        rec = bf.compute_daily_recommendation(50.0, 20.0, 10)
        assert rec == pytest.approx(3.0)

    def test_daily_recommendation_zero_days(self) -> None:
        bf = BudgetForecaster()
        rec = bf.compute_daily_recommendation(50.0, 20.0, 0)
        assert rec == 0.0

    def test_daily_recommendation_over_budget(self) -> None:
        bf = BudgetForecaster()
        rec = bf.compute_daily_recommendation(50.0, 60.0, 10)
        assert rec == 0.0

    def test_over_budget_flag(self) -> None:
        bf = BudgetForecaster()
        # projected=56, budget=50 → 56 > 50*1.10=55 → True
        assert bf.is_over_budget(56.0, 50.0) is True
        # projected=54, budget=50 → 54 < 55 → False
        assert bf.is_over_budget(54.0, 50.0) is False
        # Exactly at 110% → not over
        assert bf.is_over_budget(55.0, 50.0) is False
