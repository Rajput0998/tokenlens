"""tokenlens status — show today's token usage summary."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import typer
from rich.console import Console

console = Console()


def register(app: typer.Typer) -> None:
    """Register the status command on the top-level app."""
    app.command(name="status")(status_command)


def status_command(
    short: bool = typer.Option(False, "--short", help="Output compact format: '42K/100K'"),
) -> None:
    """Show today's token usage summary."""
    if short:
        _short_status()
        return

    from tokenlens.core.config import get_db_path

    db_path = get_db_path()
    if not db_path.exists():
        console.print("[yellow]No data yet. Run `tokenlens init` first.[/yellow]")
        return

    try:
        result = asyncio.run(_query_today_status())
    except Exception as exc:
        console.print(f"[red]Error querying database: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    if result is None:
        console.print("[yellow]No data yet. Run `tokenlens init` first.[/yellow]")
        return

    total_tokens, per_tool, total_cost, burn_label = result

    # Format total tokens with commas
    total_str = f"{total_tokens:,}"

    # Format per-tool breakdown (only active adapters — Phase 1 = Claude Code)
    tool_parts: list[str] = []
    for tool_name, tokens in per_tool.items():
        display_name = _tool_display_name(tool_name)
        token_label = _format_tokens_short(tokens)
        tool_parts.append(f"{display_name}: {token_label}")

    tool_str = " | ".join(tool_parts) if tool_parts else "no activity"

    # Format cost
    cost_str = f"${total_cost:.2f}"

    console.print(
        f"Today: {total_str} tokens | {tool_str} | Cost: {cost_str} | Burn: {burn_label}"
    )

    # Check DB size warning (500MB threshold)
    _check_db_size_warning()


def _short_status() -> None:
    """Output compact status: '42K/100K' or empty string if unreachable."""
    from tokenlens.core.config import get_db_path, settings

    db_path = get_db_path()
    if not db_path.exists():
        return  # Empty output

    try:
        result = asyncio.run(_query_today_status())
    except Exception:
        return  # Empty output on error

    if result is None:
        return  # Empty output

    total_tokens, _, _, _ = result
    daily_limit = settings.get("alerts.thresholds.daily_token_limit", None)

    token_str = _format_tokens_short(total_tokens)
    if daily_limit:
        limit_str = _format_tokens_short(int(daily_limit))
        typer.echo(f"{token_str}/{limit_str}")
    else:
        typer.echo(token_str)


async def _query_today_status() -> (
    tuple[int, dict[str, int], float, str] | None
):
    """Query DB for today's token events and compute summary.

    Returns (total_tokens, per_tool_tokens, total_cost, burn_label) or None.
    """
    from sqlalchemy import func, select

    from tokenlens.core.database import close_engine, init_engine
    from tokenlens.core.models import TokenEventRow
    from tokenlens.core.utils import calculate_burn_rate

    engine = await init_engine()

    try:
        from sqlalchemy.ext.asyncio import async_sessionmaker

        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        async with session_factory() as session:
            now = datetime.now(UTC)
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

            # Query: sum tokens per tool for today
            stmt = (
                select(
                    TokenEventRow.tool,
                    func.sum(TokenEventRow.input_tokens + TokenEventRow.output_tokens).label(
                        "total_tokens"
                    ),
                    func.sum(TokenEventRow.cost_usd).label("total_cost"),
                )
                .where(TokenEventRow.timestamp >= today_start)
                .group_by(TokenEventRow.tool)
            )

            result = await session.execute(stmt)
            rows = result.all()

            if not rows:
                return None

            per_tool: dict[str, int] = {}
            total_tokens = 0
            total_cost = 0.0

            for row in rows:
                tool_name = row[0]
                tokens = int(row[1] or 0)
                cost = float(row[2] or 0.0)
                per_tool[tool_name] = tokens
                total_tokens += tokens
                total_cost += cost

            # Calculate burn rate
            hours_elapsed = (now - today_start).total_seconds() / 3600
            burn_label = calculate_burn_rate(total_tokens, hours_elapsed)

            return total_tokens, per_tool, total_cost, burn_label
    finally:
        await close_engine()


def _tool_display_name(tool: str) -> str:
    """Convert tool enum value to display name."""
    names = {
        "claude_code": "Claude Code",
        "kiro": "Kiro",
    }
    return names.get(tool, tool)


def _format_tokens_short(tokens: int) -> str:
    """Format token count in short form: 45231 → '45K'."""
    if tokens >= 1_000_000:
        return f"{tokens / 1_000_000:.1f}M"
    if tokens >= 1_000:
        return f"{tokens / 1_000:.0f}K"
    return str(tokens)


_DB_SIZE_WARNING_MB = 500


def _check_db_size_warning() -> None:
    """Warn if DB file exceeds 500MB."""
    try:
        from tokenlens.core.config import get_db_path

        db_path = get_db_path()
        if db_path.exists():
            size_mb = db_path.stat().st_size / (1024 * 1024)
            if size_mb > _DB_SIZE_WARNING_MB:
                console.print(
                    f"\n[yellow]⚠ Database size: {size_mb:.0f}MB (>{_DB_SIZE_WARNING_MB}MB). "
                    f"Consider running `tokenlens data prune` or `tokenlens data archive`.[/yellow]"
                )
    except Exception:
        pass  # Graceful degradation
