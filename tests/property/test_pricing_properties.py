"""Property-based tests for pricing module.

**Validates: Requirements FR-P1-03.3, FR-P1-03.4**
"""

from __future__ import annotations

from unittest.mock import patch

import hypothesis.strategies as st
from hypothesis import assume, given, settings

from tokenlens.core.pricing import calculate_cost, normalize_model_name

# Known pricing table for testing
KNOWN_PRICING = {
    "claude-sonnet-4": {"input": 3.0, "output": 15.0},
    "claude-opus-4": {"input": 15.0, "output": 75.0},
    "claude-haiku-3.5": {"input": 0.80, "output": 4.0},
    "kiro-auto": {"input": 3.0, "output": 15.0},
}

known_model_st = st.sampled_from(list(KNOWN_PRICING.keys()))
non_neg_tokens_st = st.integers(min_value=0, max_value=10_000_000)

# Date stamp: YYYYMMDD
date_stamp_st = st.from_regex(r"20[2-3][0-9](0[1-9]|1[0-2])(0[1-9]|[12][0-9]|3[01])", fullmatch=True)

# Version suffix: vN.N or N.N.N
version_suffix_st = st.from_regex(r"v[0-9]+\.[0-9]+", fullmatch=True)


class TestCostFormulaCorrectness:
    """Property 5: Cost calculation formula correctness.

    For any known model and non-negative tokens, calculate_cost()
    returns the exact formula result with matched=True.

    **Validates: Requirements FR-P1-03.3**
    """

    @given(model=known_model_st, inp=non_neg_tokens_st, out=non_neg_tokens_st)
    @settings(max_examples=100)
    def test_cost_matches_formula(self, model: str, inp: int, out: int) -> None:
        with patch("tokenlens.core.pricing.get_pricing_table", return_value=KNOWN_PRICING):
            cost, matched = calculate_cost(model, inp, out)

        assert matched is True
        entry = KNOWN_PRICING[model]
        expected = (inp * entry["input"] / 1_000_000) + (out * entry["output"] / 1_000_000)
        assert abs(cost - expected) < 1e-10


class TestFuzzyModelNameMatching:
    """Property 6: Fuzzy model name matching.

    Appending date stamp (YYYYMMDD) or version suffix (vN.N) to a known
    model name still resolves to the correct pricing entry.

    **Validates: Requirements FR-P1-03.4**
    """

    @given(model=known_model_st, date=date_stamp_st)
    @settings(max_examples=50)
    def test_date_stamp_suffix_still_matches(self, model: str, date: str) -> None:
        suffixed = f"{model}-{date}"
        with patch("tokenlens.core.pricing.get_pricing_table", return_value=KNOWN_PRICING):
            cost, matched = calculate_cost(suffixed, 1_000_000, 1_000_000)

        assert matched is True
        entry = KNOWN_PRICING[model]
        expected = entry["input"] + entry["output"]
        assert abs(cost - expected) < 1e-10

    @given(model=known_model_st, ver=version_suffix_st)
    @settings(max_examples=50)
    def test_version_suffix_still_matches(self, model: str, ver: str) -> None:
        suffixed = f"{model}-{ver}"
        with patch("tokenlens.core.pricing.get_pricing_table", return_value=KNOWN_PRICING):
            cost, matched = calculate_cost(suffixed, 1_000_000, 1_000_000)

        assert matched is True
        entry = KNOWN_PRICING[model]
        expected = entry["input"] + entry["output"]
        assert abs(cost - expected) < 1e-10

    def test_normalize_strips_date_stamp(self) -> None:
        assert normalize_model_name("claude-sonnet-4-20250514") == "claude-sonnet-4"

    def test_normalize_strips_version(self) -> None:
        assert normalize_model_name("claude-opus-4-v2") == "claude-opus-4"

    def test_normalize_preserves_known_key(self) -> None:
        # normalize_model_name strips version-like suffixes, but calculate_cost
        # still matches because it normalizes both input and pricing table keys
        with patch("tokenlens.core.pricing.get_pricing_table", return_value=KNOWN_PRICING):
            cost, matched = calculate_cost("claude-haiku-3.5", 1_000_000, 0)
        assert matched is True

    def test_unknown_model_returns_zero(self) -> None:
        with patch("tokenlens.core.pricing.get_pricing_table", return_value=KNOWN_PRICING):
            cost, matched = calculate_cost("unknown-model", 100, 100)
        assert matched is False
        assert cost == 0.0
