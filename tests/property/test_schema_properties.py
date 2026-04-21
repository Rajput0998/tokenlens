"""Property-based tests for TokenEvent schema.

**Validates: Requirements FR-P1-01.1, FR-P1-01.6**
"""

from __future__ import annotations

from datetime import UTC, datetime

import hypothesis.strategies as st
from hypothesis import given, settings

from tokenlens.core.schema import ContextType, TokenEvent, ToolEnum

# --- Hypothesis strategies ---

tool_enum_st = st.sampled_from(list(ToolEnum))
context_type_st = st.sampled_from(list(ContextType))

aware_datetime_st = st.datetimes(
    min_value=datetime(2020, 1, 1),
    max_value=datetime(2030, 12, 31),
    timezones=st.just(UTC),
)

token_event_st = st.builds(
    TokenEvent,
    tool=tool_enum_st,
    model=st.text(min_size=1, max_size=64, alphabet=st.characters(categories=("L", "N", "P"))),
    user_id=st.text(min_size=1, max_size=32, alphabet=st.characters(categories=("L", "N"))),
    timestamp=aware_datetime_st,
    input_tokens=st.integers(min_value=0, max_value=10_000_000),
    output_tokens=st.integers(min_value=0, max_value=10_000_000),
    cost_usd=st.floats(min_value=0.0, max_value=1000.0, allow_nan=False, allow_infinity=False),
    context_type=context_type_st,
    turn_number=st.integers(min_value=0, max_value=10_000),
    cache_read_tokens=st.integers(min_value=0, max_value=1_000_000),
    cache_write_tokens=st.integers(min_value=0, max_value=1_000_000),
)


class TestTokenEventRoundTrip:
    """Property 1: TokenEvent JSON round-trip.

    **Validates: Requirements FR-P1-01.1, FR-P1-01.6**
    """

    @given(event=token_event_st)
    @settings(max_examples=100)
    def test_json_round_trip_produces_equivalent_object(self, event: TokenEvent) -> None:
        """Serializing via model_dump_json() then deserializing via
        model_validate_json() produces an equivalent object."""
        json_str = event.model_dump_json()
        restored = TokenEvent.model_validate_json(json_str)

        assert restored.id == event.id
        assert restored.tool == event.tool
        assert restored.model == event.model
        assert restored.user_id == event.user_id
        assert restored.session_id == event.session_id
        assert restored.timestamp == event.timestamp
        assert restored.input_tokens == event.input_tokens
        assert restored.output_tokens == event.output_tokens
        assert restored.context_type == event.context_type
        assert restored.turn_number == event.turn_number
        assert restored.cache_read_tokens == event.cache_read_tokens
        assert restored.cache_write_tokens == event.cache_write_tokens
        assert restored.file_types_in_context == event.file_types_in_context
        assert restored.tool_calls == event.tool_calls
        assert restored.raw_metadata == event.raw_metadata
        assert restored.source_file_path == event.source_file_path
        assert restored.file_byte_offset == event.file_byte_offset
