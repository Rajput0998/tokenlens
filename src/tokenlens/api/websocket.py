"""WebSocket endpoints: /ws/live (5s push) and /ws/alerts."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from sqlalchemy import func, select

from tokenlens.core.models import TokenEventRow

# Connected clients
_live_clients: set[WebSocket] = set()  # noqa: F823
_alert_clients: set[WebSocket] = set()  # noqa: F823

PING_TIMEOUT = 30  # seconds
PUSH_INTERVAL = 5  # seconds


async def _get_live_data() -> dict[str, Any]:
    """Fetch current live data for WebSocket push."""
    from tokenlens.core.database import get_session
    from tokenlens.core.utils import calculate_burn_rate

    now = datetime.now(UTC)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    async with get_session() as session:
        stmt = (
            select(
                TokenEventRow.tool,
                func.sum(TokenEventRow.input_tokens + TokenEventRow.output_tokens).label("total"),
                func.sum(TokenEventRow.cost_usd).label("cost"),
            )
            .where(TokenEventRow.timestamp >= today_start)
            .group_by(TokenEventRow.tool)
        )
        result = await session.execute(stmt)
        rows = result.all()

    per_tool: dict[str, int] = {}
    today_total = 0
    cost_today = 0.0
    for row in rows:
        tokens = int(row.total or 0)
        per_tool[row.tool] = tokens
        today_total += tokens
        cost_today += float(row.cost or 0.0)

    # Count active sessions (sessions with events in last 15 min)
    from datetime import timedelta

    active_cutoff = now - timedelta(minutes=15)
    async with get_session() as session:
        from sqlalchemy import distinct

        active_result = await session.execute(
            select(func.count(distinct(TokenEventRow.session_id))).where(
                TokenEventRow.timestamp >= active_cutoff
            )
        )
        active_sessions = active_result.scalar() or 0

    hours_elapsed = (now - today_start).total_seconds() / 3600
    burn_rate_category = calculate_burn_rate(today_total, hours_elapsed)
    burn_rate_numeric = round(today_total / max(hours_elapsed, 0.01), 1)

    # Get hourly breakdown for sparkline charts
    from collections import defaultdict

    hourly_by_tool: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    async with get_session() as session:
        hourly_stmt = (
            select(
                TokenEventRow.tool,
                TokenEventRow.timestamp,
                (TokenEventRow.input_tokens + TokenEventRow.output_tokens).label("tokens"),
            )
            .where(TokenEventRow.timestamp >= today_start)
        )
        hourly_result = await session.execute(hourly_stmt)
        for hrow in hourly_result.all():
            hour_bucket = hrow.timestamp.hour
            hourly_by_tool[hrow.tool][hour_bucket] += int(hrow.tokens)

    # Build per-tool details with hourly data
    per_tool_details: list[dict[str, Any]] = []
    for tool_name, total_tokens in per_tool.items():
        hourly_data = []
        current_hour = now.hour
        for h in range(24):
            hourly_data.append({
                "hour": h,
                "tokens": hourly_by_tool.get(tool_name, {}).get(h, 0),
            })
        per_tool_details.append({
            "tool": tool_name,
            "total_tokens": total_tokens,
            "cost": round(cost_today, 4),
            "active": tool_name in [r.tool for r in rows if (now - timedelta(minutes=15)) <= now],
            "hourly": hourly_data,
        })

    # Session window stats
    from tokenlens.core.session_window import find_current_session_start, get_session_stats

    session_start = await find_current_session_start()
    session_stats = await get_session_stats(session_start)

    return {
        "type": "live_update",
        "data": {
            "today_total": today_total,
            "per_tool": per_tool,
            "per_tool_details": per_tool_details,
            "burn_rate": burn_rate_numeric,
            "burn_rate_category": burn_rate_category,
            "active_sessions": active_sessions,
            "cost_today": round(cost_today, 4),
            "last_event_timestamp": now.isoformat(),
            "session": session_stats,
        },
    }


async def _live_push_loop():
    """Background task pushing live data every 5 seconds."""
    while True:
        if _live_clients:
            try:
                data = await _get_live_data()
                message = json.dumps(data, default=str)
                disconnected = set()
                for ws in _live_clients.copy():
                    try:
                        await ws.send_text(message)
                    except Exception:
                        disconnected.add(ws)
                _live_clients -= disconnected
            except Exception:
                pass
        await asyncio.sleep(PUSH_INTERVAL)


async def broadcast_alert(alert: dict[str, Any]) -> None:
    """Broadcast an alert to all connected /ws/alerts clients."""
    message = json.dumps(alert, default=str)
    disconnected = set()
    for ws in _alert_clients.copy():
        try:
            await ws.send_text(message)
        except Exception:
            disconnected.add(ws)
    _alert_clients -= disconnected


def register_websockets(app: FastAPI) -> None:
    """Register WebSocket routes on the FastAPI app.

    NOTE: The _live_push_loop background task is started in the lifespan
    handler in app.py, NOT via the deprecated @app.on_event("startup").
    """

    @app.websocket("/ws/live")
    async def ws_live(websocket: WebSocket):
        await websocket.accept()
        _live_clients.add(websocket)

        # Send initial payload
        try:
            data = await _get_live_data()
            await websocket.send_text(json.dumps(data, default=str))
        except Exception:
            pass

        try:
            while True:
                # Keep connection alive, handle pings
                try:
                    await asyncio.wait_for(
                        websocket.receive_text(), timeout=PING_TIMEOUT
                    )
                except TimeoutError:
                    # Send ping
                    try:
                        await websocket.send_text(json.dumps({"type": "ping"}))
                    except Exception:
                        break
        except WebSocketDisconnect:
            pass
        finally:
            _live_clients.discard(websocket)

    @app.websocket("/ws/alerts")
    async def ws_alerts(websocket: WebSocket):
        await websocket.accept()
        _alert_clients.add(websocket)

        try:
            while True:
                try:
                    await asyncio.wait_for(
                        websocket.receive_text(), timeout=PING_TIMEOUT
                    )
                except TimeoutError:
                    try:
                        await websocket.send_text(json.dumps({"type": "ping"}))
                    except Exception:
                        break
        except WebSocketDisconnect:
            pass
        finally:
            _alert_clients.discard(websocket)
