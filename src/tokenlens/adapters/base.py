"""Abstract base class for tool adapters.

Adapter methods are SYNCHRONOUS. The daemon wraps calls in
asyncio.to_thread() to avoid blocking the event loop.

File watching is handled by the daemon's watchdog, not by adapters.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from tokenlens.core.schema import TokenEvent


class ToolAdapter(ABC):
    """Abstract base class for all tool adapters.

    Adapter methods are SYNCHRONOUS. The daemon wraps calls in
    asyncio.to_thread() to avoid blocking the event loop.

    File watching is handled by the daemon's watchdog, not by adapters.
    Adapters are responsible for: discover(), get_log_paths(), parse_file().
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique adapter name (e.g., 'claude_code', 'kiro')."""
        ...

    @property
    @abstractmethod
    def version(self) -> str:
        """Semantic version string of this adapter."""
        ...

    @abstractmethod
    def discover(self) -> bool:
        """Return True if this tool's log files exist on the local machine."""
        ...

    @abstractmethod
    def get_log_paths(self) -> list[Path]:
        """Return all log file paths this adapter can parse."""
        ...

    @abstractmethod
    def parse_file(self, path: Path) -> list[TokenEvent]:
        """Parse a log file and return TokenEvents.

        Raises:
            FileNotFoundError: If path does not exist.
        """
        ...

    @abstractmethod
    def get_last_processed_position(self, path: Path) -> int:
        """Return the byte offset of the last processed position for a file."""
        ...

    def set_position(self, path: Path, offset: int) -> None:  # noqa: B027
        """Restore a previously saved byte offset for a file.

        Called by the daemon on startup to resume from where it left off.
        Default implementation is a no-op. Adapters that track file positions
        should override this.
        """

    # NOTE: watch() is NOT part of the adapter interface.
    # File watching is a daemon concern (via watchdog), not an adapter concern.
    # The adapter's job is: discover(), get_log_paths(), parse_file().
