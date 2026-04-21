"""Model pricing with fuzzy name matching."""

from __future__ import annotations

import re

from tokenlens.core.config import get_pricing_table

# Regex to strip version suffixes and date stamps from model names.
# e.g., "claude-sonnet-4-20250514" → "claude-sonnet-4"
#       "claude-opus-4-v2" → "claude-opus-4"
_VERSION_SUFFIX_RE = re.compile(r"[-_](\d{8}|\d+\.\d+.*|v\d+.*)$")


def normalize_model_name(raw_name: str) -> str:
    """Strip version suffixes and date stamps for fuzzy matching.

    Examples:
        "claude-sonnet-4-20250514" → "claude-sonnet-4"
        "claude-opus-4-v2" → "claude-opus-4"
        "claude-haiku-3.5" → "claude-haiku-3.5" (no change — known key)
    """
    name = raw_name.strip().lower()
    # Iteratively strip trailing version/date suffixes
    while _VERSION_SUFFIX_RE.search(name):
        name = _VERSION_SUFFIX_RE.sub("", name)
    return name


def _resolve_cache_rates(entry: dict[str, float]) -> tuple[float, float]:
    """Return (cache_creation_rate, cache_read_rate) from entry or derived.

    Uses explicit ``cache_creation`` and ``cache_read`` values from the pricing
    entry when present.  Otherwise derives them from the standard input rate:
    ``cache_creation = input × 1.25``, ``cache_read = input × 0.1``.
    """
    input_rate = entry["input"]
    creation = entry.get("cache_creation", input_rate * 1.25)
    read = entry.get("cache_read", input_rate * 0.1)
    return (creation, read)


def _compute_cost(
    entry: dict[str, float],
    input_tokens: int,
    output_tokens: int,
    cache_creation_tokens: int,
    cache_read_tokens: int,
) -> float:
    """Compute total cost in USD from a pricing entry and token counts."""
    cache_creation_rate, cache_read_rate = _resolve_cache_rates(entry)
    return (
        input_tokens * entry["input"] / 1_000_000
        + output_tokens * entry["output"] / 1_000_000
        + cache_creation_tokens * cache_creation_rate / 1_000_000
        + cache_read_tokens * cache_read_rate / 1_000_000
    )


def calculate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_creation_tokens: int = 0,
    cache_read_tokens: int = 0,
) -> tuple[float, bool]:
    """Calculate cost in USD including cache token pricing.

    Cache rates are looked up from the pricing table.  If not present,
    they are derived: cache_creation = input × 1.25, cache_read = input × 0.1.

    Returns (cost, matched).  If the model is not found after fuzzy matching,
    returns (0.0, False).
    """
    pricing = get_pricing_table()
    normalized = normalize_model_name(model)

    # Exact match first
    if normalized in pricing:
        entry = pricing[normalized]
        cost = _compute_cost(
            entry, input_tokens, output_tokens,
            cache_creation_tokens, cache_read_tokens,
        )
        return (cost, True)

    # Try matching against normalized keys
    for key in pricing:
        if normalize_model_name(key) == normalized:
            entry = pricing[key]
            cost = _compute_cost(
                entry, input_tokens, output_tokens,
                cache_creation_tokens, cache_read_tokens,
            )
            return (cost, True)

    return (0.0, False)
