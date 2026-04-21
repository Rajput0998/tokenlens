"""File watcher using watchdog for log directory monitoring.

Uses native OS file watching (inotify on Linux, FSEvents on macOS).
Falls back to periodic full-scan every N minutes.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

import structlog
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

if TYPE_CHECKING:
    from collections.abc import Callable

logger = structlog.get_logger()


class LogFileHandler(FileSystemEventHandler):
    """Watchdog handler that triggers callback on .jsonl file modifications."""

    def __init__(self, callback: Callable[[Path], None]) -> None:
        self._callback = callback

    def on_modified(self, event: object) -> None:
        """Filter for .jsonl files only, then call the callback."""
        if getattr(event, "is_directory", False):
            return
        src_path = getattr(event, "src_path", None)
        if src_path is None:
            return
        path = Path(src_path)
        if path.suffix == ".jsonl":
            self._callback(path)


class FileWatcher:
    """Manages watchdog observers for all adapter log directories.

    Uses native OS file watching (inotify on Linux, FSEvents on macOS).
    Falls back to periodic full-scan every `full_scan_interval_minutes` minutes.
    """

    def __init__(
        self,
        on_file_changed: Callable[[Path], None],
        full_scan_interval_minutes: int = 5,
    ) -> None:
        self._on_file_changed = on_file_changed
        self._full_scan_interval = full_scan_interval_minutes * 60
        self._observer = Observer()
        self._watched_dirs: set[str] = set()

    def watch_directory(self, directory: Path) -> None:
        """Add a directory to the watchdog observer. Skips if already watched."""
        str_dir = str(directory)
        if str_dir in self._watched_dirs:
            return
        handler = LogFileHandler(self._on_file_changed)
        self._observer.schedule(handler, str_dir, recursive=True)
        self._watched_dirs.add(str_dir)
        logger.info("Watching directory: %s", directory)

    def start(self) -> None:
        """Start the watchdog observer."""
        self._observer.start()

    def stop(self) -> None:
        """Stop the watchdog observer."""
        self._observer.stop()
        self._observer.join(timeout=5)

    async def periodic_full_scan(
        self,
        scan_callback: Callable[[], None],
        shutdown_event: asyncio.Event,
    ) -> None:
        """Run a full scan every N minutes as a fallback.

        Respects shutdown_event — exits when set.
        """
        while not shutdown_event.is_set():
            try:
                await asyncio.wait_for(
                    shutdown_event.wait(),
                    timeout=self._full_scan_interval,
                )
            except TimeoutError:
                logger.debug("Running periodic full scan.")
                await asyncio.to_thread(scan_callback)
