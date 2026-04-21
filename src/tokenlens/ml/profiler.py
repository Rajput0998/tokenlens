"""Behavioral profiler — KMeans clustering on daily usage patterns.

Classifies users into 3 archetypes based on usage timing and patterns.
Requires minimum 30 days of data for reliable clustering.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path  # noqa: TC003
from typing import Any

import joblib
import pandas as pd
from sklearn.cluster import KMeans

from tokenlens.ml.base import MLModule

# Archetype definitions
ARCHETYPES = {
    "Morning Sprinter": "Peak activity between 6-12",
    "Steady Coder": "Even distribution throughout the day",
    "Night Owl": "Peak activity after 18:00",
}

_MIN_DAYS = 30


class BehavioralProfiler(MLModule):
    """Clusters daily usage into behavioral archetypes via KMeans.

    3 archetypes:
    - Morning Sprinter: peak_hour 6-12
    - Steady Coder: even hourly distribution (low variance)
    - Night Owl: peak_hour ≥ 18
    """

    def train(self, data: pd.DataFrame) -> Any:
        """Train KMeans on daily feature vectors.

        Expects DataFrame with columns: peak_hour, total_tokens, session_count,
        avg_session_duration, input_output_ratio, first_active_hour, last_active_hour.

        Returns trained model dict or None if <30 days of data.
        """
        if data.empty or len(data) < _MIN_DAYS:
            return None

        feature_cols = [
            "peak_hour",
            "total_tokens",
            "session_count",
            "avg_session_duration",
            "input_output_ratio",
            "first_active_hour",
            "last_active_hour",
        ]
        # Fill missing columns
        for col in feature_cols:
            if col not in data.columns:
                data[col] = 0

        features = data[feature_cols].fillna(0)

        # Normalize features for clustering
        from sklearn.preprocessing import StandardScaler

        scaler = StandardScaler()
        scaled = scaler.fit_transform(features)

        model = KMeans(n_clusters=3, random_state=42, n_init=10)
        model.fit(scaled)

        # Map clusters to archetypes
        archetype_map = self._map_clusters_to_archetypes(model, scaler, feature_cols)

        return {
            "model": model,
            "scaler": scaler,
            "feature_cols": feature_cols,
            "archetype_map": archetype_map,
            "trained_at": datetime.now(UTC),
            "training_days": len(data),
        }

    def _map_clusters_to_archetypes(
        self, model: KMeans, scaler: Any, feature_cols: list[str]
    ) -> dict[int, str]:
        """Map cluster centers to archetype names based on peak_hour."""
        centers = scaler.inverse_transform(model.cluster_centers_)
        peak_hour_idx = feature_cols.index("peak_hour")

        mapping: dict[int, str] = {}
        for i, center in enumerate(centers):
            peak = center[peak_hour_idx]
            mapping[i] = self.classify_archetype(peak)

        return mapping

    @staticmethod
    def classify_archetype(peak_hour: float) -> str:
        """Map a peak hour to an archetype name."""
        if 6 <= peak_hour < 12:
            return "Morning Sprinter"
        elif peak_hour >= 18:
            return "Night Owl"
        else:
            return "Steady Coder"

    def predict(self, model: Any, input_data: dict[str, Any]) -> dict[str, Any]:
        """Classify a single day's usage into an archetype.

        input_data should contain the same feature keys as training data.
        """
        if model is None:
            return {"archetype": "Unknown", "reason": "Insufficient data (need 30+ days)"}

        feature_cols = model["feature_cols"]
        scaler = model["scaler"]
        kmeans = model["model"]
        archetype_map = model["archetype_map"]

        values = [[input_data.get(col, 0) for col in feature_cols]]
        features_df = pd.DataFrame(values, columns=feature_cols)
        scaled = scaler.transform(features_df)
        cluster = int(kmeans.predict(scaled)[0])

        return {
            "archetype": archetype_map.get(cluster, "Steady Coder"),
            "cluster": cluster,
        }

    def detect_productive_hours(
        self, hourly_data: pd.DataFrame
    ) -> list[int]:
        """Find top 3 hours by output/input ratio.

        Expects DataFrame with columns: hour (0-23), output_tokens, input_tokens.
        """
        if hourly_data.empty:
            return []

        hourly = hourly_data.copy()
        hourly["ratio"] = hourly["output_tokens"] / hourly["input_tokens"].replace(0, 1)
        top = hourly.nlargest(3, "ratio")
        return top["hour"].tolist()

    def weekly_drift_report(
        self,
        current_week: dict[str, Any],
        previous_week: dict[str, Any],
        model: Any,
    ) -> dict[str, Any]:
        """Compare current vs previous week archetype."""
        if model is None:
            return {"drift": False, "reason": "No model available"}

        current_arch = self.predict(model, current_week)
        previous_arch = self.predict(model, previous_week)

        return {
            "current_archetype": current_arch["archetype"],
            "previous_archetype": previous_arch["archetype"],
            "drift": current_arch["archetype"] != previous_arch["archetype"],
        }

    def evaluate(self, model: Any, test_data: pd.DataFrame) -> dict[str, float]:
        """Evaluate clustering quality using inertia."""
        if model is None:
            return {"inertia": float("inf")}
        return {"inertia": float(model["model"].inertia_)}

    def save(self, model: Any, path: Path) -> None:
        """Persist model to disk."""
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, path)

    def load(self, path: Path) -> Any:
        """Load model from disk."""
        return joblib.load(path)
