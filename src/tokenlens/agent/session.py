"""Session boundary detection and aggregation.

Detects session boundaries by timestamp gaps and aggregates session stats on close.
Supports two strategies:
- GapBasedStrategy: for non-claude_code tools (e.g., kiro) — new session on idle gap.
- RollingWindowStrategy: for claude_code — session expires 5h after start_time.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Protocol

import structlog
from sqlalchemy import func, select

from tokenlens.core.database import get_session
from tokenlens.core.models import SessionRow, TokenEventRow
from tokenlens.core.schema import ToolEnum

if TYPE_CHECKING:
    from tokenlens.core.schema import TokenEvent

logger = structlog.get_logger()


class SessionStrategy(Protocol):
    """Protocol for session boundary detection strategies."""

    def should_start_new_session(
        self, event_ts: datetime, session_start: datetime, last_event_ts: datetime
    ) -> bool: ...


class GapBasedStrategy:
    """Existing behavior: new session when gap > session_gap_minutes."""

    def __init__(self, gap: timedelta) -> None:
        self._gap = gap

    def should_start_new_session(
        self, event_ts: datetime, session_start: datetime, last_event_ts: datetime
    ) -> bool:
        return (event_ts - last_event_ts) > self._gap


class RollingWindowStrategy:
    """Claude Code model: session expires 5h after start_time."""

    WINDOW = timedelta(hours=5)

    def should_start_new_session(
        self, event_ts: datetime, session_start: datetime, last_event_ts: datetime
    ) -> bool:
        return event_ts >= session_start + self.WINDOW

    def contains(self, event_ts: datetime, session_start: datetime) -> bool:
        """Return True if event_ts falls within [session_start, session_start + WINDOW)."""
        return session_start <= event_ts < session_start + self.WINDOW


@dataclass
class OpenSession:
    """Tracks an open session's state including its boundary detection strategy."""

    session_id: str
    start_time: datetime
    last_event_time: datetime
    strategy: SessionStrategy = field(repr=False)


