"""tokenlens agent start/stop/status — manage the background collection daemon."""

from __future__ import annotations

import os
import signal
import time

import typer
from rich.console import Console

console = Console()


def register(agent_app: typer.Typer) -> None:
    """Register agent sub-commands on the agent Typer group."""
    agent_app.command(name="start")(agent_start)
    agent_app.command(name="stop")(agent_stop)
    agent_app.command(name="status")(agent_status)


def agent_start(
    foreground: bool = typer.Option(
        False,
        "--foreground",
        "-f",
        help="Run in foreground (primary mode for v0.1). "
        "For background: nohup tokenlens agent start --foreground &",
    ),
) -> None:
    """Start the TokenLens collection agent."""
    import asyncio

    from tokenlens.agent.daemon import (
        DaemonManager,
        daemon_shutdown,
        daemon_startup,
        daemon_watch_loop,
    )

    manager = DaemonManager()
    running, pid = manager.is_running()

    if running:
        console.print(f"[red]Agent already running (PID: {pid})[/red]")
        raise typer.Exit(code=1)

    if not foreground:
        console.print(
            "[yellow]Background daemonization not yet implemented.[/yellow]\n"
            "Use: [cyan]tokenlens agent start --foreground[/cyan]\n"
            "Or:  [cyan]nohup tokenlens agent start --foreground &[/cyan]"
        )
        raise typer.Exit(code=1)

    console.print("[green]Starting TokenLens agent in foreground...[/green]")

    async def _run() -> None:
        startup_result = await daemon_startup(manager)
        registry, session_manager, pipeline, watcher, file_change_queue, ml_runner = startup_result
        console.print(f"[green]Agent started (PID: {os.getpid()})[/green]")
        try:
            await daemon_watch_loop(
                manager, registry, session_manager, pipeline, watcher, file_change_queue, ml_runner
            )
        finally:
            await daemon_shutdown(manager, pipeline, session_manager, registry)

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        console.print("\n[yellow]Agent stopped.[/yellow]")


def agent_stop() -> None:
    """Stop the TokenLens collection agent."""
    from tokenlens.agent.daemon import DaemonManager

    manager = DaemonManager()
    running, pid = manager.is_running()

    if not running or pid is None:
        console.print("[yellow]Agent is not running.[/yellow]")
        raise typer.Exit(code=1)

    console.print(f"Stopping agent (PID: {pid})...")

    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        console.print("[yellow]Process already exited. Cleaning up PID file.[/yellow]")
        manager.remove_pid()
        return
    except PermissionError:
        console.print(f"[red]Permission denied sending SIGTERM to PID {pid}.[/red]")
        raise typer.Exit(code=1) from None

    # Wait up to 10 seconds for process to exit
    for _ in range(20):
        time.sleep(0.5)
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            console.print("[green]Agent stopped.[/green]")
            # Clean up PID file if still present
            manager.remove_pid()
            return

    console.print(f"[red]Agent (PID: {pid}) did not stop within 10 seconds.[/red]")
    raise typer.Exit(code=1)


def agent_status() -> None:
    """Show agent running state, PID, heartbeat, and events processed."""
    from tokenlens.agent.daemon import DaemonManager

    manager = DaemonManager()
    running, pid = manager.is_running()

    if not running:
        console.print("[yellow]Agent is not running.[/yellow]")
        return

    heartbeat = manager.read_heartbeat()
    heartbeat_str = heartbeat.strftime("%Y-%m-%d %H:%M:%S UTC") if heartbeat else "unknown"

    console.print(f"[green]Agent is running[/green] (PID: {pid})")
    console.print(f"  Last heartbeat: {heartbeat_str}")

    # Show events count from DB
    try:
        import asyncio

        from sqlalchemy import func, select

        from tokenlens.core.database import close_engine, init_engine
        from tokenlens.core.models import TokenEventRow

        async def _count_events() -> int:
            engine = await init_engine()
            from sqlalchemy.ext.asyncio import async_sessionmaker

            factory = async_sessionmaker(engine, expire_on_commit=False)
            async with factory() as session:
                result = await session.execute(select(func.count(TokenEventRow.id)))
                count = result.scalar() or 0
            await close_engine()
            return count

        total = asyncio.run(_count_events())
        console.print(f"  Total events in DB: {total:,}")
    except Exception:
        console.print("  Events processed: [dim]unable to query DB[/dim]")
