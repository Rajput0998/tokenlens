"""Tests for MCP server tools."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from tokenlens.integrations.mcp_server import (
    _estimate_tokens,
    _get_or_create_session,
    _mcp_lock,
    _mcp_sessions,
)


# ---------------------------------------------------------------------------
# tiktoken estimation
# ---------------------------------------------------------------------------


class TestTiktokenEstimation:
    """Test tiktoken estimation produces non-zero token counts."""

    def test_non_empty_string(self) -> None:
        tokens = _estimate_tokens("Hello, world! This is a test message.")
        assert tokens > 0

    def test_empty_string(self) -> None:
        tokens = _estimate_tokens("")
        # tiktoken returns 0 for empty string, fallback returns 1
        assert tokens >= 0

    def test_long_string(self) -> None:
        text = "The quick brown fox jumps over the lazy dog. " * 100
        tokens = _estimate_tokens(text)
        assert tokens > 100

    def test_code_content(self) -> None:
        code = "def hello():\n    print('Hello, world!')\n    return 42\n"
        tokens = _estimate_tokens(code)
        assert tokens > 5


# ---------------------------------------------------------------------------
# log_conversation_turn creates estimated event
# ---------------------------------------------------------------------------


class TestLogConversationTurn:
    """Test log_conversation_turn creates TokenEvent with estimated=true."""

    @pytest.mark.asyncio
    async def test_creates_event(self) -> None:
        from tokenlens.integrations.mcp_server import log_conversation_turn

        result = await log_conversation_turn(
            role="user",
            content="Write a Python function to sort a list.",
            model="kiro-auto",
        )
        assert "event_id" in result
        assert "estimated_tokens" in result
        assert result["estimated_tokens"] > 0
        assert "session_id" in result

    @pytest.mark.asyncio
    async def test_assistant_role(self) -> None:
        from tokenlens.integrations.mcp_server import log_conversation_turn

        result = await log_conversation_turn(
            role="assistant",
            content="Here is a sorting function:\ndef sort_list(lst):\n    return sorted(lst)",
        )
        assert result["estimated_tokens"] > 0


# ---------------------------------------------------------------------------
# Session boundary detection
# ---------------------------------------------------------------------------


class TestSessionBoundary:
    """Test session boundary detection (>15 min gap = new session)."""

    def setup_method(self) -> None:
        """Clear MCP sessions before each test."""
        with _mcp_lock:
            _mcp_sessions.clear()

    def test_same_session_within_gap(self) -> None:
        ts1 = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
        ts2 = datetime(2025, 1, 1, 12, 10, 0, tzinfo=UTC)  # 10 min later

        sid1 = _get_or_create_session("kiro", ts1)
        sid2 = _get_or_create_session("kiro", ts2)
        assert sid1 == sid2

    def test_new_session_after_gap(self) -> None:
        ts1 = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
        ts2 = datetime(2025, 1, 1, 12, 20, 0, tzinfo=UTC)  # 20 min later

        sid1 = _get_or_create_session("kiro", ts1)
        sid2 = _get_or_create_session("kiro", ts2)
        assert sid1 != sid2

    def test_exactly_15_min_same_session(self) -> None:
        ts1 = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
        ts2 = datetime(2025, 1, 1, 12, 15, 0, tzinfo=UTC)  # Exactly 15 min

        sid1 = _get_or_create_session("kiro", ts1)
        sid2 = _get_or_create_session("kiro", ts2)
        assert sid1 == sid2

    def test_first_call_creates_session(self) -> None:
        ts = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
        sid = _get_or_create_session("kiro", ts)
        assert sid is not None
        assert len(sid) == 36  # UUID format


# ---------------------------------------------------------------------------
# get_token_status structure
# ---------------------------------------------------------------------------


class TestGetTokenStatus:
    """Test get_token_status returns correct structure."""

    @pytest.mark.asyncio
    async def test_returns_structure(self) -> None:
        from tokenlens.integrations.mcp_server import get_token_status

        result = await get_token_status()
        assert "today_total" in result
        assert "per_tool" in result
        assert "cost" in result
        assert "burn_rate" in result
