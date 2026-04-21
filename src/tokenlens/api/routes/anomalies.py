"""Anomaly endpoints: list and detail."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tokenlens.api.deps import get_db_session
from tokenlens.api.schemas import (
    AnomalyDetailResponse,
    AnomalyResponse,
    PaginatedResponse,
    PaginationMeta,
)
from tokenlens.core.models import AnomalyRow

router = APIRouter(prefix="/anomalies", tags=["anomalies"])


@router.get("")
async def list_anomalies(
    severity: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    classification: str | None = None,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_db_session),
) -> PaginatedResponse[AnomalyResponse]:
    """List detected anomalies with filtering."""
    stmt = select(AnomalyRow)
    count_stmt = select(func.count()).select_from(AnomalyRow)

    if severity:
        stmt = stmt.where(AnomalyRow.severity == severity)
        count_stmt = count_stmt.where(AnomalyRow.severity == severity)
    if date_from:
        stmt = stmt.where(AnomalyRow.timestamp >= date_from)
        count_stmt = count_stmt.where(AnomalyRow.timestamp >= date_from)
    if date_to:
        stmt = stmt.where(AnomalyRow.timestamp <= date_to)
        count_stmt = count_stmt.where(AnomalyRow.timestamp <= date_to)
    if classification:
        stmt = stmt.where(AnomalyRow.classification == classification)
        count_stmt = count_stmt.where(AnomalyRow.classification == classification)

    total_result = await session.execute(count_stmt)
    total = total_result.scalar() or 0

    stmt = stmt.order_by(AnomalyRow.timestamp.desc())
    offset = (page - 1) * per_page
    stmt = stmt.offset(offset).limit(per_page)

    result = await session.execute(stmt)
    rows = result.scalars().all()

    data = [
        AnomalyResponse(
            id=row.id,
            timestamp=row.timestamp,
            severity=row.severity,
            classification=row.classification,
            description=row.description,
            score=row.score,
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


@router.get("/{anomaly_id}", response_model=AnomalyDetailResponse)
async def get_anomaly_detail(
    anomaly_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    """Get anomaly detail with metadata."""
    stmt = select(AnomalyRow).where(AnomalyRow.id == anomaly_id)
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()

    if row is None:
        raise HTTPException(status_code=404, detail="Anomaly not found")

    return AnomalyDetailResponse(
        id=row.id,
        timestamp=row.timestamp,
        severity=row.severity,
        classification=row.classification,
        description=row.description,
        score=row.score,
        metadata_json=row.metadata_json,
    )
