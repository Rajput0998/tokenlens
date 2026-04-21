"""tokenlens live — Textual TUI for real-time token monitoring.

Requires the [tui] optional extra: pip install tokenlens[tui]
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any


def _check_textual_installed() -> None:
    """Raise ImportError with helpful message if textual is not installed."""
    try:
        import textual  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "The 'textual' package is required for `tokenlens live`.\n"
            "Install it with: pip install tokenlens[tui]"
        ) from exc


def run_live_tui() -> None:
    """Launch the Textual TUI application."""
    _check_textual_installed()

    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import Container, Horizontal, Vertical
    from textual.reactive import reactive
    from textual.widgets import Footer, Header, Static

    class TokenLensLive(App[None]):
        """Real-time token monitoring TUI."""

        CSS = """
        #top-bar {
            height: 3;
            background: $primary-background;
            padding: 0 1;
        }
        #top-bar Static {
            width: 1fr;
            content-align: center middle;
        }
        #main-area {
            height: 1fr;
        }
        #left-panel {
            width: 30;
            border-right: solid $primary;
            padding: 1;
        }
        #center-panel {
            width: 1fr;
            padding: 1;
        }
        #right-panel {
            width: 25;
            border-left: solid $primary;
            padding: 1;
        }
        #bottom-bar {
            height: 5;
            border-top: solid $primary;
            padding: 0 1;
        }
        .stat-label {
            color: $text-muted;
        }
        .stat-value {
            color: $text;
            text-style: bold;
        }
        """

        BINDINGS = [
            Binding("q", "quit", "Quit"),
            Binding("r", "refresh", "Refresh"),
            Binding("t", "toggle_tool", "Toggle Tool"),
            Binding("?", "help_screen", "Help"),
        ]

        total_tokens: reactive[int] = reactive(0)
        total_cost: reactive[float] = reactive(0.0)
        burn_rate: reactive[str] = reactive("slow")

        def compose(self) -> ComposeResult:
            yield Header(show_clock=True)
            with Horizontal(id="top-bar"):
                yield Static("Total: 0 tokens", id="stat-total")
                yield Static("Cost: $0.00", id="stat-cost")
                yield Static("Burn: slow", id="stat-burn")
            with Horizontal(id="main-area"):
                with Vertical(id="left-panel"):
                    yield Static("[b]Per-Tool Counters[/b]\n", id="tool-counters")
                with Vertical(id="center-panel"):
                    yield Static("[b]Timeline (2h rolling)[/b]\n", id="timeline")
                with Vertical(id="right-panel"):
                    yield Static("[b]Session Info[/b]\n", id="session-info")
            with Container(id="bottom-bar"):
                yield Static("[b]Recent Alerts[/b]\n(none)", id="alerts")
            yield Footer()

        def on_mount(self) -> None:
            """Start auto-refresh timer."""
            self.set_interval(5.0, self._refresh_data)
            # Initial load
            self.call_after_refresh(self._refresh_data)

        async def _refresh_data(self) -> None:
            """Fetch latest data from DB and update display."""
            try:
                data = await _fetch_live_data()
                self._update_display(data)
            except Exception:
                pass  # Graceful degradation

        def _update_display(self, data: dict[str, Any]) -> None:
            """Update all widgets with fresh data."""
            self.total_tokens = data.get("total_tokens", 0)
            self.total_cost = data.get("total_cost", 0.0)
            self.burn_rate = data.get("burn_rate", "slow")

            # Top bar
            self.query_one("#stat-total", Static).update(
                f"Total: {self.total_tokens:,} tokens"
            )
            self.query_one("#stat-cost", Static).update(
                f"Cost: ${self.total_cost:.2f}"
            )
            self.query_one("#stat-burn", Static).update(
                f"Burn: {self.burn_rate}"
            )

            # Left panel — per-tool counters
            tool_lines = ["[b]Per-Tool Counters[/b]\n"]
            for tool, count in data.get("per_tool", {}).items():
                tool_lines.append(f"  {tool}: {count:,}")
            self.query_one("#tool-counters", Static).update(
                "\n".join(tool_lines) or "[b]Per-Tool Counters[/b]\n(no data)"
            )

            # Center — timeline
            timeline_lines = ["[b]Timeline (2h rolling)[/b]\n"]
            for entry in data.get("timeline", [])[-12:]:
                bar_len = min(int(entry.get("tokens", 0) / 500), 40)
                bar = "█" * bar_len
                timeline_lines.append(
                    f"  {entry.get('hour', '??')} {bar} {entry.get('tokens', 0):,}"
                )
            self.query_one("#timeline", Static).update(
                "\n".join(timeline_lines)
                if len(timeline_lines) > 1
                else "[b]Timeline[/b]\n(collecting data)"
            )

            # Right — session info
            session_info = data.get("session_info", {})
            session_lines = [
                "[b]Session Info[/b]\n",
                f"  Active: {session_info.get('active_sessions', 0)}",
                f"  Today: {session_info.get('sessions_today', 0)}",
                f"  Avg turns: {session_info.get('avg_turns', 0):.0f}",
            ]
            self.query_one("#session-info", Static).update("\n".join(session_lines))

            # Bottom — alerts
            alerts = data.get("alerts", [])
            if alerts:
                alert_lines = ["[b]Recent Alerts[/b]\n"]
                for a in alerts[-3:]:
                    alert_lines.append(f"  ⚠ {a}")
                self.query_one("#alerts", Static).update("\n".join(alert_lines))

        def action_refresh(self) -> None:
            """Manual refresh."""
            asyncio.ensure_future(self._refresh_data())

        def action_toggle_tool(self) -> None:
            """Toggle tool filter (placeholder)."""
            self.notify("Tool filter toggled (all tools shown)")

        def action_help_screen(self) -> None:
            """Show help."""
            self.notify(
                "Keys: q=quit, r=refresh, t=toggle tool, ?=help",
                title="Help",
            )

    app = TokenLensLive()
    app.run()


async def _fetch_live_data() -> dict[str, Any]:
    """Query DB for live dashboard data."""
    from sqlalchemy import func, select

    from tokenlens.core.database import get_session
    from tokenlens.core.models import TokenEventRow
    from tokenlens.core.utils import calculate_burn_rate

    now = datetime.now(UTC)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    two_hours_ago = now - timedelta(hours=2)

    data: dict[str, Any] = {
        "total_tokens": 0,
        "total_cost": 0.0,
        "burn_rate": "slow",
        "per_tool": {},
        "timeline": [],
        "session_info": {"active_sessions": 0, "sessions_today": 0, "avg_turns": 0},
        "alerts": [],
    }

    try:
        async with get_session() as db:
            # Per-tool totals today
            result = await db.execute(
                select(
                    TokenEventRow.tool,
                    func.sum(
                        TokenEventRow.input_tokens + TokenEventRow.output_tokens
                    ).label("total"),
                    func.sum(TokenEventRow.cost_usd).label("cost"),
                )
                .where(TokenEventRow.timestamp >= today_start)
                .group_by(TokenEventRow.tool)
            )
            rows = result.all()

            total_tokens = 0
            total_cost = 0.0
            per_tool: dict[str, int] = {}
            for row in rows:
                tokens = int(row.total or 0)
                per_tool[row.tool] = tokens
                total_tokens += tokens
                total_cost += float(row.cost or 0)

            hours_elapsed = max((now - today_start).total_seconds() / 3600, 0.1)
            burn_rate = calculate_burn_rate(total_tokens, hours_elapsed)

            data["total_tokens"] = total_tokens
            data["total_cost"] = total_cost
            data["burn_rate"] = burn_rate
            data["per_tool"] = per_tool

            # Timeline — last 2 hours in 10-min buckets
            result = await db.execute(
                select(
                    func.strftime("%H:%M", TokenEventRow.timestamp).label("hour"),
                    func.sum(
                        TokenEventRow.input_tokens + TokenEventRow.output_tokens
                    ).label("tokens"),
                )
                .where(TokenEventRow.timestamp >= two_hours_ago)
                .group_by(func.strftime("%Y-%m-%d %H:%M", TokenEventRow.timestamp))
                .order_by(func.strftime("%Y-%m-%d %H:%M", TokenEventRow.timestamp))
            )
            timeline_rows = result.all()
            data["timeline"] = [
                {"hour": r.hour, "tokens": int(r.tokens or 0)} for r in timeline_rows
            ]

            # Session info
            result = await db.execute(
                select(
                    func.count(TokenEventRow.session_id.distinct()).label("sessions"),
                    func.avg(TokenEventRow.turn_number).label("avg_turns"),
                )
                .where(TokenEventRow.timestamp >= today_start)
            )
            session_row = result.one_or_none()
            if session_row:
                data["session_info"] = {
                    "active_sessions": 0,
                    "sessions_today": int(session_row.sessions or 0),
                    "avg_turns": float(session_row.avg_turns or 0),
                }
    except Exception:
        pass  # Return defaults on error

    return data
