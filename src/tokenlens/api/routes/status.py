"""GET /api/v1/status — current token usage summary."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tokenlens.api.deps import get_db_session
from tokenlens.api.schemas import StatusResponse
from tokenlens.core.models import SessionRow, TokenEventRow
from tokenlens.core.utils import calculate_burn_rate

router = APIRouter(tags=["status"])


@router.get("/status", response_model=StatusResponse)
async def get_status(session: AsyncSession = Depends(get_db_session)):
    """Return current day token usage summary."""
    now = datetime.now(UTC)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Today's tokens per tool
    stmt = (
        select(
            TokenEventRow.tool,
            func.sum(TokenEventRow.input_tokens + TokenEventRow.output_tokens).label("total"),
            func.sum(TokenEventRow.cost_usd).label("cost"),
        )
        .where(TokenEventRow.timestamp >= today_start)
        .group_by(TokenEventRow.tool)
    )
    result = await session.execute(stmt)
    rows = result.all()

    per_tool: dict[str, int] = {}
    today_tokens = 0
    cost_today = 0.0
    for row in rows:
        tokens = int(row.total or 0)
        per_tool[row.tool] = tokens
        today_tokens += tokens
        cost_today += float(row.cost or 0.0)

    # Active sessions (sessions that ended within last 15 minutes)
    active_cutoff = now - timedelta(minutes=15)
    active_stmt = (
        select(func.count())
        .select_from(SessionRow)
        .where(SessionRow.end_time >= active_cutoff)
    )
    active_result = await session.execute(active_stmt)
    active_sessions = active_result.scalar() or 0

    # Burn rate
    hours_elapsed = (now - today_start).total_seconds() / 3600
    burn_rate = calculate_burn_rate(today_tokens, hours_elapsed)

    # Last heartbeat (most recent event timestamp)
    heartbeat_stmt = select(func.max(TokenEventRow.timestamp))
    heartbeat_result = await session.execute(heartbeat_stmt)
    last_heartbeat = heartbeat_result.scalar()

    # Determine daemon health
    daemon_healthy = False
    if last_heartbeat is not None:
        hb = last_heartbeat
        if hb.tzinfo is None:
            hb = hb.replace(tzinfo=UTC)
        daemon_healthy = (now - hb).total_seconds() < 300

    # Session window stats
    from tokenlens.core.session_window import find_current_session_start, get_session_stats

    session_start = await find_current_session_start()
    session_stats = await get_session_stats(session_start)

    return StatusResponse(
        today_tokens=today_tokens,
        per_tool=per_tool,
        active_sessions=active_sessions,
        burn_rate=burn_rate,
        cost_today=round(cost_today, 4),
        daemon_healthy=daemon_healthy,
        last_heartbeat=last_heartbeat,
        session=session_stats,
    )
