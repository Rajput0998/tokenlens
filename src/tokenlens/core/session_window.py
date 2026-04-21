"""Session window utilities for Claude Code's 5-hour rolling window model.

Claude Code sessions are 5-hour rolling windows. The session start is
determined by scanning events backwards from now to find the earliest
event within a continuous 5-hour block.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from tokenlens.core.models import TokenEventRow

SESSION_DURATION = timedelta(hours=5)

# Plan message limits per session
PLAN_MESSAGE_LIMITS: dict[str, int] = {
    "pro": 250,
    "max5": 1000,
    "max20": 2000,
    "custom": 250,
}


async def find_current_session_start() -> datetime:
    """Find the start of the current Claude Code session by scanning DB events.

    Looks at the last 5 hours of events. If there are events, the session
    started at the earliest event's hour (rounded down). If no events in
    the last 5 hours, returns now rounded to hour (fresh session).
    """
    from tokenlens.core.database import get_session

    now = datetime.now(UTC)
    five_hours_ago = now - SESSION_DURATION

    async with get_session() as db:
        result = await db.execute(
            select(func.min(TokenEventRow.timestamp)).where(
                TokenEventRow.timestamp >= five_hours_ago,
            )
        )
        earliest = result.scalar()

    if earliest is None:
        # No events in last 5 hours — fresh session from now
        return now.replace(minute=0, second=0, microsecond=0)

    # Ensure timezone-aware
    if earliest.tzinfo is None:
        earliest = earliest.replace(tzinfo=UTC)

    # Round down to hour
    return earliest.replace(minute=0, second=0, microsecond=0)


def get_current_session_start(first_event_ts: datetime | None = None) -> datetime:
    """Get session start from a known first event timestamp.

    This is the synchronous version used when the caller already has
    the first event timestamp. Prefer find_current_session_start() for
    accurate results.
    """
    now = datetime.now(UTC)
    if first_event_ts is None:
        return now.replace(minute=0, second=0, microsecond=0)

    if first_event_ts.tzinfo is None:
        first_event_ts = first_event_ts.replace(tzinfo=UTC)

    session_start = first_event_ts.replace(minute=0, second=0, microsecond=0)

    # If session has expired, start fresh
    if now >= session_start + SESSION_DURATION:
        return now.replace(minute=0, second=0, microsecond=0)

    return session_start


def get_session_reset_time(session_start: datetime) -> datetime:
    """Get when the current session expires."""
    return session_start + SESSION_DURATION


async def get_session_stats(session_start: datetime) -> dict:
    """Query token stats within the current session window, including predictions."""
    from tokenlens.core.config import get_effective_daily_token_limit, get_plan_type
    from tokenlens.core.database import get_session

    session_end = session_start + SESSION_DURATION
    now = datetime.now(UTC)

    async with get_session() as db:
        result = await db.execute(
            select(
                func.sum(TokenEventRow.input_tokens + TokenEventRow.output_tokens).label("tokens"),
                func.sum(TokenEventRow.cost_usd).label("cost"),
                func.count(TokenEventRow.id).label("messages"),
                func.min(TokenEventRow.timestamp).label("first_event"),
            ).where(
                TokenEventRow.timestamp >= session_start,
                TokenEventRow.timestamp < session_end,
            )
        )
        row = result.one()

    session_tokens = int(row.tokens or 0)
    session_cost = round(float(row.cost or 0), 4)
    session_messages = int(row.messages or 0)

    # Calculate rates and predictions
    elapsed_minutes = max((now - session_start).total_seconds() / 60, 1)

    token_limit = get_effective_daily_token_limit()
    tokens_remaining = max(token_limit - session_tokens, 0)

    # Burn rate (tokens per minute)
    burn_rate_per_min = session_tokens / elapsed_minutes if elapsed_minutes > 0 else 0

    # Cost rate ($ per minute)
    cost_rate_per_min = session_cost / elapsed_minutes if elapsed_minutes > 0 else 0

    # Prediction: when will tokens run out?
    tokens_exhaust_time = None
    if burn_rate_per_min > 0 and tokens_remaining > 0:
        minutes_to_exhaust = tokens_remaining / burn_rate_per_min
        exhaust_dt = now + timedelta(minutes=minutes_to_exhaust)
        # Only show if within session window
        if exhaust_dt < session_end:
            tokens_exhaust_time = exhaust_dt.isoformat()

    return {
        "session_tokens": session_tokens,
        "session_cost": session_cost,
        "session_messages": session_messages,
        "session_start": session_start.isoformat(),
        "session_reset": session_end.isoformat(),
        "first_event": row.first_event.isoformat() if row.first_event else None,
        "token_limit": token_limit,
        "plan_type": get_plan_type(),
        "burn_rate_per_min": round(burn_rate_per_min, 1),
        "cost_rate_per_min": round(cost_rate_per_min, 4),
        "tokens_exhaust_at": tokens_exhaust_time,
    }
