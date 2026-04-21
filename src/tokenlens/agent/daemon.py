"""Daemon manager — PID file, heartbeat, signal handling, startup, watch loop, shutdown.

Manages the full lifecycle of the background collection daemon.
"""

from __future__ import annotations

import asyncio
import os
import signal
from datetime import UTC, datetime
from pathlib import Path

import structlog

from tokenlens.core.config import get_data_dir

logger = structlog.get_logger()

PID_FILE = "agent.pid"
HEALTH_FILE = "agent.health"
LOG_FILE = "logs/agent.log"


class DaemonManager:
    """Manages daemon lifecycle: PID file, heartbeat, signal handling, shutdown."""

    def __init__(self) -> None:
        self._data_dir = get_data_dir()
        self._pid_path = self._data_dir / PID_FILE
        self._health_path = self._data_dir / HEALTH_FILE
        self._shutdown_event = asyncio.Event()
        self._events_processed: int = 0

    @property
    def pid_path(self) -> Path:
        return self._pid_path

    def is_running(self) -> tuple[bool, int | None]:
        """Check if daemon is already running. Returns (running, pid).

        Handles stale PID files (process dead → remove file, return False).
        """
        if not self._pid_path.exists():
            return (False, None)

        try:
            pid = int(self._pid_path.read_text().strip())
        except (ValueError, OSError):
            return (False, None)

        # Check if process is alive
        try:
            os.kill(pid, 0)  # Signal 0 = check existence
            return (True, pid)
        except ProcessLookupError:
            # Stale PID file — process is dead
            logger.warning("Stale PID file found (PID %d). Removing.", pid)
            self._pid_path.unlink(missing_ok=True)
            return (False, None)
        except PermissionError:
            # Process exists but we can't signal it
            return (True, pid)

    def write_pid(self) -> None:
        """Write current PID to file with restricted permissions."""
        self._pid_path.write_text(str(os.getpid()))
        self._pid_path.chmod(0o600)

    def remove_pid(self) -> None:
        """Remove PID file."""
        self._pid_path.unlink(missing_ok=True)

    def write_heartbeat(self) -> None:
        """Write UTC ISO timestamp to health file."""
        self._health_path.write_text(datetime.now(UTC).isoformat())

    def read_heartbeat(self) -> datetime | None:
        """Read and parse health file. Returns None if missing or invalid."""
        if not self._health_path.exists():
            return None
        try:
            return datetime.fromisoformat(self._health_path.read_text().strip())
        except (ValueError, OSError):
            return None

    def setup_signal_handlers(self, loop: asyncio.AbstractEventLoop) -> None:
        """Register SIGTERM and SIGINT handlers for graceful shutdown."""
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self._handle_signal, sig)

    def _handle_signal(self, sig: signal.Signals) -> None:
        logger.info("Received signal %s. Initiating graceful shutdown.", sig.name)
        self._shutdown_event.set()

    @property
    def shutdown_requested(self) -> bool:
        return self._shutdown_event.is_set()

    async def wait_for_shutdown(self) -> None:
        await self._shutdown_event.wait()

    def increment_events(self, count: int = 1) -> None:
        self._events_processed += count

    @property
    def events_processed(self) -> int:
        return self._events_processed


