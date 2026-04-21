"""Context efficiency engine — scores sessions and detects waste patterns.

Scoring formula uses 5 weighted factors normalized to 0-100.
Waste pattern detection identifies common inefficiency patterns.
"""

from __future__ import annotations

from typing import Any


def _normalize(value: float, low: float, high: float) -> float:
    """Normalize a value to 0-100 range. low→0, high→100, clamped."""
    if high == low:
        return 50.0
    score = (value - low) / (high - low) * 100
    return max(0.0, min(100.0, score))


class EfficiencyEngine:
    """Scores session efficiency and detects waste patterns.

    Scoring weights:
    - Output/Input ratio: 30%  (0.0→0, ≥0.5→100)
    - Cache hit rate: 25%      (0%→0, ≥50%→100)
    - Turns to completion: 20% (≥50→0, ≤5→100)
    - Context growth slope: 15% (≥10%→0, ≤1%→100)
    - Cost per output token: 10% (≥$0.001→0, ≤$0.0001→100)
    """

    WEIGHTS = {
        "output_input_ratio": 0.30,
        "cache_hit_rate": 0.25,
        "turns_to_completion": 0.20,
        "context_growth_slope": 0.15,
        "cost_per_output_token": 0.10,
    }

    def score_session(self, session_data: dict[str, Any]) -> dict[str, Any]:
        """Compute weighted efficiency score 0-100 for a session.

        Args:
            session_data: Dict with keys:
                - output_input_ratio: float (output_tokens / input_tokens)
                - cache_hit_rate: float (0.0-1.0)
                - turn_count: int
                - context_growth_slope: float (% growth per turn, e.g. 0.05 = 5%)
                - cost_per_output_token: float (USD)

        Returns:
            Dict with score, component_scores, and percentile placeholder.
        """
        components = self._compute_components(session_data)
        total = sum(
            components[k] * self.WEIGHTS[k] for k in self.WEIGHTS
        )
        # Clamp to [0, 100]
        total = max(0.0, min(100.0, total))

        return {
            "score": total,
            "component_scores": components,
        }

    def _compute_components(self, data: dict[str, Any]) -> dict[str, float]:
        """Compute individual component scores (each 0-100)."""
        oi_ratio = data.get("output_input_ratio", 0.0)
        cache_rate = data.get("cache_hit_rate", 0.0)
        turns = data.get("turn_count", 50)
        growth = data.get("context_growth_slope", 0.10)
        cost_per_out = data.get("cost_per_output_token", 0.001)

        return {
            # Output/Input ratio: 0.0→0, ≥0.5→100
            "output_input_ratio": _normalize(oi_ratio, 0.0, 0.5),
            # Cache hit rate: 0%→0, ≥50%→100
            "cache_hit_rate": _normalize(cache_rate, 0.0, 0.5),
            # Turns: ≥50→0, ≤5→100 (inverted)
            "turns_to_completion": _normalize(turns, 50, 5),
            # Context growth: ≥10%→0, ≤1%→100 (inverted)
            "context_growth_slope": _normalize(growth, 0.10, 0.01),
            # Cost per output token: ≥$0.001→0, ≤$0.0001→100 (inverted)
            "cost_per_output_token": _normalize(cost_per_out, 0.001, 0.0001),
        }

    def detect_waste_patterns(
        self, events: list[dict[str, Any]]
    ) -> list[str]:
        """Detect waste patterns in a list of session events.

        Patterns:
        1. "Repeated context loading": same large input across >5 consecutive turns
        2. "Excessive back-and-forth": >20 turns with <100 output tokens each
        3. "Context bloat": input tokens growing >10% per turn consistently

        Args:
            events: List of dicts with input_tokens, output_tokens per turn.

        Returns:
            List of detected pattern names.
        """
        patterns: list[str] = []

        if not events:
            return patterns

        # Pattern 1: Repeated context loading
        if len(events) >= 5:
            consecutive_same = 0
            for i in range(1, len(events)):
                prev_input = events[i - 1].get("input_tokens", 0)
                curr_input = events[i].get("input_tokens", 0)
                # "Same" = within 5% of each other and large (>1000)
                if prev_input > 1000 and curr_input > 1000:
                    ratio = min(prev_input, curr_input) / max(prev_input, curr_input)
                    if ratio > 0.95:
                        consecutive_same += 1
                    else:
                        consecutive_same = 0
                else:
                    consecutive_same = 0
                if consecutive_same >= 5:
                    patterns.append("Repeated context loading")
                    break

        # Pattern 2: Excessive back-and-forth
        low_output_turns = sum(
            1 for e in events if e.get("output_tokens", 0) < 100
        )
        if len(events) > 20 and low_output_turns > 20:
            patterns.append("Excessive back-and-forth")

        # Pattern 3: Context bloat
        if len(events) >= 5:
            growth_count = 0
            for i in range(1, len(events)):
                prev = events[i - 1].get("input_tokens", 0)
                curr = events[i].get("input_tokens", 0)
                if prev > 0 and (curr - prev) / prev > 0.10:
                    growth_count += 1
            if growth_count >= len(events) * 0.5:
                patterns.append("Context bloat")

        return patterns

    def generate_recommendations(
        self, score: float, patterns: list[str]
    ) -> list[str]:
        """Generate rule-based suggestions from score and detected patterns.

        Args:
            score: Efficiency score 0-100.
            patterns: List of detected waste pattern names.

        Returns:
            List of recommendation strings.
        """
        recs: list[str] = []

        if score < 30:
            recs.append(
                "Your efficiency score is low. Consider breaking large tasks "
                "into smaller, focused prompts."
            )

        if "Repeated context loading" in patterns:
            recs.append(
                "Avoid re-sending the same large context repeatedly. "
                "Use session continuity or summarize previous context."
            )

        if "Excessive back-and-forth" in patterns:
            recs.append(
                "Too many short exchanges detected. Try providing more "
                "complete instructions in fewer turns."
            )

        if "Context bloat" in patterns:
            recs.append(
                "Context size is growing rapidly each turn. Consider "
                "trimming unnecessary context or starting fresh sessions."
            )

        if score >= 70 and not patterns:
            recs.append("Good efficiency! Keep up the current usage patterns.")

        if not recs:
            recs.append(
                "Review your session patterns for optimization opportunities."
            )

        return recs

    def cross_tool_comparison(
        self, tool_scores: dict[str, list[float]]
    ) -> dict[str, float]:
        """Compute average efficiency scores per tool.

        Args:
            tool_scores: Dict mapping tool name to list of session scores.

        Returns:
            Dict mapping tool name to average score.
        """
        result: dict[str, float] = {}
        for tool, scores in tool_scores.items():
            if scores:
                result[tool] = sum(scores) / len(scores)
            else:
                result[tool] = 0.0
        return result
