"""GET /api/v1/sessions — session listing and detail."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tokenlens.api.deps import get_db_session
from tokenlens.api.schemas import (
    PaginatedResponse,
    PaginationMeta,
    SessionDetailResponse,
    SessionResponse,
    TokenEventResponse,
)
from tokenlens.core.models import SessionRow, TokenEventRow

router = APIRouter(tags=["sessions"])


@router.get("/sessions")
async def list_sessions(
    tool: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_db_session),
) -> PaginatedResponse[SessionResponse]:
    """List sessions with pagination and filtering."""
    stmt = select(SessionRow)
    count_stmt = select(func.count()).select_from(SessionRow)

    if tool:
        stmt = stmt.where(SessionRow.tool == tool)
        count_stmt = count_stmt.where(SessionRow.tool == tool)
    if date_from:
        stmt = stmt.where(SessionRow.start_time >= date_from)
        count_stmt = count_stmt.where(SessionRow.start_time >= date_from)
    if date_to:
        stmt = stmt.where(SessionRow.end_time <= date_to)
        count_stmt = count_stmt.where(SessionRow.end_time <= date_to)

    total_result = await session.execute(count_stmt)
    total = total_result.scalar() or 0

    stmt = stmt.order_by(SessionRow.start_time.desc())
    offset = (page - 1) * per_page
    stmt = stmt.offset(offset).limit(per_page)

    result = await session.execute(stmt)
    rows = result.scalars().all()

    data = [
        SessionResponse(
            id=row.id,
            tool=row.tool,
            start_time=row.start_time,
            end_time=row.end_time,
            total_input_tokens=row.total_input_tokens,
            total_output_tokens=row.total_output_tokens,
            total_cost_usd=row.total_cost_usd,
            turn_count=row.turn_count,
            efficiency_score=row.efficiency_score,
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


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
async def get_session_detail(
    session_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    """Get session detail with associated events."""
    stmt = select(SessionRow).where(SessionRow.id == session_id)
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()

    if row is None:
        raise HTTPException(status_code=404, detail="Session not found")

    # Fetch events for this session
    events_stmt = (
        select(TokenEventRow)
        .where(TokenEventRow.session_id == session_id)
        .order_by(TokenEventRow.timestamp.asc())
    )
    events_result = await session.execute(events_stmt)
    event_rows = events_result.scalars().all()

    events = [
        TokenEventResponse(
            id=e.id,
            tool=e.tool,
            model=e.model,
            timestamp=e.timestamp,
            input_tokens=e.input_tokens,
            output_tokens=e.output_tokens,
            cost_usd=e.cost_usd,
            session_id=e.session_id,
            cache_read_tokens=e.cache_read_tokens,
            cache_write_tokens=e.cache_write_tokens,
        )
        for e in event_rows
    ]

    return SessionDetailResponse(
        id=row.id,
        tool=row.tool,
        start_time=row.start_time,
        end_time=row.end_time,
        total_input_tokens=row.total_input_tokens,
        total_output_tokens=row.total_output_tokens,
        total_cost_usd=row.total_cost_usd,
        turn_count=row.turn_count,
        efficiency_score=row.efficiency_score,
        events=events,
    )
