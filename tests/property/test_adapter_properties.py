"""Property-based tests for adapter registry.

**Validates: Requirements FR-P1-05.3, FR-P1-05.5**
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import hypothesis.strategies as st
from hypothesis import given, settings

from tokenlens.adapters.base import ToolAdapter
from tokenlens.adapters.registry import AdapterRegistry

if TYPE_CHECKING:
    from pathlib import Path

    from tokenlens.core.schema import TokenEvent


class _MockAdapter(ToolAdapter):
    """Concrete mock adapter for testing."""

    def __init__(self, adapter_name: str, discovers: bool = True) -> None:
        self._name = adapter_name
        self._discovers = discovers

    @property
    def name(self) -> str:
        return self._name

    @property
    def version(self) -> str:
        return "0.0.1"

    def discover(self) -> bool:
        return self._discovers

    def get_log_paths(self) -> list[Path]:
        return []

    def parse_file(self, path: Path) -> list[TokenEvent]:
        return []

    def get_last_processed_position(self, path: Path) -> int:
        return 0


# Strategy: list of (name, discovers) pairs with unique names
adapter_spec_st = st.lists(
    st.tuples(
        st.text(min_size=1, max_size=16, alphabet=st.characters(categories=("L", "N"))),
        st.booleans(),
    ),
    min_size=1,
    max_size=20,
    unique_by=lambda t: t[0],
)


class TestGetAvailableFiltersByDiscover:
    """Property 7: get_available() filters by discover().

    For any set of mock adapters with random discover() results,
    get_available() returns exactly the subset where discover() is True.

    **Validates: Requirements FR-P1-05.3**
    """

    @given(specs=adapter_spec_st)
    @settings(max_examples=100)
    def test_get_available_returns_only_discoverable(
        self, specs: list[tuple[str, bool]]
    ) -> None:
        registry = AdapterRegistry()
        adapters = [_MockAdapter(name, discovers) for name, discovers in specs]
        for adapter in adapters:
            registry.register(adapter)

        available = registry.get_available()
        available_names = {a.name for a in available}
        expected_names = {name for name, discovers in specs if discovers}

        assert available_names == expected_names


class TestFirstRegistrationWins:
    """Property 8: First-registration-wins on name collision.

    Registering two adapters with the same name keeps only the first.

    **Validates: Requirements FR-P1-05.5**
    """

    @given(
        name=st.text(
            min_size=1, max_size=16, alphabet=st.characters(categories=("L", "N"))
        ),
        discovers_first=st.booleans(),
        discovers_second=st.booleans(),
    )
    @settings(max_examples=100)
    def test_first_adapter_kept_on_name_collision(
        self, name: str, discovers_first: bool, discovers_second: bool
    ) -> None:
        registry = AdapterRegistry()
        first = _MockAdapter(name, discovers_first)
        second = _MockAdapter(name, discovers_second)

        registry.register(first)
        registry.register(second)

        result = registry.get(name)
        assert result is first
        assert len(registry.get_all()) == 1