async def daemon_startup(manager: DaemonManager) -> tuple:
    """Execute the daemon startup sequence.

    Returns (registry, session_manager, pipeline, watcher, file_change_queue, ml_runner)
    for the watch loop.
    """
    from tokenlens.adapters.registry import AdapterRegistry
    from tokenlens.agent.pipeline import EventPipeline
    from tokenlens.agent.session import SessionManager
    from tokenlens.agent.watcher import FileWatcher
    from tokenlens.core.config import ensure_dirs, get_session_gap_minutes
    from tokenlens.core.database import get_session, init_engine
    from tokenlens.core.models import AdapterStateRow

    # Step 1: Ensure directories exist
    ensure_dirs()

    # Step 2: Initialize database engine
    await init_engine()

    # Step 3: Create and populate adapter registry
    registry = AdapterRegistry()
    registry.load_builtins()
    registry.discover_entry_points()

    # Step 4: Get available adapters
    available = registry.get_available()
    logger.info("Available adapters: %s", [a.name for a in available])

    # Step 5: Restore adapter positions from DB
    from sqlalchemy import select

    async with get_session() as db:
        for adapter in available:
            result = await db.execute(
                select(AdapterStateRow).where(
                    AdapterStateRow.adapter_name == adapter.name
                )
            )
            for state_row in result.scalars().all():
                adapter.set_position(
                    Path(state_row.file_path), state_row.byte_offset
                )
                logger.debug(
                    "Restored position for %s: %s @ %d",
                    adapter.name,
                    state_row.file_path,
                    state_row.byte_offset,
                )

    # Step 6: Create session manager and pipeline
    session_manager = SessionManager(
        session_gap_minutes=get_session_gap_minutes("claude_code")
    )
    pipeline = EventPipeline()

    # Step 7: Initial full parse of all log files
    for adapter in available:
        log_paths = await asyncio.to_thread(adapter.get_log_paths)
        for log_path in log_paths:
            events = await asyncio.to_thread(adapter.parse_file, log_path)
            for event in events:
                session_manager.assign_session_id(event)
            if events:
                await pipeline.add_events(events)
                manager.increment_events(len(events))

    # Flush initial parse
    await pipeline.flush()

    # Step 8: Update adapter_state after initial parse
    await _update_adapter_state(available)

    # Step 9: Create file watcher with async queue for real-time processing
    file_change_queue: asyncio.Queue[Path] = asyncio.Queue()

    def on_file_changed(path: Path) -> None:
        """Callback for watchdog — pushes changed path into async queue.

        Called from the watchdog thread. The queue is thread-safe and bridges
        the sync watchdog callback to the async watch loop.
        """
        try:
            file_change_queue.put_nowait(path)
            logger.debug("File change queued: %s", path)
        except asyncio.QueueFull:
            logger.warning("File change queue full, dropping: %s", path)

    watcher = FileWatcher(on_file_changed=on_file_changed)

    # Watch adapter log directories
    for adapter in available:
        log_paths = await asyncio.to_thread(adapter.get_log_paths)
        if log_paths:
            for log_path in log_paths:
                parent = log_path.parent
                watcher.watch_directory(parent)

    # Step 10: Create ML task runner (graceful degradation if ML deps missing)
    ml_runner = None
    try:
        from tokenlens.ml.scheduler import MLTaskRunner

        ml_runner = MLTaskRunner()
        logger.info("ML task runner initialized.")
    except ImportError:
        logger.info("ML dependencies not installed. ML features disabled.")
    except Exception:
        logger.warning("Failed to initialize ML task runner.", exc_info=True)

    return registry, session_manager, pipeline, watcher, file_change_queue, ml_runner


async def daemon_watch_loop(
    manager: DaemonManager,
    registry: object,
    session_manager: object,
    pipeline: object,
    watcher: object,
    file_change_queue: asyncio.Queue[Path] | None = None,
    ml_runner: object | None = None,
) -> None:
    """Run the daemon watch loop.

    Processes file changes in real-time via asyncio.Queue (pushed by watchdog),
    flushes events periodically, and runs periodic full scans as a fallback.
    """
    from tokenlens.adapters.registry import AdapterRegistry
    from tokenlens.agent.pipeline import EventPipeline
    from tokenlens.agent.session import SessionManager
    from tokenlens.agent.watcher import FileWatcher
    from tokenlens.core.config import settings

    assert isinstance(registry, AdapterRegistry)
    assert isinstance(session_manager, SessionManager)
    assert isinstance(pipeline, EventPipeline)
    assert isinstance(watcher, FileWatcher)

    if file_change_queue is None:
        file_change_queue = asyncio.Queue()

    batch_interval = settings.get("daemon.batch_write_interval_seconds", 2)

    # Start watchdog observer
    watcher.start()
    manager.write_pid()
    manager.write_heartbeat()

    logger.info("Daemon watch loop started.")

    # Thread-safe queue for events from periodic full scan
    scan_event_queue: asyncio.Queue[list] = asyncio.Queue()

    async def process_file_changes() -> None:
        """Consume file change events from the queue and parse immediately.

        This is the real-time path: watchdog detects change → queue → parse → pipeline.
        Target latency: <500ms from file change to DB write.
        """
        while not manager.shutdown_requested:
            try:
                # Wait for a file change event with a short timeout
                path = await asyncio.wait_for(
                    file_change_queue.get(), timeout=0.5
                )
            except TimeoutError:
                continue

            # Find the adapter that owns this file
            for adapter in registry.get_available():
                adapter_paths = await asyncio.to_thread(adapter.get_log_paths)
                if path in adapter_paths or any(
                    str(path).startswith(str(p.parent)) for p in adapter_paths
                ):
                    try:
                        events = await asyncio.to_thread(adapter.parse_file, path)
                        for event in events:
                            session_manager.assign_session_id(event)
                        if events:
                            await pipeline.add_events(events)
                            logger.debug(
                                "Processed %d events from %s (real-time)",
                                len(events),
                                path.name,
                            )
                    except Exception:
                        logger.warning(
                            "Error processing file change: %s",
                            path,
                            exc_info=True,
                        )
                    break

    async def flush_loop() -> None:
        """Periodically flush events and close pending sessions."""
        while not manager.shutdown_requested:
            await asyncio.sleep(batch_interval)
            written = await pipeline.flush()
            if written > 0:
                manager.increment_events(written)
                await _update_adapter_state(registry.get_available())
            await session_manager.close_pending_sessions()
            manager.write_heartbeat()

            # Run ML tasks if runner is available
            if ml_runner is not None:
                try:
                    await ml_runner.run_due_tasks()
                except Exception:
                    logger.warning("ML task execution failed.", exc_info=True)

    async def full_scan() -> None:
        """Periodic full scan of all adapter log files as a fallback.

        Uses asyncio.Queue (thread-safe) instead of a shared mutable list.
        """
        def scan_all() -> None:
            for adapter in registry.get_available():
                for log_path in adapter.get_log_paths():
                    events = adapter.parse_file(log_path)
                    if events:
                        scan_event_queue.put_nowait(events)

        await watcher.periodic_full_scan(scan_all, manager._shutdown_event)

    async def process_scan_events() -> None:
        """Process events from periodic full scans via thread-safe queue."""
        while not manager.shutdown_requested:
            try:
                events = await asyncio.wait_for(
                    scan_event_queue.get(), timeout=1.0
                )
                for event in events:
                    session_manager.assign_session_id(event)
                await pipeline.add_events(events)
            except TimeoutError:
                continue

    try:
        await asyncio.gather(
            process_file_changes(),
            flush_loop(),
            full_scan(),
            process_scan_events(),
            manager.wait_for_shutdown(),
        )
    except asyncio.CancelledError:
        pass
    finally:
        watcher.stop()


