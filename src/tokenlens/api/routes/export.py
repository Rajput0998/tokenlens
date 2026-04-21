"""Export endpoints: events CSV/JSON, report."""

from __future__ import annotations

import csv
import io
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tokenlens.api.deps import get_db_session
from tokenlens.core.models import TokenEventRow

router = APIRouter(prefix="/export", tags=["export"])


@router.get("/events")
async def export_events(
    format: str = Query(default="json", pattern="^(csv|json)$"),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    tool: str | None = None,
    session: AsyncSession = Depends(get_db_session),
):
    """Export events as CSV or JSON file download."""
    stmt = select(TokenEventRow)

    if date_from:
        stmt = stmt.where(TokenEventRow.timestamp >= date_from)
    if date_to:
        stmt = stmt.where(TokenEventRow.timestamp <= date_to)
    if tool:
        stmt = stmt.where(TokenEventRow.tool == tool)

    stmt = stmt.order_by(TokenEventRow.timestamp.asc())
    result = await session.execute(stmt)
    rows = result.scalars().all()

    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "id", "tool", "model", "timestamp", "input_tokens",
            "output_tokens", "cost_usd", "session_id",
        ])
        for row in rows:
            writer.writerow([
                row.id, row.tool, row.model, row.timestamp.isoformat(),
                row.input_tokens, row.output_tokens, row.cost_usd, row.session_id,
            ])
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=events.csv"},
        )
    else:
        import json

        data = [
            {
                "id": row.id,
                "tool": row.tool,
                "model": row.model,
                "timestamp": row.timestamp.isoformat(),
                "input_tokens": row.input_tokens,
                "output_tokens": row.output_tokens,
                "cost_usd": row.cost_usd,
                "session_id": row.session_id,
            }
            for row in rows
        ]
        content = json.dumps(data, indent=2)
        return StreamingResponse(
            iter([content]),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=events.json"},
        )


@router.get("/report")
async def export_report(
    period: str = Query(default="today", pattern="^(today|week|month)$"),
    format: str = Query(default="json", pattern="^(json|csv|markdown)$"),
    session: AsyncSession = Depends(get_db_session),
):
    """Export usage report for a period."""
    now = datetime.now(UTC)
    if period == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        start = now - timedelta(days=7)
    else:
        start = now - timedelta(days=30)

    stmt = select(
        func.sum(TokenEventRow.input_tokens + TokenEventRow.output_tokens).label("tokens"),
        func.sum(TokenEventRow.cost_usd).label("cost"),
        func.count().label("events"),
        func.count(func.distinct(TokenEventRow.session_id)).label("sessions"),
    ).where(TokenEventRow.timestamp >= start)

    result = await session.execute(stmt)
    row = result.one()

    report = {
        "period": period,
        "start": start.isoformat(),
        "end": now.isoformat(),
        "total_tokens": int(row.tokens or 0),
        "total_cost": round(float(row.cost or 0), 4),
        "total_events": int(row.events or 0),
        "total_sessions": int(row.sessions or 0),
    }

    if format == "markdown":
        md = f"""# TokenLens Report — {period}

**Period:** {report['start']} to {report['end']}

| Metric | Value |
|--------|-------|
| Total Tokens | {report['total_tokens']:,} |
| Total Cost | ${report['total_cost']:.4f} |
| Events | {report['total_events']} |
| Sessions | {report['total_sessions']} |
"""
        return StreamingResponse(
            iter([md]),
            media_type="text/markdown",
            headers={"Content-Disposition": f"attachment; filename=report-{period}.md"},
        )
    elif format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["metric", "value"])
        for k, v in report.items():
            writer.writerow([k, v])
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=report-{period}.csv"},
        )
    else:
        import json

        content = json.dumps(report, indent=2)
        return StreamingResponse(
            iter([content]),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=report-{period}.json"},
        )
