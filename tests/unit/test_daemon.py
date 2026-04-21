"""Unit tests for DaemonManager.

Tests PID file lifecycle, heartbeat round-trip, and signal handling.
"""

from __future__ import annotations

import os
import signal
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from tokenlens.agent.daemon import DaemonManager

if TYPE_CHECKING:
    from pathlib import Path


class TestIsRunning:
    """Test is_running() with no PID, valid PID, and stale PID."""

    def test_no_pid_file(self, tmp_path: Path) -> None:
        manager = DaemonManager()
        manager._pid_path = tmp_path / "agent.pid"

        running, pid = manager.is_running()

        assert running is False
        assert pid is None

    def test_valid_pid_file(self, tmp_path: Path) -> None:
        manager = DaemonManager()
        manager._pid_path = tmp_path / "agent.pid"

        # Write current process PID (which is alive)
        current_pid = os.getpid()
        manager._pid_path.write_text(str(current_pid))

        running, pid = manager.is_running()

        assert running is True
        assert pid == current_pid

    def test_stale_pid_file(self, tmp_path: Path) -> None:
        manager = DaemonManager()
        manager._pid_path = tmp_path / "agent.pid"

        # Write a PID that doesn't exist (very high number)
        stale_pid = 999999999
        manager._pid_path.write_text(str(stale_pid))

        running, pid = manager.is_running()

        assert running is False
        assert pid is None
        # Stale PID file should be removed
        assert not manager._pid_path.exists()

    def test_invalid_pid_content(self, tmp_path: Path) -> None:
        manager = DaemonManager()
        manager._pid_path = tmp_path / "agent.pid"

        manager._pid_path.write_text("not-a-number")

        running, pid = manager.is_running()

        assert running is False
        assert pid is None


class TestWriteAndRemovePid:
    """Test write_pid() and remove_pid() lifecycle."""

    def test_write_pid_creates_file(self, tmp_path: Path) -> None:
        manager = DaemonManager()
        manager._pid_path = tmp_path / "agent.pid"

        manager.write_pid()

        assert manager._pid_path.exists()
        assert manager._pid_path.read_text() == str(os.getpid())
        # Check permissions (0o600)
        mode = manager._pid_path.stat().st_mode & 0o777
        assert mode == 0o600

    def test_remove_pid_deletes_file(self, tmp_path: Path) -> None:
        manager = DaemonManager()
        manager._pid_path = tmp_path / "agent.pid"

        manager.write_pid()
        assert manager._pid_path.exists()

        manager.remove_pid()
        assert not manager._pid_path.exists()

    def test_remove_pid_no_error_if_missing(self, tmp_path: Path) -> None:
        manager = DaemonManager()
        manager._pid_path = tmp_path / "agent.pid"

        # Should not raise even if file doesn't exist
        manager.remove_pid()


class TestHeartbeat:
    """Test write_heartbeat() and read_heartbeat() round-trip."""

    def test_write_and_read_heartbeat(self, tmp_path: Path) -> None:
        manager = DaemonManager()
        manager._health_path = tmp_path / "agent.health"

        manager.write_heartbeat()

        result = manager.read_heartbeat()
        assert result is not None
        assert isinstance(result, datetime)
        # Should be very recent (within last 5 seconds)
        now = datetime.now(UTC)
        assert (now - result).total_seconds() < 5

    def test_read_heartbeat_no_file(self, tmp_path: Path) -> None:
        manager = DaemonManager()
        manager._health_path = tmp_path / "agent.health"

        result = manager.read_heartbeat()
        assert result is None

    def test_read_heartbeat_invalid_content(self, tmp_path: Path) -> None:
        manager = DaemonManager()
        manager._health_path = tmp_path / "agent.health"
        manager._health_path.write_text("not-a-datetime")

        result = manager.read_heartbeat()
        assert result is None


class TestSignalHandler:
    """Test that signal handler sets shutdown event."""

    def test_handle_signal_sets_shutdown(self) -> None:
        manager = DaemonManager()

        assert not manager.shutdown_requested

        manager._handle_signal(signal.SIGTERM)

        assert manager.shutdown_requested

    def test_events_processed_tracking(self) -> None:
        manager = DaemonManager()

        assert manager.events_processed == 0

        manager.increment_events(5)
        assert manager.events_processed == 5

        manager.increment_events(3)
        assert manager.events_processed == 8
