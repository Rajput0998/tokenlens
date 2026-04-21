"""TokenLens MCP Server — stdio transport for Kiro integration.

Provides tools for estimating Kiro token usage, querying token status,
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


def _estimate_content_tokens(text: str, content_type: str = "text") -> int:
    """Estimate tokens for content based on type.

    Uses tiktoken when available, otherwise uses type-specific char ratios:
    - code: ~3.5 chars per token
    - json/structured: ~3 chars per token
    - text/natural language: ~4 chars per token
    """
    if not text:
        return 0
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except ImportError:
        ratio = {"code": 3.5, "json": 3.0, "text": 4.0}.get(content_type, 4.0)
        return max(int(len(text) / ratio), 1)


# Fixed token overhead constants (based on Claude API behavior)
_SYSTEM_PROMPT_TOKENS = 3000
_ENV_CONTEXT_TOKENS = 300
_PER_TOOL_CALL_OVERHEAD = 200
_PER_IMAGE_TOKENS = 1500
_CONVERSATION_HISTORY_BUFFER = 500  # metadata, separators, etc.


@mcp.tool()
async def estimate_kiro_turn(
    user_message_chars: int = 0,
    response_chars: int = 0,
    files_read: list[dict[str, Any]] | None = None,
    files_written: list[dict[str, Any]] | None = None,
    tools_called: list[str] | None = None,
    search_results_chars: int = 0,
    command_output_chars: int = 0,
    images_attached: int = 0,
    subagents_invoked: int = 0,
    model: str = "claude-opus-4.6",
    notes: str = "",
) -> dict[str, Any]:
    """Estimate actual Kiro token usage for a conversation turn.

    Call this at the end of every response to track real token consumption.
    Accounts for system prompt, steering files, tool I/O, conversation
    history, and all the hidden overhead that simple chat logging misses.

    Args:
        user_message_chars: Character count of the user's message.
        response_chars: Character count of the assistant's full response.
        files_read: List of files read, each with 'path' and 'chars' keys.
        files_written: List of files written/modified, each with 'path' and 'chars_changed'.
        tools_called: List of tool names invoked (e.g. ["readFile", "strReplace", "grepSearch"]).
        search_results_chars: Total chars of search/grep results received.
        command_output_chars: Total chars of bash command outputs received.
        images_attached: Number of images attached by the user.
        subagents_invoked: Number of subagents delegated to.
        model: Model name for cost calculation.
        notes: Optional description of what was done this turn.

    Returns:
        Dict with estimated input_tokens, output_tokens, total_tokens, cost,
        and breakdown of where tokens went.
    """
    files_read = files_read or []
    files_written = files_written or []
    tools_called = tools_called or []

    # --- Measure steering file overhead ---
    steering_tokens = 0
    try:
        import os
        steering_dir = os.path.join(os.getcwd(), ".kiro", "steering")
        if os.path.isdir(steering_dir):
            for fname in os.listdir(steering_dir):
                if fname.endswith(".md"):
                    fpath = os.path.join(steering_dir, fname)
                    with open(fpath, encoding="utf-8", errors="ignore") as f:
                        steering_tokens += _estimate_content_tokens(f.read(), "text")
    except Exception:
        steering_tokens = 5000  # fallback estimate

    # Also account for workspace-level steering rules injected by Kiro
    # (sdlc-*, token-budget, etc.) — these are in the parent .kiro/steering
    try:
        import os
        parent_steering = os.path.join(os.getcwd(), "..", ".kiro", "steering")
        if os.path.isdir(parent_steering):
            for fname in os.listdir(parent_steering):
                if fname.endswith(".md"):
                    fpath = os.path.join(parent_steering, fname)
                    with open(fpath, encoding="utf-8", errors="ignore") as f:
                        steering_tokens += _estimate_content_tokens(f.read(), "text")
    except Exception:
        pass

    # --- Calculate input tokens ---
    user_msg_tokens = _estimate_content_tokens("x" * user_message_chars, "text")
    file_read_tokens = sum(
        _estimate_content_tokens("x" * f.get("chars", 0), "code")
        for f in files_read
    )
    search_tokens = _estimate_content_tokens("x" * search_results_chars, "text")
    cmd_tokens = _estimate_content_tokens("x" * command_output_chars, "text")
    image_tokens = images_attached * _PER_IMAGE_TOKENS

    # Conversation history estimate: retrieve running total from DB
    history_tokens = await _get_conversation_history_tokens()

    input_tokens = (
        _SYSTEM_PROMPT_TOKENS
        + steering_tokens
        + history_tokens
        + user_msg_tokens
        + file_read_tokens
        + search_tokens
        + cmd_tokens
        + image_tokens
        + _ENV_CONTEXT_TOKENS
    )

    # --- Calculate output tokens ---
    response_tokens = _estimate_content_tokens("x" * response_chars, "text")
    tool_call_tokens = len(tools_called) * _PER_TOOL_CALL_OVERHEAD
    # Subagent invocations have significant overhead (prompt + context passing)
    subagent_tokens = subagents_invoked * 2000

    output_tokens = response_tokens + tool_call_tokens + subagent_tokens

    total_tokens = input_tokens + output_tokens

    # --- Calculate cost ---
    try:
        from tokenlens.core.pricing import calculate_cost
        cost, matched = calculate_cost(model, input_tokens, output_tokens)
        if not matched:
            # Fallback: Opus 4 pricing ($15/M input, $75/M output)
            cost = input_tokens * 15 / 1_000_000 + output_tokens * 75 / 1_000_000
    except Exception:
        cost = input_tokens * 15 / 1_000_000 + output_tokens * 75 / 1_000_000

    # --- Store in DB ---
    ts = datetime.now(UTC)
    session_id = _get_or_create_session("kiro", ts)
    event_id = str(uuid.uuid4())

    try:
        from tokenlens.core.database import get_session as get_db
        from tokenlens.core.models import TokenEventRow

        async with get_db() as db:
            row = TokenEventRow(
                id=event_id,
                tool="kiro",
                model=model,
                user_id="default",
                session_id=session_id,
                timestamp=ts,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=round(cost, 6),
                context_type="chat",
                turn_number=0,
                raw_metadata={
                    "estimated": True,
                    "estimation_method": "kiro_self_report",
                    "breakdown": {
                        "system_prompt": _SYSTEM_PROMPT_TOKENS,
                        "steering": steering_tokens,
                        "history": history_tokens,
                        "user_message": user_msg_tokens,
                        "files_read": file_read_tokens,
                        "search_results": search_tokens,
                        "command_outputs": cmd_tokens,
                        "images": image_tokens,
                        "env_context": _ENV_CONTEXT_TOKENS,
                        "response": response_tokens,
                        "tool_calls": tool_call_tokens,
                        "subagents": subagent_tokens,
                    },
                    "tools_called": tools_called,
                    "files_read_paths": [f.get("path", "") for f in files_read],
                    "files_written_paths": [f.get("path", "") for f in files_written],
                    "notes": notes,
                },
            )
            db.add(row)
    except Exception:
        import logging
        logging.getLogger(__name__).warning(
            "Failed to store Kiro turn estimate in DB.", exc_info=True
        )

    # Update running history total
    await _update_conversation_history_tokens(user_msg_tokens + response_tokens)

    return {
        "event_id": event_id,
        "session_id": session_id,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "cost_usd": round(cost, 6),
        "breakdown": {
            "system_prompt": _SYSTEM_PROMPT_TOKENS,
            "steering_files": steering_tokens,
            "conversation_history": history_tokens,
            "user_message": user_msg_tokens,
            "files_read": file_read_tokens,
            "search_results": search_tokens,
            "command_outputs": cmd_tokens,
            "images": image_tokens,
            "response_text": response_tokens,
            "tool_call_overhead": tool_call_tokens,
            "subagent_overhead": subagent_tokens,
        },
    }


async def _get_conversation_history_tokens() -> int:
    """Retrieve the running conversation history token count from settings."""
    try:
        from tokenlens.core.database import get_session as get_db
        from tokenlens.core.models import SettingRow
        from sqlalchemy import select

        async with get_db() as db:
            result = await db.execute(
                select(SettingRow.value).where(SettingRow.key == "kiro_history_tokens")
            )
            val = result.scalar()
            return int(val) if val else 0
    except Exception:
        return 0


async def _update_conversation_history_tokens(added_tokens: int) -> None:
    """Add tokens to the running conversation history total."""
    try:
        from tokenlens.core.database import get_session as get_db
        from tokenlens.core.models import SettingRow
        from sqlalchemy import select

        current = await _get_conversation_history_tokens()
        new_total = current + added_tokens

        async with get_db() as db:
            result = await db.execute(
                select(SettingRow).where(SettingRow.key == "kiro_history_tokens")
            )
            row = result.scalar_one_or_none()
            if row:
                row.value = str(new_total)
                row.updated_at = datetime.now(UTC)
            else:
                db.add(SettingRow(
                    key="kiro_history_tokens",
                    value=str(new_total),
                ))
    except Exception:
        pass


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
