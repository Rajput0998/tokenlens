"""tokenlens compare — side-by-side tool comparison table."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import typer
from rich.console import Console
from rich.table import Table

console = Console()


def register(app: typer.Typer) -> None:
    """Register the compare command on the top-level app."""
    app.command(name="compare")(compare_command)


def compare_command(
    period: str = typer.Option("week", help="Period: today, week, month"),
) -> None:
    """Compare token usage across tools side-by-side."""
    data = asyncio.run(_gather_comparison(period))
    if not data:
        console.print("[yellow]No data available for comparison.[/yellow]")
        return

    table = Table(title=f"Tool Comparison — {period}")
    table.add_column("Metric")
    for tool in data:
        table.add_column(tool, justify="right")

    metrics = [
        "Total Tokens", "Input Tokens", "Output Tokens", "Cost", "Sessions", "Avg Efficiency",
    ]
    for metric in metrics:
        row = [metric]
        for tool in data:
            val = data[tool].get(metric, "—")
            row.append(str(val))
        table.add_row(*row)

    console.print(table)


async def _gather_comparison(period: str) -> dict[str, dict[str, str]]:
    """Query DB for per-tool comparison data."""
    from sqlalchemy import func, select

    from tokenlens.core.database import get_session, init_engine
    from tokenlens.core.models import SessionRow, TokenEventRow

    await init_engine()

    now = datetime.now(UTC)
    if period == "today":
        since = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        since = now - timedelta(days=7)
    else:
        since = now - timedelta(days=30)

    result_data: dict[str, dict[str, str]] = {}

    async with get_session() as db:
        result = await db.execute(
            select(
                TokenEventRow.tool,
                func.sum(TokenEventRow.input_tokens).label("input"),
                func.sum(TokenEventRow.output_tokens).label("output"),
                func.sum(TokenEventRow.cost_usd).label("cost"),
                func.count(TokenEventRow.session_id.distinct()).label("sessions"),
            )
            .where(TokenEventRow.timestamp >= since)
            .group_by(TokenEventRow.tool)
        )
        rows = result.all()

        for row in rows:
            tool = row.tool
            total = int(row.input or 0) + int(row.output or 0)
            result_data[tool] = {
                "Total Tokens": f"{total:,}",
                "Input Tokens": f"{int(row.input or 0):,}",
                "Output Tokens": f"{int(row.output or 0):,}",
                "Cost": f"${float(row.cost or 0):.2f}",
                "Sessions": str(int(row.sessions or 0)),
                "Avg Efficiency": "—",
            }

        # Get efficiency scores per tool
        eff_result = await db.execute(
            select(
                SessionRow.tool,
                func.avg(SessionRow.efficiency_score).label("avg_eff"),
            )
            .where(SessionRow.start_time >= since)
            .where(SessionRow.efficiency_score.isnot(None))
            .group_by(SessionRow.tool)
        )
        for row in eff_result.all():
            if row.tool in result_data and row.avg_eff is not None:
                result_data[row.tool]["Avg Efficiency"] = f"{float(row.avg_eff):.1f}"

    return result_data
