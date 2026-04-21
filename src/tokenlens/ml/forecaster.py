"""Burn rate forecaster — time-series prediction of token consumption.

Uses statsmodels ExponentialSmoothing (Holt-Winters) as default for ≥7 days,
with optional Prophet upgrade if importable. Falls back to linear extrapolation
for 1-6 days, and returns None for <1 day of data.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path  # noqa: TC003
from typing import Any

import joblib
import numpy as np
import pandas as pd  # noqa: TC002

from tokenlens.core.config import get_data_dir
from tokenlens.ml.base import MLModule


def _prophet_available() -> bool:
    """Check if Prophet is importable."""
    try:
        from prophet import Prophet  # noqa: F401

        return True
    except ImportError:
        return False


class BurnRateForecaster(MLModule):
    """Forecasts hourly token burn rate per tool.

    Training strategy:
    - ≥7 days: ExponentialSmoothing (or Prophet if available)
    - 1-6 days: linear extrapolation
    - <1 day: returns None (collecting data)
    """

    def __init__(self) -> None:
        self._models_dir = get_data_dir() / "models"
        self._models_dir.mkdir(parents=True, exist_ok=True)

    def train(self, data: pd.DataFrame) -> Any:
        """Train on hourly token data.

        Expects DataFrame with columns: ds (datetime), y (float), tool (str).
        Returns dict with model_type and trained model, or None if insufficient data.
        """
        if data.empty:
            return None

        # Calculate data span in days
        data_span = (data["ds"].max() - data["ds"].min()).total_seconds() / 86400

        if data_span < 1:
            return None

        if data_span < 7:
            # Linear extrapolation
            return self._train_linear(data)

        # ≥7 days — try Prophet first, fall back to ExponentialSmoothing
        if _prophet_available():
            return self._train_prophet(data)
        return self._train_exponential_smoothing(data)

    def _train_linear(self, data: pd.DataFrame) -> dict[str, Any]:
        """Simple linear extrapolation for 1-6 days of data."""
        total_tokens = data["y"].sum()
        hours_elapsed = max(
            (data["ds"].max() - data["ds"].min()).total_seconds() / 3600, 1
        )
        hourly_rate = total_tokens / hours_elapsed

        return {
            "model_type": "linear",
            "hourly_rate": hourly_rate,
            "total_tokens": total_tokens,
            "hours_elapsed": hours_elapsed,
            "trained_at": datetime.now(UTC),
        }

    def _train_exponential_smoothing(self, data: pd.DataFrame) -> dict[str, Any]:
        """Holt-Winters ExponentialSmoothing with 24-hour seasonality."""
        from statsmodels.tsa.holtwinters import ExponentialSmoothing

        # Ensure hourly frequency and fill gaps
        ts = data.set_index("ds")["y"].resample("h").sum().fillna(0)

        # Need at least 2 full seasonal periods (48 hours)
        if len(ts) < 48:
            return self._train_linear(data)

        model = ExponentialSmoothing(
            ts,
            seasonal_periods=24,
            trend="add",
            seasonal="add",
        ).fit(optimized=True)

        return {
            "model_type": "exponential_smoothing",
            "model": model,
            "trained_at": datetime.now(UTC),
        }

    def _train_prophet(self, data: pd.DataFrame) -> dict[str, Any]:
        """Train Prophet model for ≥7 days of data."""
        from prophet import Prophet

        df = data[["ds", "y"]].copy()
        # Prophet doesn't support timezone-aware datetimes
        df["ds"] = df["ds"].dt.tz_localize(None)
        model = Prophet(
            yearly_seasonality=False,
            weekly_seasonality=True,
        )
        model.fit(df)

        return {
            "model_type": "prophet",
            "model": model,
            "trained_at": datetime.now(UTC),
        }

    def predict(self, model: Any, input_data: dict[str, Any]) -> dict[str, Any]:
        """Forecast next 24 hours with confidence bands.

        input_data may contain:
        - tool: str (tool name for metadata)
        - daily_limit: int (optional, for limit prediction)
        """
        if model is None:
            return {"status": "collecting_data", "forecast": []}

        model_type = model["model_type"]
        tool = input_data.get("tool", "unknown")
        daily_limit = input_data.get("daily_limit")

        if model_type == "linear":
            forecast = self._predict_linear(model)
        elif model_type == "exponential_smoothing":
            forecast = self._predict_exponential_smoothing(model)
        elif model_type == "prophet":
            forecast = self._predict_prophet(model)
        else:
            return {"status": "unknown_model_type", "forecast": []}

        result: dict[str, Any] = {
            "model_type": model_type,
            "tool": tool,
            "forecast": forecast,
            "trained_at": model.get("trained_at"),
        }

        if daily_limit is not None:
            result["limit_prediction"] = self._predict_limit_hit(forecast, daily_limit)

        return result

    def _predict_linear(self, model: dict[str, Any]) -> list[dict[str, Any]]:
        """Linear projection for next 24 hours."""
        hourly_rate = model["hourly_rate"]
        now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
        forecast = []
        for h in range(24):
            hour = now + timedelta(hours=h + 1)
            forecast.append({
                "hour": hour,
                "predicted_tokens": hourly_rate,
                "lower_80": hourly_rate * 0.7,
                "upper_80": hourly_rate * 1.3,
                "lower_95": hourly_rate * 0.5,
                "upper_95": hourly_rate * 1.5,
            })
        return forecast

    def _predict_exponential_smoothing(
        self, model: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Forecast using ExponentialSmoothing with simulation intervals."""
        fitted = model["model"]
        forecast_values = fitted.forecast(24)

        # Use simulation for confidence intervals
        try:
            sim = fitted.simulate(24, repetitions=200)
            lower_80 = sim.quantile(0.1, axis=1).values
            upper_80 = sim.quantile(0.9, axis=1).values
            lower_95 = sim.quantile(0.025, axis=1).values
            upper_95 = sim.quantile(0.975, axis=1).values
        except Exception:
            # Fallback: use ±30% and ±50% of forecast
            lower_80 = forecast_values.values * 0.7
            upper_80 = forecast_values.values * 1.3
            lower_95 = forecast_values.values * 0.5
            upper_95 = forecast_values.values * 1.5

        now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
        forecast = []
        for i in range(24):
            hour = now + timedelta(hours=i + 1)
            forecast.append({
                "hour": hour,
                "predicted_tokens": max(float(forecast_values.iloc[i]), 0),
                "lower_80": max(float(lower_80[i]), 0),
                "upper_80": max(float(upper_80[i]), 0),
                "lower_95": max(float(lower_95[i]), 0),
                "upper_95": max(float(upper_95[i]), 0),
            })
        return forecast

    def _predict_prophet(self, model: dict[str, Any]) -> list[dict[str, Any]]:
        """Forecast using Prophet with separate 80% and 95% intervals."""

        prophet_model = model["model"]
        future = prophet_model.make_future_dataframe(periods=24, freq="h")

        # Get 80% interval
        prophet_model.interval_width = 0.80
        pred_80 = prophet_model.predict(future).tail(24)

        # Get 95% interval
        prophet_model.interval_width = 0.95
        pred_95 = prophet_model.predict(future).tail(24)

        forecast = []
        for (_, r80), (_, r95) in zip(pred_80.iterrows(), pred_95.iterrows(), strict=True):
            forecast.append({
                "hour": r80["ds"].to_pydatetime(),
                "predicted_tokens": max(float(r80["yhat"]), 0),
                "lower_80": max(float(r80["yhat_lower"]), 0),
                "upper_80": max(float(r80["yhat_upper"]), 0),
                "lower_95": max(float(r95["yhat_lower"]), 0),
                "upper_95": max(float(r95["yhat_upper"]), 0),
            })
        return forecast

    def _predict_limit_hit(
        self, forecast: list[dict[str, Any]], daily_limit: int
    ) -> dict[str, Any]:
        """Find first hour where cumulative tokens exceed daily limit."""
        cumulative = 0.0
        for entry in forecast:
            cumulative += entry["predicted_tokens"]
            if cumulative > daily_limit:
                return {
                    "will_hit_limit": True,
                    "estimated_time": entry["hour"],
                    "confidence_pct": 80.0,
                }
        return {
            "will_hit_limit": False,
            "estimated_time": None,
            "confidence_pct": 80.0,
        }

    def evaluate(self, model: Any, test_data: pd.DataFrame) -> dict[str, float]:
        """Evaluate model on test data. Returns MAE and RMSE."""
        if model is None or test_data.empty:
            return {"mae": float("inf"), "rmse": float("inf")}

        predictions = self.predict(model, {})
        if not predictions.get("forecast"):
            return {"mae": float("inf"), "rmse": float("inf")}

        pred_values = [f["predicted_tokens"] for f in predictions["forecast"]]
        actual = test_data["y"].values[: len(pred_values)]

        if len(actual) == 0:
            return {"mae": float("inf"), "rmse": float("inf")}

        pred_arr = np.array(pred_values[: len(actual)])
        errors = actual - pred_arr
        return {
            "mae": float(np.mean(np.abs(errors))),
            "rmse": float(np.sqrt(np.mean(errors**2))),
        }

    def save(self, model: Any, path: Path) -> None:
        """Persist model to disk via joblib."""
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, path)

    def load(self, path: Path) -> Any:
        """Load model from disk."""
        return joblib.load(path)
