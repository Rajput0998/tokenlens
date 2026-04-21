"""Tests for anomaly detector, efficiency engine, and behavioral profiler."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from tokenlens.ml.anomaly import AnomalyDetector
from tokenlens.ml.efficiency import EfficiencyEngine
from tokenlens.ml.profiler import BehavioralProfiler


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_normal_hourly_data(hours: int = 336) -> pd.DataFrame:
    """Generate 14 days of normal hourly data."""
    rng = np.random.default_rng(42)
    rows = []
    for h in range(hours):
        total = 1000 + rng.normal(0, 100)
        rows.append({
            "total_tokens": max(total, 0),
            "input_tokens": max(total * 0.6, 0),
            "output_tokens": max(total * 0.4, 0),
            "session_count": rng.integers(1, 5),
            "avg_turn_count": 10 + rng.normal(0, 2),
            "dominant_tool_flag": 0,
        })
    return pd.DataFrame(rows)


def _make_daily_vectors(days: int = 40) -> pd.DataFrame:
    """Generate daily feature vectors for profiler testing."""
    rng = np.random.default_rng(42)
    rows = []
    for d in range(days):
        rows.append({
            "peak_hour": rng.integers(6, 12),  # Morning Sprinter pattern
            "total_tokens": 5000 + rng.normal(0, 500),
            "session_count": rng.integers(2, 8),
            "avg_session_duration": 30 + rng.normal(0, 10),
            "input_output_ratio": 1.5 + rng.normal(0, 0.3),
            "first_active_hour": rng.integers(6, 10),
            "last_active_hour": rng.integers(16, 22),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 21.2 — AnomalyDetector
# ---------------------------------------------------------------------------


class TestAnomalyDetector:
    """Test anomaly detector with mock feature vectors."""

    def test_train_with_sufficient_data(self) -> None:
        detector = AnomalyDetector()
        data = _make_normal_hourly_data(336)  # 14 days
        model = detector.train(data)
        assert model is not None
        assert model["confidence"] == "full"
        assert "model" in model

    def test_train_with_reduced_confidence(self) -> None:
        detector = AnomalyDetector()
        data = _make_normal_hourly_data(72)  # 3 days
        model = detector.train(data)
        assert model is not None
        assert model["confidence"] == "reduced"

    def test_train_insufficient_data(self) -> None:
        detector = AnomalyDetector()
        data = pd.DataFrame()
        model = detector.train(data)
        assert model is None

    def test_detect_normal_observation(self) -> None:
        detector = AnomalyDetector()
        data = _make_normal_hourly_data(336)
        model = detector.train(data)

        normal_obs = {
            "total_tokens": 1000,
            "input_ratio": 0.6,
            "output_ratio": 0.4,
            "session_count": 3,
            "avg_turn_count": 10,
            "dominant_tool_flag": 0,
        }
        result = detector.detect(normal_obs, model)
        assert "is_anomaly" in result
        assert "score" in result
        assert "classification" in result
        assert "severity" in result

    def test_detect_without_model(self) -> None:
        detector = AnomalyDetector()
        result = detector.detect({"total_tokens": 1000}, None)
        assert result["is_anomaly"] is False
        assert result["classification"] == "insufficient_data"

    def test_classify_input_heavy(self) -> None:
        detector = AnomalyDetector()
        classification, desc, severity = detector._classify(
            {"input_ratio": 0.9, "output_ratio": 0.1, "avg_turn_count": 5, "total_tokens": 1000},
            is_anomaly=True,
        )
        assert classification == "Large context loading"

    def test_classify_extended_conversation(self) -> None:
        detector = AnomalyDetector()
        classification, desc, severity = detector._classify(
            {"input_ratio": 0.5, "output_ratio": 0.5, "avg_turn_count": 50, "total_tokens": 1000},
            is_anomaly=True,
        )
        assert classification == "Extended conversation"


# ---------------------------------------------------------------------------
# 21.3 — EfficiencyEngine
# ---------------------------------------------------------------------------


class TestEfficiencyEngine:
    """Test efficiency scoring formula with known inputs."""

    def test_perfect_score(self) -> None:
        engine = EfficiencyEngine()
        result = engine.score_session({
            "output_input_ratio": 0.5,
            "cache_hit_rate": 0.5,
            "turn_count": 5,
            "context_growth_slope": 0.01,
            "cost_per_output_token": 0.0001,
        })
        assert result["score"] == pytest.approx(100.0, abs=0.1)

    def test_worst_score(self) -> None:
        engine = EfficiencyEngine()
        result = engine.score_session({
            "output_input_ratio": 0.0,
            "cache_hit_rate": 0.0,
            "turn_count": 50,
            "context_growth_slope": 0.10,
            "cost_per_output_token": 0.001,
        })
        assert result["score"] == pytest.approx(0.0, abs=0.1)

    def test_mid_range_score(self) -> None:
        engine = EfficiencyEngine()
        result = engine.score_session({
            "output_input_ratio": 0.25,
            "cache_hit_rate": 0.25,
            "turn_count": 27,
            "context_growth_slope": 0.055,
            "cost_per_output_token": 0.00055,
        })
        # Each component should be ~50, so total ~50
        assert 40 <= result["score"] <= 60

    def test_score_always_in_range(self) -> None:
        engine = EfficiencyEngine()
        # Extreme values
        result = engine.score_session({
            "output_input_ratio": 100.0,
            "cache_hit_rate": 100.0,
            "turn_count": -10,
            "context_growth_slope": -1.0,
            "cost_per_output_token": -0.01,
        })
        assert 0 <= result["score"] <= 100


class TestWastePatterns:
    """Test waste pattern detection rules."""

    def test_repeated_context_loading(self) -> None:
        engine = EfficiencyEngine()
        events = [{"input_tokens": 5000, "output_tokens": 200} for _ in range(10)]
        patterns = engine.detect_waste_patterns(events)
        assert "Repeated context loading" in patterns

    def test_excessive_back_and_forth(self) -> None:
        engine = EfficiencyEngine()
        events = [{"input_tokens": 500, "output_tokens": 50} for _ in range(25)]
        patterns = engine.detect_waste_patterns(events)
        assert "Excessive back-and-forth" in patterns

    def test_context_bloat(self) -> None:
        engine = EfficiencyEngine()
        events = [{"input_tokens": 100 * (1.15 ** i), "output_tokens": 50} for i in range(10)]
        patterns = engine.detect_waste_patterns(events)
        assert "Context bloat" in patterns

    def test_no_patterns_for_good_session(self) -> None:
        engine = EfficiencyEngine()
        events = [
            {"input_tokens": 500 + i * 10, "output_tokens": 300 + i * 5}
            for i in range(5)
        ]
        patterns = engine.detect_waste_patterns(events)
        assert len(patterns) == 0

    def test_empty_events(self) -> None:
        engine = EfficiencyEngine()
        patterns = engine.detect_waste_patterns([])
        assert patterns == []


class TestRecommendations:
    """Test recommendation generation."""

    def test_low_score_recommendation(self) -> None:
        engine = EfficiencyEngine()
        recs = engine.generate_recommendations(20.0, [])
        assert any("low" in r.lower() for r in recs)

    def test_pattern_specific_recommendations(self) -> None:
        engine = EfficiencyEngine()
        recs = engine.generate_recommendations(50.0, ["Context bloat"])
        assert any("context" in r.lower() for r in recs)

    def test_good_score_recommendation(self) -> None:
        engine = EfficiencyEngine()
        recs = engine.generate_recommendations(80.0, [])
        assert any("good" in r.lower() for r in recs)


# ---------------------------------------------------------------------------
# 21.4 — BehavioralProfiler
# ---------------------------------------------------------------------------


class TestBehavioralProfiler:
    """Test profiler with 30-day minimum and 3 archetypes."""

    def test_insufficient_data_returns_none(self) -> None:
        profiler = BehavioralProfiler()
        data = _make_daily_vectors(20)  # Less than 30
        model = profiler.train(data)
        assert model is None

    def test_sufficient_data_trains(self) -> None:
        profiler = BehavioralProfiler()
        data = _make_daily_vectors(40)
        model = profiler.train(data)
        assert model is not None
        assert model["training_days"] == 40
        assert len(model["archetype_map"]) == 3

    def test_classify_morning_sprinter(self) -> None:
        assert BehavioralProfiler.classify_archetype(8.0) == "Morning Sprinter"

    def test_classify_night_owl(self) -> None:
        assert BehavioralProfiler.classify_archetype(21.0) == "Night Owl"

    def test_classify_steady_coder(self) -> None:
        assert BehavioralProfiler.classify_archetype(14.0) == "Steady Coder"

    def test_predict_without_model(self) -> None:
        profiler = BehavioralProfiler()
        result = profiler.predict(None, {"peak_hour": 8})
        assert result["archetype"] == "Unknown"

    def test_three_archetypes_in_map(self) -> None:
        profiler = BehavioralProfiler()
        data = _make_daily_vectors(40)
        model = profiler.train(data)
        assert model is not None
        archetypes = set(model["archetype_map"].values())
        # All values should be valid archetype names
        valid = {"Morning Sprinter", "Steady Coder", "Night Owl"}
        assert archetypes.issubset(valid)
