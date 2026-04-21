"""Kiro steering file auto-generation.

Generates .kiro/steering/token-budget.md with usage, burn rate, tips, and cost.
Triggered by MLTaskRunner.run_due_tasks() every 30 minutes.
Configurable via [integrations.kiro] in config.toml.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import structlog

from tokenlens.core.config import settings

logger = structlog.get_logger()

_STEERING_UPDATE_INTERVAL = timedelta(minutes=30)
_KEY_LAST_STEERING_UPDATE = "integrations.kiro.last_steering_update"


def is_kiro_integration_enabled() -> bool:
    """Check if Kiro integration is enabled in config."""
    return bool(settings.get("integrations.kiro.enabled", False))


def get_steering_update_interval() -> timedelta:
    """Get the steering update interval from config."""
    minutes = int(settings.get("integrations.kiro.steering_update_interval_minutes", 30))
    return timedelta(minutes=minutes)


async def should_update_steering(last_updated: datetime | None) -> bool:
    """Check if steering file update is due."""
    if not is_kiro_integration_enabled():
        return False
    if last_updated is None:
        return True
    interval = get_steering_update_interval()
    return (datetime.now(UTC) - last_updated) >= interval


async def generate_steering_file() -> None:
    """Generate the .kiro/steering/token-budget.md file."""
    data = await _gather_steering_data()
    content = _render_steering_content(data)
    _write_steering_file(content)
    logger.info("Kiro steering file updated.")


async def _gather_steering_data() -> dict[str, Any]:
    """Gather data for the steering file."""
    from sqlalchemy import func, select

    from tokenlens.core.database import get_session
    from tokenlens.core.models import TokenEventRow
    from tokenlens.core.utils import calculate_burn_rate

    now = datetime.now(UTC)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)

    data: dict[str, Any] = {
        "timestamp": now.isoformat(),
        "today_tokens": 0,
        "today_cost": 0.0,
        "burn_rate": "slow",
        "weekly_tokens": 0,
        "weekly_cost": 0.0,
        "daily_limit": None,
        "monthly_budget": None,
        "limit_pct": 0,
        "tips": [],
    }

    try:
        async with get_session() as db:
            # Today's usage
            result = await db.execute(
                select(
                    func.sum(TokenEventRow.input_tokens + TokenEventRow.output_tokens).label(
                        "total"
                    ),
                    func.sum(TokenEventRow.cost_usd).label("cost"),
                )
                .where(TokenEventRow.timestamp >= today_start)
            )
            row = result.one_or_none()
            if row and row.total:
                data["today_tokens"] = int(row.total)
                data["today_cost"] = float(row.cost or 0)

            # Weekly usage
            result = await db.execute(
                select(
                    func.sum(TokenEventRow.input_tokens + TokenEventRow.output_tokens).label(
                        "total"
                    ),
                    func.sum(TokenEventRow.cost_usd).label("cost"),
                )
                .where(TokenEventRow.timestamp >= week_ago)
            )
            row = result.one_or_none()
            if row and row.total:
                data["weekly_tokens"] = int(row.total)
                data["weekly_cost"] = float(row.cost or 0)

        # Burn rate
        hours_elapsed = max((now - today_start).total_seconds() / 3600, 0.1)
        data["burn_rate"] = calculate_burn_rate(data["today_tokens"], hours_elapsed)

        # Limits
        daily_limit = settings.get("alerts.thresholds.daily_token_limit", None)
        if daily_limit:
            data["daily_limit"] = int(daily_limit)
            data["limit_pct"] = int(data["today_tokens"] / int(daily_limit) * 100)

        monthly_budget = settings.get("alerts.thresholds.monthly_cost_budget", None)
        if monthly_budget:
            data["monthly_budget"] = float(monthly_budget)

        # Tips
        data["tips"] = _generate_tips(data)

    except Exception:
        logger.warning("Failed to gather steering data.", exc_info=True)

    return data


def _generate_tips(data: dict[str, Any]) -> list[str]:
    """Generate contextual tips based on current usage."""
    tips: list[str] = []

    if data["burn_rate"] == "critical":
        tips.append("⚠️ Token burn rate is critical. Consider pausing non-essential tasks.")
    elif data["burn_rate"] == "fast":
        tips.append("Token burn rate is fast. Monitor closely.")

    if data["limit_pct"] > 75:
        tips.append(f"You've used {data['limit_pct']}% of your daily token limit.")

    if data["today_tokens"] > 0 and data["weekly_tokens"] > 0:
        daily_avg = data["weekly_tokens"] / 7
        if data["today_tokens"] > daily_avg * 1.5:
            tips.append("Today's usage is 50%+ above your weekly average.")

    if not tips:
        tips.append("Usage is within normal parameters.")

    return tips


def _render_steering_content(data: dict[str, Any]) -> str:
    """Render the steering file markdown content."""
    lines = [
        "# Token Budget Status",
        "",
        f"*Auto-generated by TokenLens at {data['timestamp']}*",
        "",
        "## Current Usage",
        "",
        f"- **Today:** {data['today_tokens']:,} tokens (${data['today_cost']:.2f})",
        f"- **This week:** {data['weekly_tokens']:,} tokens (${data['weekly_cost']:.2f})",
        f"- **Burn rate:** {data['burn_rate']}",
    ]

    if data["daily_limit"]:
        lines.append(
            f"- **Daily limit:** {data['daily_limit']:,} tokens ({data['limit_pct']}% used)"
        )

    if data["monthly_budget"]:
        lines.append(f"- **Monthly budget:** ${data['monthly_budget']:.2f}")

    lines.extend(["", "## Tips", ""])
    for tip in data["tips"]:
        lines.append(f"- {tip}")

    lines.extend([
        "",
        "## Guidelines",
        "",
        "- Break large tasks into smaller, focused prompts to reduce context accumulation",
        "- Start fresh sessions when switching topics to avoid context bloat",
        "- Use specific file references instead of including entire files in context",
        "- Consider using lighter models for simple tasks (formatting, renaming, etc.)",
        "",
    ])

    return "\n".join(lines)


def _write_steering_file(content: str) -> None:
    """Write the steering file to .kiro/steering/token-budget.md."""
    # Write to the project's .kiro directory (current working directory)
    kiro_dir = Path.cwd() / ".kiro" / "steering"
    kiro_dir.mkdir(parents=True, exist_ok=True)
    steering_path = kiro_dir / "token-budget.md"
    steering_path.write_text(content)