async def daemon_shutdown(
    manager: DaemonManager,
    pipeline: object,
    session_manager: object,
    registry: object,
) -> None:
    """Graceful shutdown: flush events, close sessions, update state, cleanup.

    Called on SIGTERM/SIGINT.
    """
    from tokenlens.adapters.registry import AdapterRegistry
    from tokenlens.agent.pipeline import EventPipeline
    from tokenlens.agent.session import SessionManager
    from tokenlens.core.database import close_engine

    assert isinstance(pipeline, EventPipeline)
    assert isinstance(session_manager, SessionManager)
    assert isinstance(registry, AdapterRegistry)

    logger.info("Shutting down daemon...")

    # Step 1: Flush all pending events
    try:
        written = await pipeline.flush()
        if written > 0:
            manager.increment_events(written)
        logger.info("Flushed %d pending events.", written)
    except Exception:
        logger.error("Error flushing events during shutdown.", exc_info=True)

    # Step 2: Close all open sessions
    try:
        await session_manager.flush_all_open_sessions()
        logger.info("All open sessions closed.")
    except Exception:
        logger.error("Error closing sessions during shutdown.", exc_info=True)

    # Step 3: Update adapter_state with final positions
    try:
        await _update_adapter_state(registry.get_available())
    except Exception:
        logger.error("Error updating adapter state during shutdown.", exc_info=True)

    # Step 4: Remove PID file
    manager.remove_pid()

    # Step 5: Close database engine
    await close_engine()

    logger.info(
        "Daemon shutdown complete. Total events processed: %d",
        manager.events_processed,
    )


async def _update_adapter_state(adapters: list) -> None:
    """Update adapter_state table with current file positions for all adapters."""
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert

    from tokenlens.core.database import get_session
    from tokenlens.core.models import AdapterStateRow

    async with get_session() as db:
        for adapter in adapters:
            for log_path in adapter.get_log_paths():
                offset = adapter.get_last_processed_position(log_path)
                stmt = sqlite_insert(AdapterStateRow).values(
                    adapter_name=adapter.name,
                    file_path=str(log_path),
                    byte_offset=offset,
                    last_processed_at=datetime.now(UTC),
                ).on_conflict_do_update(
                    index_elements=["adapter_name", "file_path"],
                    set_={
                        "byte_offset": offset,
                        "last_processed_at": datetime.now(UTC),
                    },
                )
                await db.execute(stmt)
