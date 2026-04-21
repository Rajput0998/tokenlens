"""Property-based tests for schema validation rules.

**Validates: Requirements FR-P1-01.3, FR-P1-01.4, FR-P1-01.5**
"""

from __future__ import annotations

from datetime import UTC, datetime

import hypothesis.strategies as st
import pytest
from hypothesis import given, settings
from pydantic import ValidationError

from tokenlens.core.schema import TokenEvent, ToolEnum


# Minimal valid kwargs for constructing a TokenEvent
def _valid_kwargs() -> dict:
    return {
        "tool": ToolEnum.CLAUDE_CODE,
        "model": "claude-sonnet-4",
        "user_id": "user1",
        "timestamp": datetime.now(UTC),
        "input_tokens": 100,
        "output_tokens": 50,
    }


class TestNegativeValuesRejected:
    """Property 2: Negative values rejected for token counts and cost.

    **Validates: Requirements FR-P1-01.4, FR-P1-01.5**
    """

    @given(neg=st.integers(max_value=-1))
    @settings(max_examples=50)
    def test_negative_input_tokens_rejected(self, neg: int) -> None:
        kwargs = _valid_kwargs()
        kwargs["input_tokens"] = neg
        with pytest.raises(ValidationError):
            TokenEvent(**kwargs)

    @given(neg=st.integers(max_value=-1))
    @settings(max_examples=50)
    def test_negative_output_tokens_rejected(self, neg: int) -> None:
        kwargs = _valid_kwargs()
        kwargs["output_tokens"] = neg
        with pytest.raises(ValidationError):
            TokenEvent(**kwargs)

    @given(neg=st.floats(max_value=-0.01, allow_nan=False, allow_infinity=False))
    @settings(max_examples=50)
    def test_negative_cost_usd_rejected(self, neg: float) -> None:
        kwargs = _valid_kwargs()
        kwargs["cost_usd"] = neg
        with pytest.raises(ValidationError):
            TokenEvent(**kwargs)

    @given(neg=st.integers(max_value=-1))
    @settings(max_examples=50)
    def test_negative_cache_read_tokens_rejected(self, neg: int) -> None:
        kwargs = _valid_kwargs()
        kwargs["cache_read_tokens"] = neg
        with pytest.raises(ValidationError):
            TokenEvent(**kwargs)

    @given(neg=st.integers(max_value=-1))
    @settings(max_examples=50)
    def test_negative_cache_write_tokens_rejected(self, neg: int) -> None:
        kwargs = _valid_kwargs()
        kwargs["cache_write_tokens"] = neg
        with pytest.raises(ValidationError):
            TokenEvent(**kwargs)


class TestMissingRequiredFields:
    """Property 3: Missing required field raises ValidationError.

    **Validates: Requirements FR-P1-01.3**
    """

    REQUIRED_FIELDS = ["tool", "model", "user_id", "timestamp", "input_tokens", "output_tokens"]

    @given(field=st.sampled_from(REQUIRED_FIELDS))
    @settings(max_examples=20)
    def test_omitting_required_field_raises_validation_error(self, field: str) -> None:
        kwargs = _valid_kwargs()
        del kwargs[field]
        with pytest.raises(ValidationError) as exc_info:
            TokenEvent(**kwargs)
        # The error should mention the missing field
        error_fields = [e["loc"][0] for e in exc_info.value.errors()]
        assert field in error_fields
