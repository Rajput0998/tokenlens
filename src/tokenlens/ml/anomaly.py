"""Anomaly detector — IsolationForest on personal usage baseline.

Detects unusual token consumption patterns using a rolling 14-day baseline.
Classifies anomalies by type and severity using configurable rules.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path  # noqa: TC003
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from tokenlens.core.config import settings
from tokenlens.ml.base import MLModule


class AnomalyDetector(MLModule):
    """Detects anomalous token usage via IsolationForest on hourly feature vectors."""

    def _build_feature_vectors(self, hourly_data: pd.DataFrame) -> pd.DataFrame:
        """Build feature vectors from hourly token event data.

        Expects columns: total_tokens, input_tokens, output_tokens,
        session_count, avg_turn_count, dominant_tool_flag.
        """
        features = hourly_data.copy()

        if "input_tokens" in features.columns and "total_tokens" in features.columns:
            total = features["total_tokens"].replace(0, 1)
            features["input_ratio"] = features["input_tokens"] / total
            features["output_ratio"] = features.get("output_tokens", 0) / total
        else:
            features["input_ratio"] = 0.5
            features["output_ratio"] = 0.5

        feature_cols = [
            "total_tokens",
            "input_ratio",
            "output_ratio",
            "session_count",
            "avg_turn_count",
            "dominant_tool_flag",
        ]
        # Fill missing columns with 0
        for col in feature_cols:
            if col not in features.columns:
                features[col] = 0

        return features[feature_cols].fillna(0)

    def train(self, data: pd.DataFrame) -> Any:
        """Train IsolationForest on baseline data.

        Args:
            data: DataFrame with hourly feature vectors.

        Returns:
            Dict with model and metadata, or None if insufficient data.
        """
        if data.empty or len(data) < 24:
            return None

        features = self._build_feature_vectors(data)
        confidence = "full" if len(data) >= 14 * 24 else "reduced"

        model = IsolationForest(
            contamination="auto",
            random_state=42,
        )
        model.fit(features)

        return {
            "model": model,
            "confidence": confidence,
            "trained_at": datetime.now(UTC),
            "training_samples": len(data),
        }

    def detect(self, hourly_data: dict[str, Any], model: Any) -> dict[str, Any]:
        """Score a single hourly observation against the trained model.

        Args:
            hourly_data: Dict with feature values for one hour.
            model: Trained model dict from train().

        Returns:
            Dict with is_anomaly, score, classification, severity, description, confidence.
        """
        if model is None:
            return {
                "is_anomaly": False,
                "score": 0.0,
                "classification": "insufficient_data",
                "severity": "warning",
                "description": "Not enough data for anomaly detection.",
                "confidence": "reduced",
            }

        iso_model = model["model"]
        confidence = model["confidence"]

        # Build feature vector
        feature_cols = [
            "total_tokens",
            "input_ratio",
            "output_ratio",
            "session_count",
            "avg_turn_count",
            "dominant_tool_flag",
        ]
        values = [[hourly_data.get(col, 0) for col in feature_cols]]
        features_df = pd.DataFrame(values, columns=feature_cols)

        score = float(iso_model.decision_function(features_df)[0])
        prediction = int(iso_model.predict(features_df)[0])
        is_anomaly = prediction == -1

        # Classify the anomaly
        classification, description, severity = self._classify(hourly_data, is_anomaly)

        return {
            "is_anomaly": is_anomaly,
            "score": score,
            "classification": classification,
            "severity": severity,
            "description": description,
            "confidence": confidence,
        }

    def _classify(
        self, data: dict[str, Any], is_anomaly: bool
    ) -> tuple[str, str, str]:
        """Classify anomaly type using configurable rules from [ml.anomaly] config."""
        if not is_anomaly:
            return ("normal", "Normal usage pattern.", "warning")

        input_ratio = data.get("input_ratio", 0.5)
        output_ratio = data.get("output_ratio", 0.5)
        avg_turn_count = data.get("avg_turn_count", 0)
        total_tokens = data.get("total_tokens", 0)

        # Config thresholds
        extended_turns = settings.get("ml.anomaly.extended_conversation_turns", 30)

        # Rule 1: Input-heavy (ratio >5:1)
        if output_ratio > 0 and input_ratio / max(output_ratio, 0.001) > 5:
            return (
                "Large context loading",
                "Input tokens significantly exceed output tokens (>5:1 ratio).",
                "warning",
            )

        # Rule 2: Extended conversation
        if avg_turn_count > extended_turns:
            return (
                "Extended conversation",
                f"Average turn count ({avg_turn_count:.0f}) exceeds threshold ({extended_turns}).",
                "warning",
            )

        # Rule 3: Usage burst (simplified — compare against a baseline)
        # In production this would compare against daily_avg from training data
        if total_tokens > 50000:  # High absolute threshold as fallback
            return (
                "Usage burst",
                f"Token usage ({total_tokens:,}) is unusually high.",
                "critical",
            )

        return (
            "Unclassified anomaly",
            "Unusual usage pattern detected but doesn't match known categories.",
            "warning",
        )

    def predict(self, model: Any, input_data: dict[str, Any]) -> dict[str, Any]:
        """Alias for detect() to satisfy MLModule interface."""
        return self.detect(input_data, model)

    def evaluate(self, model: Any, test_data: pd.DataFrame) -> dict[str, float]:
        """Evaluate anomaly detector on labeled test data."""
        if model is None or test_data.empty:
            return {"accuracy": 0.0}

        features = self._build_feature_vectors(test_data)
        iso_model = model["model"]
        predictions = iso_model.predict(features)
        # Without labels, return the fraction flagged as anomalous
        anomaly_rate = float(np.mean(predictions == -1))
        return {"anomaly_rate": anomaly_rate}

    def save(self, model: Any, path: Path) -> None:
        """Persist model to disk."""
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, path)

    def load(self, path: Path) -> Any:
        """Load model from disk."""
        return joblib.load(path)
