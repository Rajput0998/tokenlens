"""Analytics endpoints: timeline, heatmap, tools, models, summary."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tokenlens.api.deps import get_db_session
from tokenlens.api.schemas import (
    HeatmapCell,
    ModelBreakdown,
    SummaryResponse,
    TimelinePoint,
    ToolComparison,
)
from tokenlens.core.models import TokenEventRow

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/timeline", response_model=list[TimelinePoint])
async def get_timeline(
    period: str = Query(default="1h", pattern="^(1h|1d|1w|24h|7d|30d)$"),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    tool: str | None = None,
    model: str | None = None,
    session: AsyncSession = Depends(get_db_session),
):
    """Token usage timeline aggregated by period."""
    now = datetime.now(UTC)
    if date_to is None:
        date_to = now
    if date_from is None:
        if period in ("1h", "24h"):
            date_from = now - timedelta(days=1)
        elif period in ("1d", "7d"):
            date_from = now - timedelta(days=7)
        else:
            date_from = now - timedelta(days=30)

    stmt = select(
        TokenEventRow.timestamp,
        TokenEventRow.tool,
        TokenEventRow.model,
        (TokenEventRow.input_tokens + TokenEventRow.output_tokens).label("tokens"),
        TokenEventRow.cost_usd,
    ).where(
        TokenEventRow.timestamp >= date_from,
        TokenEventRow.timestamp <= date_to,
    )

    if tool:
        stmt = stmt.where(TokenEventRow.tool == tool)
    if model:
        stmt = stmt.where(TokenEventRow.model == model)

    stmt = stmt.order_by(TokenEventRow.timestamp.asc())
    result = await session.execute(stmt)
    rows = result.all()

    # Aggregate by period
    points: list[TimelinePoint] = []
    for row in rows:
        points.append(
            TimelinePoint(
                timestamp=row.timestamp,
                tokens=int(row.tokens),
                cost=float(row.cost_usd),
                tool=row.tool,
                model=row.model,
            )
        )

    return points


@router.get("/heatmap", response_model=list[HeatmapCell])
async def get_heatmap(
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    tool: str | None = None,
    tz_offset_minutes: int = Query(default=0, description="Client timezone offset in minutes (e.g. 330 for IST, -300 for EST)"),
    session: AsyncSession = Depends(get_db_session),
):
    """24x7 heatmap of token usage by day-of-week and hour."""
    now = datetime.now(UTC)
    if date_to is None:
        date_to = now
    if date_from is None:
        date_from = now - timedelta(days=30)

    stmt = select(
        TokenEventRow.timestamp,
        (TokenEventRow.input_tokens + TokenEventRow.output_tokens).label("tokens"),
    ).where(
        TokenEventRow.timestamp >= date_from,
        TokenEventRow.timestamp <= date_to,
    )

    if tool:
        stmt = stmt.where(TokenEventRow.tool == tool)

    result = await session.execute(stmt)
    rows = result.all()

    # Build 7x24 matrix, adjusting timestamps to client's local timezone
    tz_delta = timedelta(minutes=tz_offset_minutes)
    matrix: dict[tuple[int, int], float] = {}
    for row in rows:
        local_time = row.timestamp + tz_delta
        dow = local_time.weekday()  # 0=Monday
        hour = local_time.hour
        key = (dow, hour)
        matrix[key] = matrix.get(key, 0) + int(row.tokens)

    cells = [
        HeatmapCell(day_of_week=dow, hour=hour, value=value)
        for (dow, hour), value in sorted(matrix.items())
    ]
    return cells


@router.get("/tools", response_model=list[ToolComparison])
async def get_tools(
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    session: AsyncSession = Depends(get_db_session),
):
    """Per-tool comparison stats."""
    now = datetime.now(UTC)
    if date_to is None:
        date_to = now
    if date_from is None:
        date_from = now - timedelta(days=30)

    stmt = (
        select(
            TokenEventRow.tool,
            func.sum(
                TokenEventRow.input_tokens + TokenEventRow.output_tokens
            ).label("total_tokens"),
            func.sum(TokenEventRow.cost_usd).label("total_cost"),
            func.count(
                func.distinct(TokenEventRow.session_id)
            ).label("session_count"),
        )
        .where(
            TokenEventRow.timestamp >= date_from,
            TokenEventRow.timestamp <= date_to,
        )
        .group_by(TokenEventRow.tool)
    )

    result = await session.execute(stmt)
    rows = result.all()

    return [
        ToolComparison(
            tool=row.tool,
            total_tokens=int(row.total_tokens or 0),
            total_cost=float(row.total_cost or 0),
            session_count=int(row.session_count or 0),
        )
        for row in rows
    ]


@router.get("/models", response_model=list[ModelBreakdown])
async def get_models(
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    session: AsyncSession = Depends(get_db_session),
):
    """Per-model breakdown stats."""
    now = datetime.now(UTC)
    if date_to is None:
        date_to = now
    if date_from is None:
        date_from = now - timedelta(days=30)

    stmt = (
        select(
            TokenEventRow.model,
            func.sum(
                TokenEventRow.input_tokens + TokenEventRow.output_tokens
            ).label("total_tokens"),
            func.sum(TokenEventRow.cost_usd).label("total_cost"),
            func.count().label("event_count"),
        )
        .where(
            TokenEventRow.timestamp >= date_from,
            TokenEventRow.timestamp <= date_to,
        )
        .group_by(TokenEventRow.model)
    )

    result = await session.execute(stmt)
    rows = result.all()

    return [
        ModelBreakdown(
            model=row.model,
            total_tokens=int(row.total_tokens or 0),
            total_cost=float(row.total_cost or 0),
            event_count=int(row.event_count or 0),
        )
        for row in rows
    ]


@router.get("/summary", response_model=SummaryResponse)
async def get_summary(
    session: AsyncSession = Depends(get_db_session),
):
    """Summary stats for today, week, month, all_time."""
    now = datetime.now(UTC)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())
    month_start = today_start.replace(day=1)

    async def _period_stats(start: datetime | None) -> dict:
        stmt = select(
            func.sum(TokenEventRow.input_tokens + TokenEventRow.output_tokens).label("tokens"),
            func.sum(TokenEventRow.cost_usd).label("cost"),
            func.count().label("events"),
            func.count(func.distinct(TokenEventRow.session_id)).label("sessions"),
        )
        if start:
            stmt = stmt.where(TokenEventRow.timestamp >= start)
        result = await session.execute(stmt)
        row = result.one()
        return {
            "tokens": int(row.tokens or 0),
            "cost": round(float(row.cost or 0), 4),
            "events": int(row.events or 0),
            "sessions": int(row.sessions or 0),
        }

    return SummaryResponse(
        today=await _period_stats(today_start),
        week=await _period_stats(week_start),
        month=await _period_stats(month_start),
        all_time=await _period_stats(None),
    )
