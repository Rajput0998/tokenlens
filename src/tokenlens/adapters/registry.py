"""Adapter registry for discovering and managing tool adapters.

Built-in adapters are registered explicitly.
Community adapters are discovered via Python entry_points.
"""

from __future__ import annotations

import importlib.metadata
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tokenlens.adapters.base import ToolAdapter

logger = logging.getLogger(__name__)

ENTRY_POINT_GROUP = "tokenlens.adapters"


class AdapterRegistry:
    """Discovers and manages tool adapters.

    Built-in adapters are registered explicitly.
    Community adapters are discovered via Python entry_points.
    """

    def __init__(self) -> None:
        self._adapters: dict[str, ToolAdapter] = {}

    def register(self, adapter: ToolAdapter) -> None:
        """Register an adapter. First registration wins on name collision."""
        if adapter.name in self._adapters:
            logger.warning(
                "Adapter '%s' already registered — keeping first. "
                "Ignoring duplicate from %s.",
                adapter.name,
                type(adapter).__name__,
            )
            return
        self._adapters[adapter.name] = adapter
        logger.info("Registered adapter: %s (v%s)", adapter.name, adapter.version)

    def discover_entry_points(self) -> None:
        """Load adapters from Python entry_points under 'tokenlens.adapters'."""
        eps = importlib.metadata.entry_points()
        group = (
            eps.select(group=ENTRY_POINT_GROUP)
            if hasattr(eps, "select")
            else eps.get(ENTRY_POINT_GROUP, [])
        )
        for ep in group:
            try:
                adapter_cls = ep.load()
                adapter = adapter_cls()
                self.register(adapter)
            except Exception:
                logger.warning(
                    "Failed to load adapter entry_point '%s'. Skipping.",
                    ep.name,
                    exc_info=True,
                )

    def load_builtins(self) -> None:
        """Register built-in adapters (Claude Code)."""
        from tokenlens.adapters.claude_code import ClaudeCodeAdapter

        self.register(ClaudeCodeAdapter())

    def get_all(self) -> list[ToolAdapter]:
        """Return all registered adapters."""
        return list(self._adapters.values())

    def get_available(self) -> list[ToolAdapter]:
        """Return only adapters whose discover() returns True."""
        available = []
        for adapter in self._adapters.values():
            try:
                if adapter.discover():
                    available.append(adapter)
            except Exception:
                logger.warning(
                    "Adapter '%s' discover() raised an exception. Skipping.",
                    adapter.name,
                    exc_info=True,
                )
        return available

    def get(self, name: str) -> ToolAdapter | None:
        """Lookup adapter by name."""
        return self._adapters.get(name)
