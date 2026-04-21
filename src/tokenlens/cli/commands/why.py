"""tokenlens why — explain the last anomaly in plain English."""

from __future__ import annotations

import asyncio

import typer
from rich.console import Console

console = Console()


def register(app: typer.Typer) -> None:
    """Register the why command on the top-level app."""
    app.command(name="why")(why_command)


def why_command() -> None:
    """Explain the last detected anomaly in plain English."""
    result = asyncio.run(_get_last_anomaly())
    if result is None:
        console.print("[green]No anomalies detected recently. Usage looks normal.[/green]")
        return

    console.print("\n[bold]Last Anomaly Explanation[/bold]\n")
    console.print(f"  [bold]What:[/bold] {result['classification']}")
    console.print(f"  [bold]When:[/bold] {result['timestamp']}")
    console.print(f"  [bold]Severity:[/bold] {result['severity']}")
    console.print(f"  [bold]Why:[/bold] {result['description']}")
    console.print()

    if result.get("recommendation"):
        console.print(f"  [bold]Suggestion:[/bold] {result['recommendation']}")


async def _get_last_anomaly() -> dict | None:
    """Query DB for the most recent anomaly."""
    from sqlalchemy import select

    from tokenlens.core.database import get_session, init_engine
    from tokenlens.core.models import AnomalyRow

    await init_engine()

    async with get_session() as db:
        result = await db.execute(
            select(AnomalyRow)
            .order_by(AnomalyRow.detected_at.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()

        if row is None:
            return None

        return {
            "classification": row.classification,
            "timestamp": row.detected_at.strftime("%Y-%m-%d %H:%M UTC"),
            "severity": row.severity,
            "description": row.description,
            "recommendation": _get_recommendation(row.classification),
        }


def _get_recommendation(classification: str) -> str:
    """Generate a plain-English recommendation for the anomaly type."""
    recommendations = {
        "Large context loading": (
            "Consider breaking large files into smaller chunks or using "
            "session continuity to avoid re-sending context."
        ),
        "Extended conversation": (
            "Try starting a fresh session when switching topics. "
            "Long conversations accumulate context that increases cost."
        ),
        "Usage burst": (
            "A sudden spike in usage was detected. Check if automated "
            "processes or repeated retries are causing excess token consumption."
        ),
        "Unclassified anomaly": (
            "Review your recent sessions for unusual patterns. "
            "Consider checking if any tools are running unexpectedly."
        ),
    }
    return recommendations.get(
        classification,
        "Review recent usage patterns for optimization opportunities.",
    )
