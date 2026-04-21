"""Session window calculation utilities for the 5-hour rolling window model.

Each session is a 5-hour rolling window. A new session begins whenever
there is a gap of 5 or more hours between consecutive events, or when the
adapter records a new native session identifier.

Public surface
--------------
SESSION_DURATION          : timedelta constant (5 hours)
SessionCalculator         : class — all per-session metrics live here
find_current_session_start: async helper used by the WebSocket push loop
get_session_stats         : async helper — returns the full metrics dict
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, text

from tokenlens.core.models import TokenEventRow

logger = logging.getLogger(__name__)

SESSION_DURATION = timedelta(hours=5)


# ---------------------------------------------------------------------------
# Data container
# ---------------------------------------------------------------------------

@dataclass
class SessionMetrics:
    """All computed metrics for the current session window."""

    # Raw DB aggregates
    session_tokens: int = 0
    session_cost: float = 0.0
    session_messages: int = 0

    # Window boundaries
    session_start: datetime | None = None
    session_end: datetime | None = None
    first_event: datetime | None = None

    # Rates
    burn_rate_per_min: float = 0.0   # tokens/min  (last-60-min window)
    cost_rate_per_min: float = 0.0   # $/min       (session average)

    # Limits & usage
    token_limit: int = 0
    tokens_remaining: int = 0
    usage_pct: float = 0.0           # 0–100

    # Prediction
    tokens_exhaust_at: datetime | None = None

    # Plan
    plan_type: str = "custom"

    def to_dict(self) -> dict:
        """Serialize to the dict format expected by the WebSocket push."""
        return {
            "session_tokens": self.session_tokens,
            "session_cost": self.session_cost,
            "session_messages": self.session_messages,
            "session_start": self.session_start.isoformat() if self.session_start else None,
            "session_reset": self.session_end.isoformat() if self.session_end else None,
            "first_event": self.first_event.isoformat() if self.first_event else None,
            "token_limit": self.token_limit,
            "plan_type": self.plan_type,
            "burn_rate_per_min": round(self.burn_rate_per_min, 1),
            "cost_rate_per_min": round(self.cost_rate_per_min, 4),
            "tokens_exhaust_at": self.tokens_exhaust_at.isoformat() if self.tokens_exhaust_at else None,
            "usage_pct": round(self.usage_pct, 1),
        }


# ---------------------------------------------------------------------------
# Calculator class
# ---------------------------------------------------------------------------

class SessionCalculator:
    """Computes all session-window metrics from raw DB data.

    Each public method is responsible for exactly one metric so that
    individual calculations can be tested and debugged in isolation.

    Typical call sequence (see get_session_stats below):
        calc = SessionCalculator(session_start)
        m    = SessionMetrics()
        await calc.load_session_aggregates(m)
        await calc.compute_burn_rate(m)
        calc.compute_cost_rate(m)
        calc.compute_usage_pct(m)
        calc.compute_exhaust_prediction(m)
    """

    def __init__(self, session_start: datetime) -> None:
        self.session_start: datetime = session_start
        self.session_end: datetime = session_start + SESSION_DURATION
        self.now: datetime = datetime.now(UTC)

    # ------------------------------------------------------------------
    # Step 1 — load raw DB aggregates for the session window
    # ------------------------------------------------------------------

    async def load_session_aggregates(self, m: SessionMetrics) -> None:
        """Query total tokens, cost, messages and event boundary timestamps
        for all events that fall inside the current 5-hour window."""
        from tokenlens.core.database import get_session as db_session

        async with db_session() as db:
            result = await db.execute(
                select(
                    func.sum(
                        TokenEventRow.input_tokens + TokenEventRow.output_tokens
                    ).label("tokens"),
                    func.sum(TokenEventRow.cost_usd).label("cost"),
                    func.count(TokenEventRow.id).label("messages"),
                    func.min(TokenEventRow.timestamp).label("first_event"),
                )
                .where(
                    TokenEventRow.timestamp >= self.session_start,
                    TokenEventRow.timestamp < self.session_end,
                )
            )
            row = result.one()

        m.session_tokens = int(row.tokens or 0)
        m.session_cost = round(float(row.cost or 0), 4)
        m.session_messages = int(row.messages or 0)
        m.session_start = self.session_start
        m.session_end = self.session_end

        if row.first_event:
            ts = row.first_event
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=UTC)
            m.first_event = ts

    # ------------------------------------------------------------------
    # Step 2 — burn rate  (tokens/min over the trailing 60-minute window)
    # ------------------------------------------------------------------

    async def compute_burn_rate(self, m: SessionMetrics) -> None:
        """Compute burn rate as: tokens consumed in the last 60 minutes / 60.

        Using a fixed 60-minute trailing window produces a stable, intuitive
        rate that reflects recent activity rather than a diluted session
        average. A session that has been idle for hours will show a low
        rate; one that is actively running will show a high rate.
        """
        from tokenlens.core.database import get_session as db_session

        one_hour_ago = self.now - timedelta(hours=1)

        async with db_session() as db:
            result = await db.execute(
                select(
                    func.sum(
                        TokenEventRow.input_tokens + TokenEventRow.output_tokens
                    ).label("hourly_tokens")
                )
                .where(
                    TokenEventRow.timestamp >= one_hour_ago,
                    TokenEventRow.timestamp < self.session_end,
                )
            )
            row = result.one()

        hourly_tokens = int(row.hourly_tokens or 0)
        m.burn_rate_per_min = hourly_tokens / 60.0

    # ------------------------------------------------------------------
    # Step 3 — cost rate  ($/min, session average)
    # ------------------------------------------------------------------

    def compute_cost_rate(self, m: SessionMetrics) -> None:
        """Compute cost velocity as: total session cost / elapsed session minutes.

        Elapsed minutes is measured from session_start to now (wall-clock),
        clamped to a minimum of 1 minute to avoid division by zero at the
        very start of a new session.
        """
        elapsed_minutes = max(
            (self.now - self.session_start).total_seconds() / 60, 1
        )
        m.cost_rate_per_min = (
            m.session_cost / elapsed_minutes if elapsed_minutes > 0 else 0.0
        )

    # ------------------------------------------------------------------
    # Step 4 — token limit & usage percentage
    # ------------------------------------------------------------------

    def compute_usage_pct(self, m: SessionMetrics) -> None:
        """Populate token_limit, tokens_remaining and usage_pct fields.

        token_limit  — resolved from plan config (pro / max5 / max20 / custom).
        usage_pct    — 0–100 percentage of the limit consumed so far.
        """
        from tokenlens.core.config import get_effective_daily_token_limit, get_plan_type

        m.token_limit = get_effective_daily_token_limit()
        m.tokens_remaining = max(m.token_limit - m.session_tokens, 0)
        m.plan_type = get_plan_type()
        m.usage_pct = (
            (m.session_tokens / m.token_limit * 100) if m.token_limit > 0 else 0.0
        )

    # ------------------------------------------------------------------
    # Step 5 — exhaust prediction
    # ------------------------------------------------------------------

    def compute_exhaust_prediction(self, m: SessionMetrics) -> None:
        """Predict the time at which the token limit will be reached.

        Prediction is shown when:
          - The burn rate is positive AND tokens remain, AND
          - Either the predicted exhaust falls inside the session window,
            OR the current usage is already at or above 70 % of the limit
            (warning mode — user may hit the limit even if reset comes first).

        The result is stored as a UTC datetime in m.tokens_exhaust_at.
        """
        if m.burn_rate_per_min <= 0 or m.tokens_remaining <= 0:
            m.tokens_exhaust_at = None
            return

        minutes_to_exhaust = m.tokens_remaining / m.burn_rate_per_min
        exhaust_dt = self.now + timedelta(minutes=minutes_to_exhaust)

        inside_window = exhaust_dt < self.session_end
        near_limit = m.usage_pct >= 70

        m.tokens_exhaust_at = exhaust_dt if (inside_window or near_limit) else None


# ---------------------------------------------------------------------------
# Session-start detection helpers
# ---------------------------------------------------------------------------

def _round_to_hour(ts: datetime) -> datetime:
    """Truncate a timezone-aware datetime to the start of its UTC hour."""
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    return ts.replace(minute=0, second=0, microsecond=0)


def _ensure_utc(ts: datetime) -> datetime:
    """Return ts with UTC tzinfo, adding it if missing."""
    return ts if ts.tzinfo else ts.replace(tzinfo=UTC)


async def _find_start_by_native_session_id() -> datetime | None:
    """Primary detection strategy: use the adapter's native session identifier.

    The adapter stores a per-conversation identifier inside raw_metadata
    under the key 'claude_session_id'. We fetch the most recent event's
    identifier, then find the earliest event sharing that same identifier.
    That timestamp (rounded to the hour) is the session start.

    Returns None when no session identifier is present so the caller can
    fall through to the gap-detection strategy.
    """
    from tokenlens.core.database import get_session as db_session

    async with db_session() as db:
        row = (await db.execute(
            text("SELECT raw_metadata FROM token_events ORDER BY timestamp DESC LIMIT 1")
        )).fetchone()

    if not row:
        return None

    try:
        meta = json.loads(row[0]) if isinstance(row[0], str) else (row[0] or {})
        session_id = meta.get("claude_session_id", "")
    except Exception:
        return None

    if not session_id:
        return None

    async with db_session() as db:
        earliest = (await db.execute(
            text(
                "SELECT MIN(timestamp) FROM token_events "
                "WHERE json_extract(raw_metadata, '$.claude_session_id') = :sid"
            ),
            {"sid": session_id},
        )).scalar()

    if not earliest:
        return None

    if isinstance(earliest, str):
        earliest = datetime.fromisoformat(earliest)

    return _round_to_hour(_ensure_utc(earliest))


async def _find_start_by_gap_detection() -> datetime:
    """Fallback detection strategy: locate the most recent session boundary via SQL.

    A session boundary is any event preceded by a gap of ≥ SESSION_DURATION,
    or the very first recorded event (no predecessor). Among all such
    boundary candidates within a 10-hour lookback window, we select the
    most recent one — that is the start of the current active session.

    The detection is done entirely inside the database using a CTE with the
    LAG window function, so no timestamp list is fetched into Python memory:

        ordered_events  — all events in the lookback window, with each row's
                          predecessor timestamp attached via LAG() ASC
        session_boundaries — rows where predecessor is absent (first event)
                             or the gap to predecessor ≥ SESSION_DURATION
        result          — MAX(timestamp) of all boundary candidates

    JULIANDAY arithmetic gives the gap in fractional days; multiplying by
    24.0 converts to hours for the threshold comparison.

    Returns the boundary timestamp truncated to its UTC hour.  If no events
    exist in the window at all, the current UTC hour is returned as the
    start of a brand-new session.
    """
    from tokenlens.core.database import get_session as db_session

    now = datetime.now(UTC)
    lookback = now - (SESSION_DURATION * 2)
    gap_hours = SESSION_DURATION.total_seconds() / 3600.0

    sql = text(
        """
        WITH ordered_events AS (
            SELECT timestamp,
                   LAG(timestamp) OVER (ORDER BY timestamp ASC) AS prev_timestamp
            FROM token_events
            WHERE timestamp >= :lookback
        ),
        session_boundaries AS (
            SELECT timestamp
            FROM ordered_events
            WHERE prev_timestamp IS NULL
               OR (JULIANDAY(timestamp) - JULIANDAY(prev_timestamp)) * 24.0 >= :gap_hours
        )
        SELECT MAX(timestamp) AS session_start
        FROM session_boundaries
        """
    )

    async with db_session() as db:
        result = (await db.execute(sql, {"lookback": lookback.isoformat(), "gap_hours": gap_hours})).scalar()

    if not result:
        return _round_to_hour(now)

    if isinstance(result, str):
        result = datetime.fromisoformat(result)

    return _round_to_hour(_ensure_utc(result))


# ---------------------------------------------------------------------------
# Public async API
# ---------------------------------------------------------------------------

async def find_current_session_start() -> datetime:
    """Resolve the start timestamp of the active 5-hour session window.

    Two strategies are attempted in order:

    1. Native session identifier — looks up the 'claude_session_id' stored
       in raw_metadata for the most recent event, then finds the earliest
       event sharing that identifier. This is the most precise approach
       because it uses the identifier that the adapter itself assigns to
       each conversation.

    2. Gap-based detection — scans the last 10 hours of timestamps and
       locates the most recent gap of ≥ 5 hours between consecutive events.
       Everything after the gap belongs to the current session.

    In both cases the result is truncated to the start of its UTC hour,
    matching the hour-boundary alignment used by the 5-hour rolling window.
    """
    result = await _find_start_by_native_session_id()
    if result is not None:
        return result

    return await _find_start_by_gap_detection()


def get_current_session_start(first_event_ts: datetime | None = None) -> datetime:
    """Synchronous convenience wrapper used when the caller already holds
    the first event timestamp (e.g., the CLI status command).

    Prefer find_current_session_start() for accuracy when the timestamp
    is not already known.
    """
    now = datetime.now(UTC)
    if first_event_ts is None:
        return _round_to_hour(now)

    ts = _ensure_utc(first_event_ts)
    start = _round_to_hour(ts)

    if now >= start + SESSION_DURATION:
        return _round_to_hour(now)

    return start


def get_session_reset_time(session_start: datetime) -> datetime:
    """Return the expiry time of the session that started at session_start."""
    return session_start + SESSION_DURATION


async def get_session_stats(session_start: datetime) -> dict:
    """Compute and return all session-window metrics as a plain dict.

    This is the single entry point called by the WebSocket push loop.
    Internally it delegates every calculation to SessionCalculator so
    that each metric has one well-defined place where it is computed.
    """
    calc = SessionCalculator(session_start)
    m = SessionMetrics()

    await calc.load_session_aggregates(m)   # Step 1 — DB aggregates
    await calc.compute_burn_rate(m)         # Step 2 — tokens/min
    calc.compute_cost_rate(m)               # Step 3 — $/min
    calc.compute_usage_pct(m)              # Step 4 — limit & %
    calc.compute_exhaust_prediction(m)     # Step 5 — exhaust time

    return m.to_dict()
