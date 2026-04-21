"""tokenlens export — export token data to CSV or JSON."""

from __future__ import annotations

import asyncio
import csv
import io
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import typer
from rich.console import Console

console = Console()


def register(app: typer.Typer) -> None:
    """Register the export command on the top-level app."""
    app.command(name="export")(export_command)


def export_command(
    format: str = typer.Option("csv", help="Export format: csv, json"),
    period: str = typer.Option("today", help="Period: today, week, month, all"),
    output: str | None = typer.Option(None, help="Output file path (default: stdout)"),
) -> None:
    """Export token events to CSV or JSON. Queries DB directly."""
    data = asyncio.run(_query_events(period))

    if not data:
        console.print("[yellow]No data to export for the specified period.[/yellow]")
        return

    if format == "json":
        content = _format_json(data)
    else:
        content = _format_csv(data)  # noqa: SIM108

    if output:
        path = Path(output)
        path.write_text(content)
        console.print(f"[green]Exported {len(data)} events to {path}[/green]")
    else:
        console.print(content)


async def _query_events(period: str) -> list[dict]:
    """Query DB for token events in the specified period."""
    from sqlalchemy import select

    from tokenlens.core.database import get_session, init_engine
    from tokenlens.core.models import TokenEventRow

    await init_engine()

    now = datetime.now(UTC)
    if period == "today":
        since = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        since = now - timedelta(days=7)
    elif period == "month":
        since = now - timedelta(days=30)
    else:
        since = None

    async with get_session() as db:
        stmt = select(TokenEventRow).order_by(TokenEventRow.timestamp)
        if since is not None:
            stmt = stmt.where(TokenEventRow.timestamp >= since)

        result = await db.execute(stmt)
        rows = result.scalars().all()

        return [
            {
                "id": row.id,
                "tool": row.tool,
                "model": row.model,
                "session_id": row.session_id,
                "timestamp": row.timestamp.isoformat() if row.timestamp else "",
                "input_tokens": row.input_tokens,
                "output_tokens": row.output_tokens,
                "cost_usd": row.cost_usd,
                "turn_number": row.turn_number,
            }
            for row in rows
        ]


def _format_csv(data: list[dict]) -> str:
    """Format data as CSV string."""
    if not data:
        return ""

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=data[0].keys())
    writer.writeheader()
    writer.writerows(data)
    return output.getvalue()


def _format_json(data: list[dict]) -> str:
    """Format data as JSON string."""
    return json.dumps(data, indent=2, default=str)
