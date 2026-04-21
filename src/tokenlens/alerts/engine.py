"""Alert engine: threshold triggers, anomaly alerts, predictive alerts, dedup."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any


class AlertEngine:
    """Manages alert generation with deduplication.

    Threshold triggers at 50/75/90/100% of daily token limit and monthly cost budget.
    Dedup: don't send same threshold twice per billing period.
    """

    def __init__(self) -> None:
        self._sent_alerts: dict[str, datetime] = {}  # alert_key -> last_sent_time
        self._dedup_window = timedelta(hours=24)  # Don't repeat within 24h

    def _is_duplicate(self, alert_key: str) -> bool:
        """Check if this alert was already sent within the dedup window."""
        last_sent = self._sent_alerts.get(alert_key)
        if last_sent is None:
            return False
        return (datetime.now(UTC) - last_sent) < self._dedup_window

    def _mark_sent(self, alert_key: str) -> None:
        """Record that an alert was sent."""
        self._sent_alerts[alert_key] = datetime.now(UTC)

    def check_thresholds(
        self,
        current_tokens: int,
        daily_limit: int | None = None,
        current_cost: float = 0.0,
        monthly_budget: float | None = None,
        days_in_month: int = 30,
        plan_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Check token and cost thresholds, return new alerts (deduped).

        Args:
            current_tokens: Tokens used today.
            daily_limit: Daily token limit. When ``None``, resolved from the
                configured plan via ``get_effective_daily_token_limit()``.
            current_cost: Cost spent this month.
            monthly_budget: Monthly cost budget. When ``None``, resolved from
                the configured plan via ``get_effective_monthly_cost_budget()``.
            days_in_month: Days in current billing period.
            plan_type: Subscription plan identifier (e.g. ``"max5"``). When
                ``None``, resolved via ``get_plan_type()``.

        Returns:
            List of alert dicts to dispatch.
        """
        from tokenlens.core.config import (
            get_effective_daily_token_limit,
            get_effective_monthly_cost_budget,
            get_plan_type,
        )

        if daily_limit is None:
            daily_limit = get_effective_daily_token_limit()
        if monthly_budget is None:
            monthly_budget = get_effective_monthly_cost_budget()
        if plan_type is None:
            plan_type = get_plan_type()

        alerts: list[dict[str, Any]] = []
        now = datetime.now(UTC)

        # Token thresholds
        if daily_limit > 0:
            pct = (current_tokens / daily_limit) * 100
            for threshold in [50, 75, 90, 100]:
                if pct >= threshold:
                    key = f"token_threshold_{threshold}"
                    if not self._is_duplicate(key):
                        severity = "critical" if threshold >= 90 else "warning"
                        alerts.append({
                            "type": "alert",
                            "severity": severity,
                            "title": f"{threshold}% of daily limit reached",
                            "message": (
                                f"You've used {current_tokens:,} of "
                                f"{daily_limit:,} daily tokens "
                                f"({plan_type} plan)."
                            ),
                            "timestamp": now.isoformat(),
                            "threshold_pct": threshold,
                            "category": "token_threshold",
                        })
                        self._mark_sent(key)

        # Cost thresholds
        if monthly_budget > 0:
            cost_pct = (current_cost / monthly_budget) * 100
            for threshold in [50, 75, 90, 100]:
                if cost_pct >= threshold:
                    key = f"cost_threshold_{threshold}"
                    if not self._is_duplicate(key):
                        severity = "critical" if threshold >= 90 else "warning"
                        alerts.append({
                            "type": "alert",
                            "severity": severity,
                            "title": f"{threshold}% of monthly budget reached",
                            "message": (
                                f"You've spent ${current_cost:.2f} of "
                                f"${monthly_budget:.2f} monthly budget "
                                f"({plan_type} plan)."
                            ),
                            "timestamp": now.isoformat(),
                            "threshold_pct": threshold,
                            "category": "cost_threshold",
                        })
                        self._mark_sent(key)

        return alerts

    def check_anomaly(self, anomaly_result: dict[str, Any]) -> list[dict[str, Any]]:
        """Generate alert from anomaly detection result.

        Args:
            anomaly_result: Output from AnomalyDetector.detect().

        Returns:
            List of alert dicts (0 or 1).
        """
        if not anomaly_result.get("is_anomaly"):
            return []

        key = f"anomaly_{anomaly_result.get('classification', 'unknown')}"
        if self._is_duplicate(key):
            return []

        self._mark_sent(key)
        now = datetime.now(UTC)

        return [{
            "type": "alert",
            "severity": anomaly_result.get("severity", "warning"),
            "title": f"Anomaly detected: {anomaly_result.get('classification', 'Unknown')}",
            "message": anomaly_result.get("description", "Unusual usage pattern detected."),
            "timestamp": now.isoformat(),
            "category": "anomaly",
            "score": anomaly_result.get("score", 0.0),
        }]

    def check_predictive(
        self,
        hours_to_limit: float | None,
        threshold_hours: float = 2.0,
    ) -> list[dict[str, Any]]:
        """Generate predictive alert if limit hit is projected within threshold_hours.

        Args:
            hours_to_limit: Estimated hours until daily limit is hit (None = won't hit).
            threshold_hours: Alert if limit hit within this many hours.

        Returns:
            List of alert dicts (0 or 1).
        """
        if hours_to_limit is None or hours_to_limit > threshold_hours:
            return []

        key = "predictive_limit"
        if self._is_duplicate(key):
            return []

        self._mark_sent(key)
        now = datetime.now(UTC)

        return [{
            "type": "alert",
            "severity": "warning",
            "title": "Daily limit projected within 2 hours",
            "message": (
                f"At current burn rate, you'll hit your daily token limit "
                f"in approximately {hours_to_limit:.1f} hours."
            ),
            "timestamp": now.isoformat(),
            "category": "predictive",
            "hours_to_limit": hours_to_limit,
        }]

    def check_model_switch(
        self,
        current_model: str | None,
        previous_model: str | None,
        session_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Detect model switch mid-session.

        Args:
            current_model: Model used in latest event.
            previous_model: Model used in previous event of same session.
            session_id: Session ID for context.

        Returns:
            List of alert dicts (0 or 1).
        """
        if not current_model or not previous_model:
            return []
        if current_model == previous_model:
            return []

        key = f"model_switch_{session_id or 'unknown'}"
        if self._is_duplicate(key):
            return []

        self._mark_sent(key)
        now = datetime.now(UTC)

        return [{
            "type": "alert",
            "severity": "warning",
            "title": "Model switch detected",
            "message": (
                f"Model changed from {previous_model} to {current_model} "
                f"mid-session."
            ),
            "timestamp": now.isoformat(),
            "category": "model_switch",
            "previous_model": previous_model,
            "current_model": current_model,
            "session_id": session_id,
        }]

    def reset_dedup(self) -> None:
        """Clear dedup state (e.g. at start of new billing period)."""
        self._sent_alerts.clear()
