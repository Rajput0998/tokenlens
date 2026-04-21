"""Budget forecaster — derives cost from token forecast × pricing table.

No separate ML model for cost. Multiplies token predictions by per-model pricing.
What-if simulator deferred to Phase 3.
"""

from __future__ import annotations

from typing import Any


class BudgetForecaster:
    """Projects monthly cost from token forecasts and pricing data."""

    def project_monthly_cost(
        self,
        token_forecast: list[dict[str, Any]],
        pricing_table: dict[str, dict[str, float]],
        model: str = "claude-sonnet-4",
    ) -> dict[str, Any]:
        """Multiply token predictions by per-model pricing.

        Args:
            token_forecast: List of hourly forecast dicts with 'predicted_tokens'.
            pricing_table: Model pricing dict,
                e.g. {"claude-sonnet-4": {"input": 3.0, "output": 15.0}}.
            model: Model name to look up pricing.

        Returns:
            Dict with projected_monthly_cost and per_hour_breakdown.
        """
        pricing = pricing_table.get(model, {"input": 3.0, "output": 15.0})
        # Assume 50/50 input/output split for forecasted tokens
        input_price_per_token = pricing["input"] / 1_000_000
        output_price_per_token = pricing["output"] / 1_000_000
        avg_price_per_token = (input_price_per_token + output_price_per_token) / 2

        daily_tokens = sum(f.get("predicted_tokens", 0) for f in token_forecast)
        daily_cost = daily_tokens * avg_price_per_token
        projected_monthly = daily_cost * 30

        return {
            "projected_monthly_cost": projected_monthly,
            "daily_cost": daily_cost,
            "daily_tokens": daily_tokens,
        }

    def compute_daily_recommendation(
        self,
        monthly_budget: float,
        spent_so_far: float,
        remaining_days: int,
    ) -> float:
        """Compute recommended daily spend: (budget - spent) / remaining_days.

        Returns 0.0 if remaining_days <= 0 or budget already exceeded.
        """
        if remaining_days <= 0:
            return 0.0
        remaining = monthly_budget - spent_so_far
        if remaining <= 0:
            return 0.0
        return remaining / remaining_days

    def is_over_budget(
        self,
        projected_monthly_cost: float,
        monthly_budget: float,
    ) -> bool:
        """Return True if projected cost exceeds budget by more than 10%."""
        return projected_monthly_cost > monthly_budget * 1.10

    def what_if_simulate(
        self,
        baseline_daily_cost: float,
        scenario: dict[str, Any],
    ) -> dict[str, Any]:
        """Simulate a what-if scenario and return projected monthly cost.

        Args:
            baseline_daily_cost: Current average daily cost in USD.
            scenario: Dict with optional keys:
                - context_size: float multiplier (e.g. 1.5 = 50% more context → more input tokens)
                - model_switch: str target model name (affects pricing)
                - usage_pct_change: float (e.g. -0.2 = 20% less usage)

        Returns:
            Dict with projected_monthly_cost and breakdown.
        """
        multiplier = 1.0

        # Context size affects input tokens (roughly proportional to cost)
        context_size = scenario.get("context_size")
        if context_size is not None and context_size > 0:
            # Context size multiplier affects ~60% of cost (input portion)
            multiplier *= 0.4 + 0.6 * context_size

        # Usage percentage change
        usage_pct = scenario.get("usage_pct_change")
        if usage_pct is not None:
            multiplier *= 1.0 + usage_pct

        # Model switch — use pricing ratio
        model_switch = scenario.get("model_switch")
        if model_switch:
            from tokenlens.core.config import get_pricing_table

            pricing = get_pricing_table()
            # Default model pricing (claude-sonnet-4)
            default_avg = (3.0 + 15.0) / 2  # $9/MTok average
            target_pricing = pricing.get(model_switch, {})
            if target_pricing:
                target_avg = (
                    target_pricing.get("input", 3.0) + target_pricing.get("output", 15.0)
                ) / 2
                multiplier *= target_avg / default_avg

        projected_daily = baseline_daily_cost * multiplier
        projected_monthly = projected_daily * 30

        return {
            "projected_monthly_cost": projected_monthly,
            "projected_daily_cost": projected_daily,
            "multiplier": multiplier,
        }
