"""Prediction endpoints: burnrate, limit, budget, whatif, profile."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tokenlens.api.deps import get_db_session
from tokenlens.api.schemas import (
    BudgetProjection,
    BurnRateForecastResponse,
    LimitPrediction,
    WhatIfRequest,
    WhatIfResponse,
)
from tokenlens.core.config import settings
from tokenlens.core.models import TokenEventRow

router = APIRouter(prefix="/predictions", tags=["predictions"])


@router.get("/burnrate", response_model=BurnRateForecastResponse)
async def get_burnrate(
    tool: str | None = None,
    session: AsyncSession = Depends(get_db_session),
):
    """Get burn rate forecast based on current session window."""
    from tokenlens.core.session_window import (
        SESSION_DURATION,
        get_current_session_start,
    )

    now = datetime.now(UTC)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Find earliest event today to determine session start
    first_event_stmt = select(func.min(TokenEventRow.timestamp)).where(
        TokenEventRow.timestamp >= today_start
    )
    first_event_result = await session.execute(first_event_stmt)
    first_event_ts = first_event_result.scalar()

    session_start = get_current_session_start(first_event_ts)
    session_end = session_start + SESSION_DURATION

    stmt = select(
        TokenEventRow.timestamp,
        (TokenEventRow.input_tokens + TokenEventRow.output_tokens).label("tokens"),
    ).where(
        TokenEventRow.timestamp >= session_start,
        TokenEventRow.timestamp < session_end,
    )

    if tool:
        stmt = stmt.where(TokenEventRow.tool == tool)

    stmt = stmt.order_by(TokenEventRow.timestamp.asc())
    result = await session.execute(stmt)
    rows = result.all()

    if not rows:
        return BurnRateForecastResponse(status="collecting_data", forecast=[])

    # Calculate rate from session start
    total_tokens = sum(int(r.tokens) for r in rows)
    hours_elapsed = max((now - session_start).total_seconds() / 3600, 0.1)
    hourly_rate = total_tokens / hours_elapsed

    forecast = []
    base_hour = now.replace(minute=0, second=0, microsecond=0)
    # Forecast remaining hours in session window
    hours_remaining = max((session_end - now).total_seconds() / 3600, 0)
    forecast_hours = min(int(hours_remaining) + 1, 24)
    for h in range(forecast_hours):
        hour = base_hour + timedelta(hours=h + 1)
        forecast.append({
            "hour": hour.isoformat(),
            "predicted_tokens": hourly_rate,
            "lower_80": hourly_rate * 0.7,
            "upper_80": hourly_rate * 1.3,
        })

    return BurnRateForecastResponse(
        model_type="linear",
        tool=tool,
        forecast=forecast,
    )


@router.get("/limit", response_model=LimitPrediction)
async def get_limit_prediction(
    session: AsyncSession = Depends(get_db_session),
):
    """Predict if session token limit will be hit."""
    from tokenlens.core.config import get_effective_daily_token_limit
    from tokenlens.core.session_window import (
        SESSION_DURATION,
        get_current_session_start,
    )

    now = datetime.now(UTC)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    daily_limit = get_effective_daily_token_limit()

    # Find earliest event today to determine session start
    first_event_stmt = select(func.min(TokenEventRow.timestamp)).where(
        TokenEventRow.timestamp >= today_start
    )
    first_event_result = await session.execute(first_event_stmt)
    first_event_ts = first_event_result.scalar()

    session_start = get_current_session_start(first_event_ts)
    session_end = session_start + SESSION_DURATION

    # Query usage within the session window
    stmt = select(
        func.sum(TokenEventRow.input_tokens + TokenEventRow.output_tokens).label("total"),
    ).where(
        TokenEventRow.timestamp >= session_start,
        TokenEventRow.timestamp < session_end,
    )

    result = await session.execute(stmt)
    current_usage = int(result.scalar() or 0)

    hours_elapsed = max((now - session_start).total_seconds() / 3600, 0.1)
    hourly_rate = current_usage / hours_elapsed
    hours_remaining = max((session_end - now).total_seconds() / 3600, 0)
    projected_total = current_usage + hourly_rate * hours_remaining

    will_hit = projected_total > daily_limit
    estimated_time = None
    if will_hit and hourly_rate > 0:
        tokens_remaining = daily_limit - current_usage
        hours_to_limit = tokens_remaining / hourly_rate
        if hours_to_limit > 0:
            estimated_time = now + timedelta(hours=hours_to_limit)

    return LimitPrediction(
        will_hit_limit=will_hit,
        estimated_time=estimated_time,
        current_usage=current_usage,
        daily_limit=daily_limit,
    )


@router.get("/budget", response_model=BudgetProjection)
async def get_budget_projection(
    session: AsyncSession = Depends(get_db_session),
):
    """Project monthly cost from current usage."""
    now = datetime.now(UTC)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    monthly_budget = settings.get("alerts.thresholds.monthly_cost_budget", 50.0)

    stmt = select(
        func.sum(TokenEventRow.cost_usd).label("cost"),
        func.sum(TokenEventRow.input_tokens + TokenEventRow.output_tokens).label("tokens"),
    ).where(TokenEventRow.timestamp >= month_start)

    result = await session.execute(stmt)
    row = result.one()
    spent_so_far = float(row.cost or 0)
    tokens_so_far = float(row.tokens or 0)

    days_elapsed = max((now - month_start).days, 1)
    daily_cost = spent_so_far / days_elapsed
    daily_tokens = tokens_so_far / days_elapsed
    projected_monthly = daily_cost * 30

    remaining_days = 30 - days_elapsed
    recommended_daily = 0.0
    if remaining_days > 0:
        remaining_budget = monthly_budget - spent_so_far
        recommended_daily = max(0.0, remaining_budget / remaining_days)

    return BudgetProjection(
        projected_monthly_cost=round(projected_monthly, 4),
        daily_cost=round(daily_cost, 4),
        daily_tokens=round(daily_tokens, 2),
        monthly_budget=monthly_budget,
        is_over_budget=projected_monthly > monthly_budget * 1.10,
        recommended_daily_spend=round(recommended_daily, 4),
    )


@router.post("/whatif", response_model=WhatIfResponse)
async def what_if(
    request: WhatIfRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """What-if scenario simulation."""
    from tokenlens.ml.budget import BudgetForecaster

    forecaster = BudgetForecaster()

    # Get current baseline
    now = datetime.now(UTC)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    stmt = select(
        func.sum(TokenEventRow.cost_usd).label("cost"),
    ).where(TokenEventRow.timestamp >= month_start)

    result = await session.execute(stmt)
    spent_so_far = float(result.scalar() or 0)
    days_elapsed = max((now - month_start).days, 1)
    baseline_daily = spent_so_far / days_elapsed
    baseline_monthly = baseline_daily * 30

    # Simulate
    scenario = {
        "context_size": request.context_size,
        "model_switch": request.model_switch,
        "usage_pct_change": request.usage_pct_change,
    }
    projected = forecaster.what_if_simulate(
        baseline_daily_cost=baseline_daily,
        scenario=scenario,
    )

    projected_monthly = projected["projected_monthly_cost"]
    cost_diff = projected_monthly - baseline_monthly
    pct_change = (cost_diff / baseline_monthly * 100) if baseline_monthly > 0 else 0.0

    return WhatIfResponse(
        baseline_monthly_cost=round(baseline_monthly, 4),
        projected_monthly_cost=round(projected_monthly, 4),
        cost_difference=round(cost_diff, 4),
        pct_change=round(pct_change, 2),
        scenario=scenario,
    )


@router.get("/profile")
async def get_profile(
    tz_offset_minutes: int = Query(default=0, description="Client timezone offset in minutes (e.g. 330 for IST, -300 for EST)"),
    session: AsyncSession = Depends(get_db_session),
):
    """Get behavioral profile (archetype)."""
    now = datetime.now(UTC)
    week_ago = now - timedelta(days=7)

    stmt = select(
        TokenEventRow.timestamp,
        (TokenEventRow.input_tokens + TokenEventRow.output_tokens).label("tokens"),
    ).where(TokenEventRow.timestamp >= week_ago)

    result = await session.execute(stmt)
    rows = result.all()

    if not rows:
        return {"archetype": "Unknown", "reason": "Insufficient data"}

    # Determine peak hour in client's local timezone
    tz_delta = timedelta(minutes=tz_offset_minutes)
    hour_totals: dict[int, int] = {}
    for row in rows:
        local_time = row.timestamp + tz_delta
        h = local_time.hour
        hour_totals[h] = hour_totals.get(h, 0) + int(row.tokens)

    peak_hour = max(hour_totals, key=hour_totals.get) if hour_totals else 12

    from tokenlens.ml.profiler import BehavioralProfiler

    archetype = BehavioralProfiler.classify_archetype(float(peak_hour))

    return {
        "archetype": archetype,
        "peak_hour": peak_hour,
        "total_tokens_week": sum(int(r.tokens) for r in rows),
    }
