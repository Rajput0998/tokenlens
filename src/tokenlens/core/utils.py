"""Reusable utility functions for TokenLens.

Used by CLI status, API status endpoint, and WebSocket live push.
"""

from __future__ import annotations


def calculate_burn_rate(tokens_today: int, hours_elapsed: float) -> str:
    """Classify token burn rate based on tokens per hour.

    Args:
        tokens_today: Total tokens consumed today.
        hours_elapsed: Hours elapsed since start of day (or tracking period).

    Returns:
        One of: "slow" (<1K/hr), "normal" (1K-5K/hr),
        "fast" (5K-10K/hr), "critical" (>10K/hr).
    """
    if hours_elapsed <= 0:
        return "slow"

    rate = tokens_today / hours_elapsed

    if rate < 1_000:
        return "slow"
    if rate < 5_000:
        return "normal"
    if rate < 10_000:
        return "fast"
    return "critical"
