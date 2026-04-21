"""Efficiency endpoints: sessions, recommendations, trends."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tokenlens.api.deps import get_db_session
from tokenlens.api.schemas import (
    EfficiencyTrend,
    PaginatedResponse,
    PaginationMeta,
    Recommendation,
    SessionEfficiency,
)
from tokenlens.core.models import SessionRow

router = APIRouter(prefix="/efficiency", tags=["efficiency"])


@router.get("/sessions")
async def list_efficiency_sessions(
    tool: str | None = None,
    min_score: float | None = None,
    max_score: float | None = None,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_db_session),
) -> PaginatedResponse[SessionEfficiency]:
    """List sessions with efficiency scores."""
    stmt = select(SessionRow).where(SessionRow.efficiency_score.isnot(None))
    count_stmt = (
        select(func.count())
        .select_from(SessionRow)
        .where(SessionRow.efficiency_score.isnot(None))
    )

    if tool:
        stmt = stmt.where(SessionRow.tool == tool)
        count_stmt = count_stmt.where(SessionRow.tool == tool)
    if min_score is not None:
        stmt = stmt.where(SessionRow.efficiency_score >= min_score)
        count_stmt = count_stmt.where(SessionRow.efficiency_score >= min_score)
    if max_score is not None:
        stmt = stmt.where(SessionRow.efficiency_score <= max_score)
        count_stmt = count_stmt.where(SessionRow.efficiency_score <= max_score)

    total_result = await session.execute(count_stmt)
    total = total_result.scalar() or 0

    stmt = stmt.order_by(SessionRow.start_time.desc())
    offset = (page - 1) * per_page
    stmt = stmt.offset(offset).limit(per_page)

    result = await session.execute(stmt)
    rows = result.scalars().all()

    data = [
        SessionEfficiency(
            session_id=row.id,
            tool=row.tool,
            score=row.efficiency_score or 0.0,
            start_time=row.start_time,
            end_time=row.end_time,
            turn_count=row.turn_count,
            total_tokens=row.total_input_tokens + row.total_output_tokens,
        )
        for row in rows
    ]

    total_pages = (total + per_page - 1) // per_page if total > 0 else 0

    return PaginatedResponse(
        data=data,
        meta=PaginationMeta(
            page=page,
            per_page=per_page,
            total=total,
            total_pages=total_pages,
        ),
    )


@router.get("/recommendations", response_model=list[Recommendation])
async def get_recommendations(
    session: AsyncSession = Depends(get_db_session),
):
    """Get top efficiency recommendations based on recent sessions."""
    # Get recent sessions with scores
    stmt = (
        select(SessionRow)
        .where(SessionRow.efficiency_score.isnot(None))
        .order_by(SessionRow.start_time.desc())
        .limit(20)
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()

    if not rows:
        return [
            Recommendation(
                message="Start using TokenLens to get personalized recommendations."
            )
        ]

    scores = [r.efficiency_score for r in rows if r.efficiency_score is not None]
    avg_score = sum(scores) / len(scores) if scores else 50.0

    from tokenlens.ml.efficiency import EfficiencyEngine

    engine = EfficiencyEngine()
    recs = engine.generate_recommendations(avg_score, [])

    return [Recommendation(message=r) for r in recs[:5]]


@router.get("/trends", response_model=list[EfficiencyTrend])
async def get_trends(
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    tool: str | None = None,
    session: AsyncSession = Depends(get_db_session),
):
    """Efficiency score trends over time."""
    now = datetime.now(UTC)
    if date_to is None:
        date_to = now
    if date_from is None:
        date_from = now - timedelta(days=30)

    stmt = select(SessionRow).where(
        SessionRow.start_time >= date_from,
        SessionRow.start_time <= date_to,
        SessionRow.efficiency_score.isnot(None),
    )

    if tool:
        stmt = stmt.where(SessionRow.tool == tool)

    stmt = stmt.order_by(SessionRow.start_time.asc())
    result = await session.execute(stmt)
    rows = result.scalars().all()

    # Group by date
    daily: dict[str, list[float]] = {}
    for row in rows:
        date_key = row.start_time.strftime("%Y-%m-%d")
        if date_key not in daily:
            daily[date_key] = []
        if row.efficiency_score is not None:
            daily[date_key].append(row.efficiency_score)

    trends = [
        EfficiencyTrend(
            date=datetime.strptime(date_key, "%Y-%m-%d").replace(tzinfo=UTC),
            avg_score=sum(scores) / len(scores),
            session_count=len(scores),
        )
        for date_key, scores in daily.items()
    ]

    return trends
