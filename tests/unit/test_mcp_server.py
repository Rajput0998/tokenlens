"""Tests for MCP server tools."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from tokenlens.integrations.mcp_server import (
    _estimate_content_tokens,
    _get_or_create_session,
    _mcp_lock,
    _mcp_sessions,
)


# ---------------------------------------------------------------------------
# Token estimation by content type
# ---------------------------------------------------------------------------


class TestContentTokenEstimation:
    """Test _estimate_content_tokens with different content types."""

    def test_non_empty_text(self) -> None:
        tokens = _estimate_content_tokens("Hello, world! This is a test message.", "text")
        assert tokens > 0

    def test_empty_string(self) -> None:
        tokens = _estimate_content_tokens("", "text")
        assert tokens == 0

    def test_long_string(self) -> None:
        text = "The quick brown fox jumps over the lazy dog. " * 100
        tokens = _estimate_content_tokens(text, "text")
        assert tokens > 100

    def test_code_content(self) -> None:
        code = "def hello():\n    print('Hello, world!')\n    return 42\n"
        tokens = _estimate_content_tokens(code, "code")
        assert tokens > 5

    def test_code_has_more_tokens_than_text(self) -> None:
        """Code uses ~3.5 chars/token vs text ~4 chars/token, so same string = more tokens as code."""
        content = "x" * 1000
        code_tokens = _estimate_content_tokens(content, "code")
        text_tokens = _estimate_content_tokens(content, "text")
        assert code_tokens >= text_tokens


# ---------------------------------------------------------------------------
# estimate_kiro_turn creates accurate event
# ---------------------------------------------------------------------------


class TestEstimateKiroTurn:
    """Test estimate_kiro_turn creates TokenEvent with full breakdown."""

    @pytest.mark.asyncio
    async def test_creates_event(self) -> None:
        from tokenlens.integrations.mcp_server import estimate_kiro_turn

        result = await estimate_kiro_turn(
            user_message_chars=200,
            response_chars=1000,
            tools_called=["readFile", "strReplace"],
            model="claude-opus-4.6",
            notes="test turn",
        )
        assert "event_id" in result
        assert "total_tokens" in result
        assert result["total_tokens"] > 0
        assert "breakdown" in result
        assert result["breakdown"]["system_prompt"] == 3000
        assert result["breakdown"]["tool_call_overhead"] == 400  # 2 tools × 200

    @pytest.mark.asyncio
    async def test_file_read_tokens(self) -> None:
        from tokenlens.integrations.mcp_server import estimate_kiro_turn

        result = await estimate_kiro_turn(
            files_read=[{"path": "test.py", "chars": 3500}],
        )
        assert result["breakdown"]["files_read"] > 0


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
