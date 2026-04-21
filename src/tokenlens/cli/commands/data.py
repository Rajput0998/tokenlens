"""tokenlens data — data retention commands (archive, prune)."""

from __future__ import annotations

import asyncio
import json
import tarfile
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import typer
from rich.console import Console

console = Console()

data_app = typer.Typer(help="Data retention and management commands.")


def register(app: typer.Typer) -> None:
    """Register the data command group on the top-level app."""
    app.add_typer(data_app, name="data")


@data_app.command()
def archive(
    before: str = typer.Option(..., help="Archive events before this date (YYYY-MM-DD)"),
    output: str | None = typer.Option(None, help="Output path for archive file"),
) -> None:
    """Export old events to .tar.gz and remove from DB."""
    try:
        cutoff = datetime.strptime(before, "%Y-%m-%d").replace(tzinfo=UTC)
    except ValueError:
        console.print("[red]Invalid date format. Use YYYY-MM-DD.[/red]")
        raise typer.Exit(code=1) from None

    result = asyncio.run(_archive_events(cutoff, output))
    if result is None:
        console.print("[yellow]No events found before the specified date.[/yellow]")
        return

    console.print(
        f"[green]Archived {result['count']} events to {result['path']}[/green]"
    )
    console.print(f"  Removed from DB: {result['count']} rows")


@data_app.command()
def prune(
    keep_days: int = typer.Option(..., "--keep-days", help="Delete events older than N days"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
) -> None:
    """Delete old events from the database."""
    cutoff = datetime.now(UTC) - timedelta(days=keep_days)

    count = asyncio.run(_count_events_before(cutoff))
    if count == 0:
        console.print("[yellow]No events to prune.[/yellow]")
        return

    if not yes:
        confirm = typer.confirm(
            f"Delete {count} events older than {keep_days} days?"
        )
        if not confirm:
            console.print("Cancelled.")
            return

    deleted = asyncio.run(_prune_events(cutoff))
    console.print(f"[green]Pruned {deleted} events.[/green]")


async def _archive_events(cutoff: datetime, output_path: str | None) -> dict | None:
    """Export events before cutoff to tar.gz and delete from DB."""
    from sqlalchemy import delete, select

    from tokenlens.core.config import get_data_dir
    from tokenlens.core.database import get_session, init_engine
    from tokenlens.core.models import TokenEventRow

    await init_engine()

    async with get_session() as db:
        result = await db.execute(
            select(TokenEventRow).where(TokenEventRow.timestamp < cutoff)
        )
        rows = result.scalars().all()

        if not rows:
            return None

        # Export to JSON
        events = [
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

        # Write to tar.gz
        if output_path is None:
            data_dir = get_data_dir()
            date_str = cutoff.strftime("%Y%m%d")
            output_path = str(data_dir / f"archive_{date_str}.tar.gz")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(events, f, default=str)
            json_path = f.name

        with tarfile.open(output_path, "w:gz") as tar:
            tar.add(json_path, arcname="events.json")

        Path(json_path).unlink()

        # Delete from DB
        await db.execute(
            delete(TokenEventRow).where(TokenEventRow.timestamp < cutoff)
        )

        return {"count": len(events), "path": output_path}


async def _count_events_before(cutoff: datetime) -> int:
    """Count events before cutoff date."""
    from sqlalchemy import func, select

    from tokenlens.core.database import get_session, init_engine
    from tokenlens.core.models import TokenEventRow

    await init_engine()

    async with get_session() as db:
        result = await db.execute(
            select(func.count(TokenEventRow.id)).where(
                TokenEventRow.timestamp < cutoff
            )
        )
        return result.scalar_one_or_none() or 0


async def _prune_events(cutoff: datetime) -> int:
    """Delete events before cutoff date."""
    from sqlalchemy import delete

    from tokenlens.core.database import get_session, init_engine
    from tokenlens.core.models import TokenEventRow

    await init_engine()

    async with get_session() as db:
        result = await db.execute(
            delete(TokenEventRow).where(TokenEventRow.timestamp < cutoff)
        )
        return result.rowcount or 0
