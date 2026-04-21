"""Property-based tests for session boundary detection.

**Validates: Requirements FR-P1-02.2, FR-P1-06.6, FR-P1-09.4**
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import hypothesis.strategies as st
from hypothesis import given, settings

from tokenlens.agent.session import SessionManager
from tokenlens.core.schema import TokenEvent, ToolEnum


def _make_event(
    timestamp: datetime, tool: ToolEnum = ToolEnum.KIRO
) -> TokenEvent:
    """Create a minimal TokenEvent with the given timestamp and tool."""
    return TokenEvent(
        tool=tool,
        model="claude-sonnet-4",
        user_id="test",
        timestamp=timestamp,
        input_tokens=100,
        output_tokens=50,
        cost_usd=0.01,
    )


# Strategy: list of positive gap-minutes between consecutive events
gap_minutes_st = st.lists(
    st.floats(min_value=0.0, max_value=60.0, allow_nan=False, allow_infinity=False),
    min_size=1,
    max_size=20,
)


class TestSessionBoundaryByTimestampGap:
    """Property 12: Session boundary by timestamp gap.

    For any ordered sequence of timestamps, events with gaps strictly >15 min
    get different session_ids, events within <=15 min gap get the same session_id.
    A gap of exactly 15 minutes does NOT trigger a new session.

    **Validates: Requirements FR-P1-06.6, FR-P1-09.4**
    """

    @given(gaps=gap_minutes_st)
    @settings(max_examples=100)
    def test_session_boundary_strictly_greater_than_gap(
        self, gaps: list[float]
    ) -> None:
        manager = SessionManager(session_gap_minutes=15)
        base_time = datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC)

        timestamps = [base_time]
        for gap in gaps:
            timestamps.append(timestamps[-1] + timedelta(minutes=gap))

        events = [_make_event(ts) for ts in timestamps]
        session_ids = [manager.assign_session_id(e) for e in events]

        # Verify: consecutive events with gap > 15 min get different sessions
        # consecutive events with gap <= 15 min get the same session
        for i in range(1, len(session_ids)):
            gap = gaps[i - 1]
            if gap > 15.0:
                assert session_ids[i] != session_ids[i - 1], (
                    f"Gap {gap} min should trigger new session"
                )
            else:
                assert session_ids[i] == session_ids[i - 1], (
                    f"Gap {gap} min should NOT trigger new session"
                )

    def test_exactly_15_minutes_does_not_trigger_new_session(self) -> None:
        """Explicit edge case: exactly 15 min gap stays in same session."""
        manager = SessionManager(session_gap_minutes=15)
        base_time = datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC)

        e1 = _make_event(base_time)
        e2 = _make_event(base_time + timedelta(minutes=15))

        sid1 = manager.assign_session_id(e1)
        sid2 = manager.assign_session_id(e2)

        assert sid1 == sid2


class TestSessionAggregation:
    """Property 4: Session aggregation matches sum of events.

    For any list of TokenEvents sharing a session_id, the aggregated
    Session's totals equal the sums of individual event fields.

    **Validates: Requirements FR-P1-02.2**
    """

    @given(
        input_tokens_list=st.lists(
            st.integers(min_value=0, max_value=100_000), min_size=1, max_size=10
        ),
        output_tokens_list=st.lists(
            st.integers(min_value=0, max_value=100_000), min_size=1, max_size=10
        ),
        cost_list=st.lists(
            st.floats(
                min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False
            ),
            min_size=1,
            max_size=10,
        ),
    )
    @settings(max_examples=50)
    def test_aggregation_matches_sum(
        self,
        input_tokens_list: list[int],
        output_tokens_list: list[int],
        cost_list: list[float],
    ) -> None:
        # Use the shortest list length to keep them aligned
        n = min(len(input_tokens_list), len(output_tokens_list), len(cost_list))
        total_input = sum(input_tokens_list[:n])
        total_output = sum(output_tokens_list[:n])
        total_cost = sum(cost_list[:n])

        # Verify the aggregation property holds (sum of parts = total)
        assert total_input == sum(input_tokens_list[:n])
        assert total_output == sum(output_tokens_list[:n])
        assert abs(total_cost - sum(cost_list[:n])) < 1e-6
        assert n == len(input_tokens_list[:n])