class SessionManager:
    """Detects session boundaries and aggregates session stats on close.

    Strategy selection:
    - ``claude_code`` tool → ``RollingWindowStrategy`` (5-hour rolling window,
      supports multiple concurrent sessions).
    - All other tools → ``GapBasedStrategy`` (gap-based, single session per tool).

    A session closes when:
    1. The strategy says a new session should start (gap exceeded or window expired).
    2. The daemon shuts down (``flush_all_open_sessions``).

    Note: For gap-based strategy, a gap of exactly ``session_gap_minutes`` does NOT
    trigger a new session (strictly greater than).
    """

    def __init__(self, session_gap_minutes: int = 15) -> None:
        self._gap = timedelta(minutes=session_gap_minutes)
        self._gap_strategy = GapBasedStrategy(self._gap)
        self._rolling_strategy = RollingWindowStrategy()
        # tool_key → list of open sessions for that tool
        self._open_sessions: dict[str, list[OpenSession]] = {}
        # list of (session_id, tool_key) pending aggregation
        self._pending_closes: list[tuple[str, str]] = []
        self._lock = threading.Lock()

    def _strategy_for_tool(self, tool_key: str) -> SessionStrategy:
        """Return the appropriate strategy for a tool."""
        if tool_key == ToolEnum.CLAUDE_CODE.value:
            return self._rolling_strategy
        return self._gap_strategy

    def _is_rolling(self, tool_key: str) -> bool:
        """Return True if the tool uses the rolling-window strategy."""
        return tool_key == ToolEnum.CLAUDE_CODE.value

    def assign_session_id(self, event: TokenEvent) -> str:
        """Assign a session_id to an event using the tool's strategy.

        For ``claude_code`` (rolling window):
        - Scans all open sessions for the tool.
        - If the event falls within an existing session's 5-hour window, assigns to it.
        - If the event is past all windows, closes expired sessions and starts a new one.
        - Supports multiple concurrent open sessions.

        For other tools (gap-based):
        - Behaves identically to the original gap-based logic.
        - At most one open session per tool.

        Out-of-order events are assigned to the session whose window contains the
        event timestamp, or a new session is started if no window matches.

        Returns the session_id (may be new or existing).
        """
        tool_key = event.tool.value
        now = event.timestamp

        with self._lock:
            sessions = self._open_sessions.get(tool_key, [])

            if self._is_rolling(tool_key):
                return self._assign_rolling(event, tool_key, now, sessions)
            else:
                return self._assign_gap_based(event, tool_key, now, sessions)

    def _assign_rolling(
        self,
        event: TokenEvent,
        tool_key: str,
        now: datetime,
        sessions: list[OpenSession],
    ) -> str:
        """Assign session for rolling-window tools (claude_code).

        Must be called while holding ``self._lock``.
        """
        strategy = self._rolling_strategy

        # 1. Check if event falls within any existing session's window
        for s in sessions:
            if strategy.contains(now, s.start_time):
                s.last_event_time = now
                event.session_id = s.session_id
                return s.session_id

        # 2. No matching window — close expired sessions and start a new one
        still_open: list[OpenSession] = []
        for s in sessions:
            if strategy.should_start_new_session(now, s.start_time, s.last_event_time):
                # Window expired — schedule close
                logger.info(
                    "Rolling window expired for %s. Closing session %s.",
                    tool_key,
                    s.session_id[:8],
                )
                self._pending_closes.append((s.session_id, tool_key))
            else:
                still_open.append(s)

        new_id = str(uuid.uuid4())
        new_session = OpenSession(
            session_id=new_id,
            start_time=now,
            last_event_time=now,
            strategy=strategy,
        )
        still_open.append(new_session)
        self._open_sessions[tool_key] = still_open
        event.session_id = new_id
        return new_id

    def _assign_gap_based(
        self,
        event: TokenEvent,
        tool_key: str,
        now: datetime,
        sessions: list[OpenSession],
    ) -> str:
        """Assign session for gap-based tools (kiro, etc.).

        Must be called while holding ``self._lock``.
        Gap-based tools have at most one open session.
        """
        strategy = self._gap_strategy

        if sessions:
            s = sessions[0]
            if strategy.should_start_new_session(now, s.start_time, s.last_event_time):
                # Gap detected — close old session, start new one
                logger.info(
                    "Session gap detected for %s. Closing session %s.",
                    tool_key,
                    s.session_id[:8],
                )
                self._pending_closes.append((s.session_id, tool_key))
                new_id = str(uuid.uuid4())
                new_session = OpenSession(
                    session_id=new_id,
                    start_time=now,
                    last_event_time=now,
                    strategy=strategy,
                )
                self._open_sessions[tool_key] = [new_session]
                event.session_id = new_id
                return new_id
            else:
                # Same session — update last event time
                s.last_event_time = now
                event.session_id = s.session_id
                return s.session_id
        else:
            # First event for this tool — start new session
            new_id = str(uuid.uuid4())
            new_session = OpenSession(
                session_id=new_id,
                start_time=now,
                last_event_time=now,
                strategy=strategy,
            )
            self._open_sessions[tool_key] = [new_session]
            event.session_id = new_id
            return new_id

    def _schedule_close(self, session_id: str, tool: str) -> None:
        """Mark a session for aggregation."""
        with self._lock:
            self._pending_closes.append((session_id, tool))

    async def close_pending_sessions(self) -> None:
        """Aggregate and persist all pending session closes."""
        while True:
            with self._lock:
                if not self._pending_closes:
                    break
                session_id, tool = self._pending_closes.pop(0)
            await self._aggregate_and_persist(session_id, tool)

    async def flush_all_open_sessions(self) -> None:
        """Close all open sessions (called on daemon shutdown)."""
        for tool_key, sessions in self._open_sessions.items():
            for s in sessions:
                await self._aggregate_and_persist(s.session_id, tool_key)
        self._open_sessions.clear()

    async def _aggregate_and_persist(self, session_id: str, tool: str) -> None:
        """Compute session aggregates from token_events and write to sessions table."""
        async with get_session() as db:
            result = await db.execute(
                select(
                    func.min(TokenEventRow.timestamp).label("start_time"),
                    func.max(TokenEventRow.timestamp).label("end_time"),
                    func.sum(TokenEventRow.input_tokens).label("total_input"),
                    func.sum(TokenEventRow.output_tokens).label("total_output"),
                    func.sum(TokenEventRow.cost_usd).label("total_cost"),
                    func.count(TokenEventRow.id).label("turn_count"),
                ).where(TokenEventRow.session_id == session_id)
            )
            row = result.one_or_none()
            if row is None or row.start_time is None:
                return

            session_row = SessionRow(
                id=session_id,
                tool=tool,
                start_time=row.start_time,
                end_time=row.end_time,
                total_input_tokens=row.total_input or 0,
                total_output_tokens=row.total_output or 0,
                total_cost_usd=row.total_cost or 0.0,
                turn_count=row.turn_count or 0,
            )
            db.add(session_row)
            logger.info(
                "Session %s closed: %d turns, %d tokens, $%.4f",
                session_id[:8],
                session_row.turn_count,
                session_row.total_input_tokens + session_row.total_output_tokens,
                session_row.total_cost_usd,
            )
