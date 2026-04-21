"""Unit tests for FileWatcher and LogFileHandler.

Tests JSONL filtering, duplicate directory skipping, and periodic scan shutdown.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from tokenlens.agent.watcher import FileWatcher, LogFileHandler


class TestLogFileHandlerFiltering:
    """Test that LogFileHandler.on_modified() filters non-JSONL files."""

    def test_jsonl_file_triggers_callback(self) -> None:
        callback = MagicMock()
        handler = LogFileHandler(callback)

        event = SimpleNamespace(is_directory=False, src_path="/tmp/test.jsonl")
        handler.on_modified(event)

        callback.assert_called_once_with(Path("/tmp/test.jsonl"))

    def test_non_jsonl_file_does_not_trigger_callback(self) -> None:
        callback = MagicMock()
        handler = LogFileHandler(callback)

        event = SimpleNamespace(is_directory=False, src_path="/tmp/test.txt")
        handler.on_modified(event)

        callback.assert_not_called()

    def test_directory_event_does_not_trigger_callback(self) -> None:
        callback = MagicMock()
        handler = LogFileHandler(callback)

        event = SimpleNamespace(is_directory=True, src_path="/tmp/logs")
        handler.on_modified(event)

        callback.assert_not_called()

    def test_json_file_does_not_trigger_callback(self) -> None:
        callback = MagicMock()
        handler = LogFileHandler(callback)

        event = SimpleNamespace(is_directory=False, src_path="/tmp/test.json")
        handler.on_modified(event)

        callback.assert_not_called()


class TestWatchDirectorySkipsDuplicates:
    """Test that watch_directory() skips already-watched directories."""

    def test_same_directory_not_watched_twice(self, tmp_path: Path) -> None:
        callback = MagicMock()
        watcher = FileWatcher(on_file_changed=callback)

        watcher.watch_directory(tmp_path)
        watcher.watch_directory(tmp_path)

        assert len(watcher._watched_dirs) == 1

    def test_different_directories_both_watched(self, tmp_path: Path) -> None:
        callback = MagicMock()
        watcher = FileWatcher(on_file_changed=callback)

        dir1 = tmp_path / "dir1"
        dir2 = tmp_path / "dir2"
        dir1.mkdir()
        dir2.mkdir()

        watcher.watch_directory(dir1)
        watcher.watch_directory(dir2)

        assert len(watcher._watched_dirs) == 2


class TestPeriodicFullScan:
    """Test that periodic_full_scan respects shutdown_event."""

    async def test_exits_when_shutdown_set(self) -> None:
        callback = MagicMock()
        watcher = FileWatcher(on_file_changed=callback, full_scan_interval_minutes=1)

        shutdown_event = asyncio.Event()
        # Set shutdown immediately
        shutdown_event.set()

        # Should exit immediately without calling scan_callback
        await watcher.periodic_full_scan(callback, shutdown_event)
        callback.assert_not_called()

    async def test_calls_scan_callback_on_timeout(self) -> None:
        scan_callback = MagicMock()
        watcher = FileWatcher(on_file_changed=MagicMock(), full_scan_interval_minutes=1)
        # Override interval to very short for testing
        watcher._full_scan_interval = 0.05  # 50ms

        shutdown_event = asyncio.Event()

        async def stop_after_scan() -> None:
            # Wait for at least one scan to happen
            await asyncio.sleep(0.15)
            shutdown_event.set()

        await asyncio.gather(
            watcher.periodic_full_scan(scan_callback, shutdown_event),
            stop_after_scan(),
        )

        assert scan_callback.call_count >= 1
