"""GET /api/v1/events — paginated, filtered token events."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tokenlens.api.deps import get_db_session
from tokenlens.api.schemas import PaginatedResponse, PaginationMeta, TokenEventResponse
from tokenlens.core.models import TokenEventRow

router = APIRouter(tags=["events"])

ALLOWED_SORT_COLUMNS = {
    "timestamp", "tool", "model", "input_tokens",
    "output_tokens", "cost_usd", "session_id",
}


@router.get("/events")
async def list_events(
    tool: str | None = None,
    model: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    session_id: str | None = None,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    sort_by: str = "timestamp",
    sort_order: str = "desc",
    session: AsyncSession = Depends(get_db_session),
) -> PaginatedResponse[TokenEventResponse]:
    """List token events with pagination and filtering."""
    stmt = select(TokenEventRow)
    count_stmt = select(func.count()).select_from(TokenEventRow)

    # Filters
    if tool:
        stmt = stmt.where(TokenEventRow.tool == tool)
        count_stmt = count_stmt.where(TokenEventRow.tool == tool)
    if model:
        stmt = stmt.where(TokenEventRow.model == model)
        count_stmt = count_stmt.where(TokenEventRow.model == model)
    if date_from:
        stmt = stmt.where(TokenEventRow.timestamp >= date_from)
        count_stmt = count_stmt.where(TokenEventRow.timestamp >= date_from)
    if date_to:
        stmt = stmt.where(TokenEventRow.timestamp <= date_to)
        count_stmt = count_stmt.where(TokenEventRow.timestamp <= date_to)
    if session_id:
        stmt = stmt.where(TokenEventRow.session_id == session_id)
        count_stmt = count_stmt.where(TokenEventRow.session_id == session_id)

    # Count
    total_result = await session.execute(count_stmt)
    total = total_result.scalar() or 0

    # Sort — whitelist allowed columns to prevent schema probing
    if sort_by not in ALLOWED_SORT_COLUMNS:
        sort_by = "timestamp"
    sort_col = getattr(TokenEventRow, sort_by, TokenEventRow.timestamp)
    stmt = (
        stmt.order_by(sort_col.asc()) if sort_order == "asc"
        else stmt.order_by(sort_col.desc())
    )

    # Paginate
    offset = (page - 1) * per_page
    stmt = stmt.offset(offset).limit(per_page)

    result = await session.execute(stmt)
    rows = result.scalars().all()

    data = [
        TokenEventResponse(
            id=row.id,
            tool=row.tool,
            model=row.model,
            timestamp=row.timestamp,
            input_tokens=row.input_tokens,
            output_tokens=row.output_tokens,
            cost_usd=row.cost_usd,
            session_id=row.session_id,
            cache_read_tokens=row.cache_read_tokens,
            cache_write_tokens=row.cache_write_tokens,
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
