"""TokenLens MCP Server — stdio transport for Kiro integration.

Provides tools for logging conversation turns, querying token status,
and getting efficiency tips via the Model Context Protocol.
"""

from __future__ import annotations

import threading
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("tokenlens")

# Dedicated SessionManager state for MCP server (thread-safe)
_mcp_lock = threading.Lock()
_mcp_sessions: dict[str, tuple[str, datetime]] = {}  # tool → (session_id, last_ts)
_SESSION_GAP_MINUTES = 15


def _get_or_create_session(tool: str, timestamp: datetime) -> str:
    """Get existing session or create new one based on gap detection."""
    with _mcp_lock:
        if tool in _mcp_sessions:
            session_id, last_ts = _mcp_sessions[tool]
            gap = timestamp - last_ts
            if gap > timedelta(minutes=_SESSION_GAP_MINUTES):
                # New session
                new_id = str(uuid.uuid4())
                _mcp_sessions[tool] = (new_id, timestamp)
                return new_id
            else:
                _mcp_sessions[tool] = (session_id, timestamp)
                return session_id
        else:
            new_id = str(uuid.uuid4())
            _mcp_sessions[tool] = (new_id, timestamp)
            return new_id


def _estimate_tokens(text: str) -> int:
    """Estimate token count using tiktoken cl100k_base encoding."""
    try:
        import tiktoken

        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except ImportError:
        # Fallback: rough estimate of ~4 chars per token
        return max(len(text) // 4, 1)


@mcp.tool()
async def log_conversation_turn(
    role: str,
    content: str,
    model: str = "kiro-auto",
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Log a conversation turn with token estimation.

    Args:
        role: The role of the speaker (e.g., "user", "assistant").
        content: The text content of the turn.
        model: The model name (default: "kiro-auto").
        timestamp: ISO format timestamp (default: now).

    Returns:
        Dict with event_id and estimated_tokens.
    """
    ts = datetime.fromisoformat(timestamp) if timestamp else datetime.now(UTC)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)

    estimated_tokens = _estimate_tokens(content)
    session_id = _get_or_create_session("kiro", ts)
    event_id = str(uuid.uuid4())

    # Determine input vs output tokens based on role
    if role == "assistant":
        input_tokens = 0
        output_tokens = estimated_tokens
    else:
        input_tokens = estimated_tokens
        output_tokens = 0

    # Store in database
    try:
        from tokenlens.core.database import get_session
        from tokenlens.core.models import TokenEventRow
        from tokenlens.core.pricing import calculate_cost

        cost, _ = calculate_cost(model, input_tokens, output_tokens)

        async with get_session() as db:
            row = TokenEventRow(
                id=event_id,
                tool="kiro",
                model=model,
                user_id="default",
                session_id=session_id,
                timestamp=ts,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost,
                context_type="chat",
                turn_number=0,
                raw_metadata={"estimated": True, "role": role},
            )
            db.add(row)
    except Exception:
        import logging

        logging.getLogger(__name__).warning(
            "Failed to store MCP event in DB. Event may be lost.", exc_info=True
        )

    return {
        "event_id": event_id,
        "estimated_tokens": estimated_tokens,
        "session_id": session_id,
    }


@mcp.tool()
async def get_token_status() -> dict[str, Any]:
    """Get today's token usage summary.

    Returns:
        Dict with today_total, per_tool breakdown, cost, and burn_rate.
    """
    try:
        from sqlalchemy import func, select

        from tokenlens.core.database import get_session
        from tokenlens.core.models import TokenEventRow

        today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)

        async with get_session() as db:
            result = await db.execute(
                select(
                    TokenEventRow.tool,
                    func.sum(TokenEventRow.input_tokens + TokenEventRow.output_tokens).label(
                        "total"
                    ),
                    func.sum(TokenEventRow.cost_usd).label("cost"),
                    func.count(TokenEventRow.id).label("events"),
                )
                .where(TokenEventRow.timestamp >= today_start)
                .group_by(TokenEventRow.tool)
            )
            rows = result.all()

        per_tool: dict[str, int] = {}
        total_tokens = 0
        total_cost = 0.0
        for row in rows:
            per_tool[row.tool] = int(row.total or 0)
            total_tokens += int(row.total or 0)
            total_cost += float(row.cost or 0)

        # Simple burn rate: tokens per hour
        hours_elapsed = max(
            (datetime.now(UTC) - today_start).total_seconds() / 3600, 1
        )
        burn_rate = f"{total_tokens / hours_elapsed:.0f} tokens/hour"

        return {
            "today_total": total_tokens,
            "per_tool": per_tool,
            "cost": round(total_cost, 4),
            "burn_rate": burn_rate,
        }
    except Exception as e:
        return {
            "today_total": 0,
            "per_tool": {},
            "cost": 0.0,
            "burn_rate": "unknown",
            "error": str(e),
        }


@mcp.tool()
async def log_session_summary(
    turns: list[dict[str, str]],
    model: str = "kiro-auto",
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Log an entire conversation session at once with accurate token estimation.

    Call this once at the end of a conversation instead of logging each turn
    individually. Each turn is tokenized separately for accurate input/output
    token counts.

    Args:
        turns: List of conversation turns. Each turn is a dict with:
            - role: "user" or "assistant"
            - content: The full text content of that turn
        model: The model name (default: "kiro-auto").
        timestamp: ISO format timestamp for the session (default: now).

    Returns:
        Dict with session_id, total_input_tokens, total_output_tokens,
        total_cost, and turn_count.
    """
    ts = datetime.fromisoformat(timestamp) if timestamp else datetime.now(UTC)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)

    session_id = _get_or_create_session("kiro", ts)

    total_input = 0
    total_output = 0
    total_cost = 0.0
    events_created = 0

    try:
        from tokenlens.core.database import get_session
        from tokenlens.core.models import TokenEventRow
        from tokenlens.core.pricing import calculate_cost

        async with get_session() as db:
            for i, turn in enumerate(turns):
                role = turn.get("role", "user")
                content = turn.get("content", "")
                if not content:
                    continue

                estimated = _estimate_tokens(content)
                if role == "assistant":
                    inp, out = 0, estimated
                else:
                    inp, out = estimated, 0

                total_input += inp
                total_output += out

                cost, _ = calculate_cost(model, inp, out)
                total_cost += cost

                event_id = str(uuid.uuid4())
                row = TokenEventRow(
                    id=event_id,
                    tool="kiro",
                    model=model,
                    user_id="default",
                    session_id=session_id,
                    timestamp=ts + timedelta(seconds=i),
                    input_tokens=inp,
                    output_tokens=out,
                    cost_usd=cost,
                    context_type="chat",
                    turn_number=i + 1,
                    raw_metadata={"estimated": True, "role": role, "batch": True},
                )
                db.add(row)
                events_created += 1

    except Exception:
        import logging
        logging.getLogger(__name__).warning(
            "Failed to store session summary. Events may be lost.", exc_info=True
        )

    return {
        "session_id": session_id,
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_tokens": total_input + total_output,
        "total_cost": round(total_cost, 6),
        "turn_count": events_created,
    }


@mcp.tool()
async def get_efficiency_tips() -> dict[str, list[str]]:
    """Get top 3 efficiency recommendations.

    Returns:
        Dict with tips list.
    """
    try:
        from tokenlens.ml.efficiency import EfficiencyEngine

        engine = EfficiencyEngine()
        # Generate general recommendations
        tips = engine.generate_recommendations(50.0, [])
        return {"tips": tips[:3]}
    except Exception:
        return {
            "tips": [
                "Break large tasks into smaller, focused prompts.",
                "Avoid re-sending the same large context repeatedly.",
                "Start fresh sessions when switching topics.",
            ]
        }


def run_server() -> None:
    """Run the MCP server in stdio mode."""
    mcp.run(transport="stdio")
