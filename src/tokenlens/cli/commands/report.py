"""tokenlens report — generate formatted usage reports."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

console = Console()


def register(app: typer.Typer) -> None:
    """Register the report command on the top-level app."""
    app.command(name="report")(report_command)


def report_command(
    period: str = typer.Option("today", help="Period: today, week, month"),
    format: str = typer.Option("table", help="Output format: table, json, markdown"),
) -> None:
    """Generate a usage report for the specified period."""
    data = asyncio.run(_gather_report_data(period))
    if data is None:
        console.print("[yellow]No data available for the specified period.[/yellow]")
        return

    if format == "json":
        _output_json(data)
    elif format == "markdown":
        _output_markdown(data, period)
    else:
        _output_table(data, period)


async def _gather_report_data(period: str) -> dict[str, Any] | None:
    """Query DB for report data."""
    from sqlalchemy import func, select

    from tokenlens.core.database import get_session, init_engine
    from tokenlens.core.models import SessionRow, TokenEventRow

    await init_engine()

    now = datetime.now(UTC)
    if period == "today":
        since = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        since = now - timedelta(days=7)
    elif period == "month":
        since = now - timedelta(days=30)
    else:
        since = now.replace(hour=0, minute=0, second=0, microsecond=0)

    async with get_session() as db:
        # Per-tool breakdown
        result = await db.execute(
            select(
                TokenEventRow.tool,
                func.sum(TokenEventRow.input_tokens).label("input"),
                func.sum(TokenEventRow.output_tokens).label("output"),
                func.sum(TokenEventRow.cost_usd).label("cost"),
                func.count(TokenEventRow.id).label("events"),
            )
            .where(TokenEventRow.timestamp >= since)
            .group_by(TokenEventRow.tool)
        )
        tool_rows = result.all()

        if not tool_rows:
            return None

        # Per-model breakdown
        result = await db.execute(
            select(
                TokenEventRow.model,
                func.sum(TokenEventRow.input_tokens + TokenEventRow.output_tokens).label("total"),
                func.sum(TokenEventRow.cost_usd).label("cost"),
            )
            .where(TokenEventRow.timestamp >= since)
            .group_by(TokenEventRow.model)
        )
        model_rows = result.all()

        # Top 5 sessions by token count
        result = await db.execute(
            select(
                SessionRow.id,
                SessionRow.tool,
                SessionRow.total_input_tokens,
                SessionRow.total_output_tokens,
                SessionRow.total_cost_usd,
                SessionRow.turn_count,
                SessionRow.efficiency_score,
            )
            .where(SessionRow.start_time >= since)
            .order_by(
                (SessionRow.total_input_tokens + SessionRow.total_output_tokens).desc()
            )
            .limit(5)
        )
        session_rows = result.all()

        # Efficiency average
        result = await db.execute(
            select(func.avg(SessionRow.efficiency_score))
            .where(SessionRow.start_time >= since)
            .where(SessionRow.efficiency_score.isnot(None))
        )
        avg_efficiency = result.scalar_one_or_none()

    total_input = sum(int(r.input or 0) for r in tool_rows)
    total_output = sum(int(r.output or 0) for r in tool_rows)
    total_cost = sum(float(r.cost or 0) for r in tool_rows)

    return {
        "period": period,
        "since": since.isoformat(),
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_tokens": total_input + total_output,
        "total_cost": total_cost,
        "per_tool": [
            {
                "tool": r.tool,
                "input_tokens": int(r.input or 0),
                "output_tokens": int(r.output or 0),
                "cost": float(r.cost or 0),
                "events": int(r.events or 0),
            }
            for r in tool_rows
        ],
        "per_model": [
            {
                "model": r.model,
                "total_tokens": int(r.total or 0),
                "cost": float(r.cost or 0),
            }
            for r in model_rows
        ],
        "top_sessions": [
            {
                "id": r.id[:8],
                "tool": r.tool,
                "tokens": (r.total_input_tokens or 0) + (r.total_output_tokens or 0),
                "cost": float(r.total_cost_usd or 0),
                "turns": r.turn_count or 0,
                "efficiency": r.efficiency_score,
            }
            for r in session_rows
        ],
        "avg_efficiency": float(avg_efficiency) if avg_efficiency else None,
    }


def _output_table(data: dict[str, Any], period: str) -> None:
    """Render report as Rich table."""
    console.print(f"\n[bold]TokenLens Report — {period}[/bold]\n")

    # Summary
    console.print(
        f"  Total tokens: {data['total_tokens']:,} "
        f"(input: {data['total_input_tokens']:,}, output: {data['total_output_tokens']:,})"
    )
    console.print(f"  Total cost: ${data['total_cost']:.2f}")
    if data["avg_efficiency"] is not None:
        console.print(f"  Avg efficiency: {data['avg_efficiency']:.1f}/100")
    console.print()

    # Per-tool table
    table = Table(title="Per-Tool Breakdown")
    table.add_column("Tool")
    table.add_column("Input", justify="right")
    table.add_column("Output", justify="right")
    table.add_column("Cost", justify="right")
    table.add_column("Events", justify="right")
    for t in data["per_tool"]:
        table.add_row(
            t["tool"],
            f"{t['input_tokens']:,}",
            f"{t['output_tokens']:,}",
            f"${t['cost']:.2f}",
            str(t["events"]),
        )
    console.print(table)

    # Per-model table
    if data["per_model"]:
        model_table = Table(title="Per-Model Breakdown")
        model_table.add_column("Model")
        model_table.add_column("Tokens", justify="right")
        model_table.add_column("Cost", justify="right")
        for m in data["per_model"]:
            model_table.add_row(m["model"], f"{m['total_tokens']:,}", f"${m['cost']:.2f}")
        console.print(model_table)

    # Top sessions
    if data["top_sessions"]:
        sess_table = Table(title="Top 5 Sessions")
        sess_table.add_column("ID")
        sess_table.add_column("Tool")
        sess_table.add_column("Tokens", justify="right")
        sess_table.add_column("Cost", justify="right")
        sess_table.add_column("Turns", justify="right")
        for s in data["top_sessions"]:
            sess_table.add_row(
                s["id"], s["tool"], f"{s['tokens']:,}", f"${s['cost']:.2f}", str(s["turns"])
            )
        console.print(sess_table)


def _output_json(data: dict[str, Any]) -> None:
    """Output report as JSON."""
    console.print_json(json.dumps(data, indent=2, default=str))


def _output_markdown(data: dict[str, Any], period: str) -> None:
    """Output report as Markdown."""
    lines = [
        f"# TokenLens Report — {period}",
        "",
        f"**Total tokens:** {data['total_tokens']:,}",
        f"**Total cost:** ${data['total_cost']:.2f}",
    ]
    if data["avg_efficiency"] is not None:
        lines.append(f"**Avg efficiency:** {data['avg_efficiency']:.1f}/100")
    lines.extend(["", "## Per-Tool Breakdown", "", "| Tool | Input | Output | Cost | Events |"])
    lines.append("| --- | ---: | ---: | ---: | ---: |")
    for t in data["per_tool"]:
        lines.append(
            f"| {t['tool']} | {t['input_tokens']:,} | {t['output_tokens']:,} "
            f"| ${t['cost']:.2f} | {t['events']} |"
        )
    lines.extend(["", "## Per-Model Breakdown", "", "| Model | Tokens | Cost |"])
    lines.append("| --- | ---: | ---: |")
    for m in data["per_model"]:
        lines.append(f"| {m['model']} | {m['total_tokens']:,} | ${m['cost']:.2f} |")

    console.print("\n".join(lines))
