"""Property-based tests for EfficiencyEngine scoring.

**Validates: Requirements FR-P2-03.1, FR-P2-03.2**
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from tokenlens.ml.efficiency import EfficiencyEngine

engine = EfficiencyEngine()


# ---------------------------------------------------------------------------
# Property 15: Efficiency score always 0-100
# ---------------------------------------------------------------------------


@given(
    output_input_ratio=st.floats(min_value=-1.0, max_value=10.0, allow_nan=False, allow_infinity=False),
    cache_hit_rate=st.floats(min_value=-1.0, max_value=5.0, allow_nan=False, allow_infinity=False),
    turn_count=st.integers(min_value=-10, max_value=200),
    context_growth_slope=st.floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    cost_per_output_token=st.floats(min_value=-0.01, max_value=0.01, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=500)
def test_property_15_score_always_0_to_100(
    output_input_ratio: float,
    cache_hit_rate: float,
    turn_count: int,
    context_growth_slope: float,
    cost_per_output_token: float,
) -> None:
    """**Validates: Requirements FR-P2-03.1**

    Property 15: For any combination of the 5 input dimensions,
    the weighted efficiency score is always in [0, 100].
    """
    result = engine.score_session({
        "output_input_ratio": output_input_ratio,
        "cache_hit_rate": cache_hit_rate,
        "turn_count": turn_count,
        "context_growth_slope": context_growth_slope,
        "cost_per_output_token": cost_per_output_token,
    })
    assert 0.0 <= result["score"] <= 100.0, (
        f"Score {result['score']} out of [0, 100] range for inputs: "
        f"oi={output_input_ratio}, cache={cache_hit_rate}, turns={turn_count}, "
        f"growth={context_growth_slope}, cost={cost_per_output_token}"
    )


# ---------------------------------------------------------------------------
# Property 16: Higher output/input ratio → higher score (monotonicity)
# ---------------------------------------------------------------------------


@given(
    ratio_low=st.floats(min_value=0.0, max_value=0.49, allow_nan=False, allow_infinity=False),
    ratio_high=st.floats(min_value=0.0, max_value=0.5, allow_nan=False, allow_infinity=False),
    cache_hit_rate=st.floats(min_value=0.0, max_value=0.5, allow_nan=False, allow_infinity=False),
    turn_count=st.integers(min_value=5, max_value=50),
    context_growth_slope=st.floats(min_value=0.01, max_value=0.10, allow_nan=False, allow_infinity=False),
    cost_per_output_token=st.floats(min_value=0.0001, max_value=0.001, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=500)
def test_property_16_higher_ratio_higher_score(
    ratio_low: float,
    ratio_high: float,
    cache_hit_rate: float,
    turn_count: int,
    context_growth_slope: float,
    cost_per_output_token: float,
) -> None:
    """**Validates: Requirements FR-P2-03.2**

    Property 16: Higher output/input ratio → higher or equal score,
    when all other factors are held constant.
    """
    # Ensure ratio_high >= ratio_low
    if ratio_high < ratio_low:
        ratio_low, ratio_high = ratio_high, ratio_low

    base_data = {
        "cache_hit_rate": cache_hit_rate,
        "turn_count": turn_count,
        "context_growth_slope": context_growth_slope,
        "cost_per_output_token": cost_per_output_token,
    }

    result_low = engine.score_session({**base_data, "output_input_ratio": ratio_low})
    result_high = engine.score_session({**base_data, "output_input_ratio": ratio_high})

    assert result_high["score"] >= result_low["score"], (
        f"Monotonicity violated: ratio {ratio_high} scored {result_high['score']} "
        f"< ratio {ratio_low} scored {result_low['score']}"
    )
