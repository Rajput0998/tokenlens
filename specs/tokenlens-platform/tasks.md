# Implementation Plan: TokenLens Platform

## Overview

TokenLens is a local-first token monitoring platform for AI coding tools. This plan covers Phase 1 (Core Data Fabric) with full task granularity — each task is a discrete coding step completable in 1-2 hours. Phases 2-6 are epic-level placeholders to be expanded when reached.

**Language:** Python 3.12+ (backend), React 18 + TypeScript (frontend, Phase 4)
**Testing:** pytest + pytest-asyncio + Hypothesis (property-based) + factory-boy

---

## Phase 1: Core Data Fabric

- [x] 1. Scaffold project structure and dev tooling
  - Create `pyproject.toml` with project metadata, dependencies (typer, rich, structlog, pydantic, dynaconf, sqlalchemy[asyncio], aiosqlite, alembic, watchdog, httpx), optional extras (`[ml]`, `[api]`, `[all]`, `[dev]`), `[project.scripts]` entry point `tokenlens = "tokenlens.cli.main:app"`, and `[project.entry-points."tokenlens.adapters"]` for `claude_code`
  - Create `src/tokenlens/__init__.py` with `__version__ = "0.1.0"`
  - Create all `__init__.py` files for subpackages: `core/`, `adapters/`, `agent/`, `ml/`, `api/`, `alerts/`, `cli/`, `cli/commands/`, `integrations/`
  - Create `.pre-commit-config.yaml` with ruff (lint + format) and mypy hooks
  - Create `ruff.toml` with Python 3.12 target, line-length 100, and import sorting
  - Create `tests/conftest.py` with async DB fixture (in-memory SQLite), `tests/__init__.py`, `tests/unit/__init__.py`, `tests/integration/__init__.py`, `tests/property/__init__.py`
  - Verify: `pip install -e ".[dev]"` succeeds, `ruff check src/` passes, `mypy src/tokenlens/` passes
  - _Requirements: FR-P6-01.1, FR-P6-01.3, FR-P6-04.1_

- [x] 2. Implement Pydantic v2 schemas
  - [x] 2.1 Create `src/tokenlens/core/schema.py` with `ToolEnum`, `ContextType`, `TokenEvent`, `Session`, and `AdapterState` models
    - `TokenEvent`: all required fields (id, tool, model, user_id, session_id, timestamp, input_tokens, output_tokens, cost_usd, context_type, turn_number), optional fields (cache_read_tokens, cache_write_tokens, file_types_in_context, tool_calls, raw_metadata), dedup fields (source_file_path, file_byte_offset)
    - `field_validator` for `timestamp` to ensure timezone awareness (replace naive with UTC)
    - `Field(ge=0)` constraints on all token counts and cost
    - `Session`: id, tool, start_time, end_time, total_input_tokens, total_output_tokens, total_cost_usd, turn_count, efficiency_score (nullable)
    - `AdapterState`: adapter_name, file_path, byte_offset, last_processed_at
    - All models: `model_config = {"from_attributes": True}`
    - _Requirements: FR-P1-01.1, FR-P1-01.2, FR-P1-01.3, FR-P1-01.4, FR-P1-01.5, FR-P1-01.6, FR-P1-02.1_

  - [x] 2.2 Write property tests for TokenEvent schema
    - **Property 1: TokenEvent JSON round-trip** — serialize via `.model_dump_json()` and deserialize via `TokenEvent.model_validate_json()` produces equivalent object
    - **Validates: Requirements FR-P1-01.1, FR-P1-01.6**

  - [x] 2.3 Write property tests for schema validation
    - **Property 2: Negative values rejected** — negative int for token counts or negative float for cost_usd raises `ValidationError`
    - **Validates: Requirements FR-P1-01.4, FR-P1-01.5**
    - **Property 3: Missing required field raises ValidationError** — omitting any required field (tool, model, user_id, timestamp, input_tokens, output_tokens) raises `ValidationError` identifying the field
    - **Validates: Requirements FR-P1-01.3**


- [x] 3. Implement SQLAlchemy ORM models
  - [x] 3.1 Create `src/tokenlens/core/models.py` with `Base`, shared `_tool_enum`, and all ORM models
    - `TokenEventRow`: all columns matching schema, `_tool_enum` shared at module level, JSON columns for list/dict fields, `__table_args__` with indexes (`ix_token_events_timestamp`, `ix_token_events_tool`, `ix_token_events_model`, `ix_token_events_user_id`, `ix_token_events_session_id`, `ix_token_events_tool_timestamp` composite) and `UniqueConstraint("tool", "source_file_path", "file_byte_offset", name="uq_dedup_key")`
    - `SessionRow`: id, tool (reuses `_tool_enum`), start_time, end_time, aggregates, efficiency_score nullable, indexes on tool and start_time
    - `AdapterStateRow`: autoincrement id, adapter_name, file_path, byte_offset, last_processed_at, `UniqueConstraint("adapter_name", "file_path", name="uq_adapter_file")`
    - `SettingRow`: key (PK), value, updated_at
    - `AnomalyRow`: Phase 2 table defined in models.py but NOT created by initial migration — added via separate Alembic migration in Phase 2
    - _Requirements: FR-P1-08.2, FR-P1-08.4_

  - [x] 3.2 Write unit tests for ORM models
    - Test that all models can be instantiated with valid data
    - Test that `_tool_enum` is shared across `TokenEventRow` and `SessionRow`
    - Test table name and column definitions match expected schema
    - _Requirements: FR-P1-08.2_

- [x] 4. Implement database layer and Alembic migrations
  - [x] 4.1 Create `src/tokenlens/core/database.py` with async engine, session factory, and lifecycle functions
    - `init_engine(db_url)`: create `AsyncEngine` with `aiosqlite`, `pool_pre_ping=True`, `check_same_thread=False`, create `async_sessionmaker`, run `Base.metadata.create_all` via `conn.run_sync()`
    - `get_engine()`: return existing or init new engine
    - `get_session()`: async context manager yielding `AsyncSession` with commit/rollback
    - `close_engine()`: dispose engine and reset globals
    - Default DB path: `~/.tokenlens/tokenlens.db`
    - _Requirements: FR-P1-08.1, FR-P1-08.3_

  - [x] 4.2 Set up Alembic with async env.py pattern
    - Create `alembic.ini` at project root pointing to `src/tokenlens/core/migrations/`
    - Create `src/tokenlens/core/migrations/env.py` using the async pattern: `run_async_migrations()` with `create_async_engine()` and `async with engine.begin()` — this is required for aiosqlite compatibility
    - Create `src/tokenlens/core/migrations/script.py.mako` template
    - Auto-generate initial migration: `alembic revision --autogenerate -m "initial"` — must include `token_events`, `sessions`, `adapter_state`, `settings` tables (NOT `anomalies` — that's Phase 2)
    - Verify: `alembic upgrade head` succeeds against a fresh SQLite DB
    - _Requirements: FR-P1-08.3_

  - [x] 4.3 Write integration tests for database layer
    - Test `init_engine()` creates tables in an in-memory SQLite DB
    - Test `get_session()` context manager commits on success and rolls back on exception
    - Test `close_engine()` disposes engine cleanly
    - Test inserting a `TokenEventRow` and reading it back
    - **Property 13: Database-level dedup** — inserting the same `(tool, source_file_path, file_byte_offset)` twice results in exactly one row
    - **Validates: Requirements FR-P1-09.9**
    - _Requirements: FR-P1-08.1_


- [x] 5. Implement configuration system
  - [x] 5.1 Create `src/tokenlens/core/config.py` with dynaconf settings loader
    - `TOKENLENS_DIR = Path.home() / ".tokenlens"`, `CONFIG_PATH = TOKENLENS_DIR / "config.toml"`
    - `settings = Dynaconf(envvar_prefix="TOKENLENS", settings_files=[str(CONFIG_PATH)], environments=False, load_dotenv=False)`
    - Helper functions: `get_data_dir()`, `get_db_path()`, `get_pricing_table()`, `get_session_gap_minutes(tool)`, `ensure_dirs()` (creates `~/.tokenlens/`, `logs/`, `models/` subdirectories)
    - Create `DEFAULT_CONFIG_TEMPLATE` string constant (or `src/tokenlens/core/defaults.py`) containing the full default `config.toml` content from design doc section 1.1 — all sections: `[general]`, `[daemon]`, `[adapters.claude_code]`, `[adapters.kiro]`, `[pricing.models]`, `[api]`, `[alerts]`, `[alerts.thresholds]`, `[alerts.webhooks]`, `[ml]`, `[ml.anomaly]`, `[integrations.kiro]`. The `tokenlens init` command writes this template to disk.
    - No `poll_interval_seconds` — only `batch_write_interval_seconds` and `full_scan_interval_minutes`
    - _Requirements: FR-P1-11.1, FR-P1-11.2, FR-P1-11.3, FR-P1-11.4_

  - [x] 5.2 Write unit tests for configuration
    - Test default values when no config file exists
    - Test loading from a temporary TOML file
    - **Property 14: Environment variable overrides** — setting `TOKENLENS_` prefixed env var overrides TOML value
    - **Validates: Requirements FR-P1-11.3**
    - _Requirements: FR-P1-11.4_

- [x] 6. Implement model pricing with fuzzy matching
  - [x] 6.1 Create `src/tokenlens/core/pricing.py` with `normalize_model_name()` and `calculate_cost()`
    - `_VERSION_SUFFIX_RE`: regex to strip date stamps (YYYYMMDD) and version suffixes (vN.N) iteratively
    - `normalize_model_name(raw_name)`: lowercase, strip, iteratively remove trailing version/date suffixes
    - `calculate_cost(model, input_tokens, output_tokens) -> tuple[float, bool]`: exact match first, then normalized key match, return `(0.0, False)` if no match
    - Cost formula: `(input_tokens * input_price / 1_000_000) + (output_tokens * output_price / 1_000_000)`
    - _Requirements: FR-P1-03.1, FR-P1-03.2, FR-P1-03.3, FR-P1-03.4_

  - [x] 6.2 Write property tests for pricing
    - **Property 5: Cost calculation formula correctness** — for any known model and non-negative tokens, `calculate_cost()` returns the exact formula result with `matched=True`
    - **Validates: Requirements FR-P1-03.3**
    - **Property 6: Fuzzy model name matching** — appending date stamp (YYYYMMDD) or version suffix (vN.N) to a known model name still resolves to the correct pricing entry
    - **Validates: Requirements FR-P1-03.4**
    - _Requirements: FR-P1-03.3, FR-P1-03.4_

- [x] 7. Checkpoint — Ensure all core module tests pass
  - Run `pytest tests/ -v` — all tests pass
  - Run `ruff check src/` — no errors
  - Run `mypy src/tokenlens/` — no errors


- [x] 8. Implement Adapter SDK and Registry
  - [x] 8.1 Create `src/tokenlens/adapters/base.py` with `ToolAdapter` abstract base class
    - Abstract properties: `name -> str`, `version -> str`
    - Abstract methods: `discover() -> bool`, `get_log_paths() -> list[Path]`, `parse_file(path: Path) -> list[TokenEvent]`, `get_last_processed_position(path: Path) -> int`
    - All methods are synchronous — daemon wraps in `asyncio.to_thread()`
    - NOTE: `watch()` is NOT part of the adapter interface — file watching is a daemon concern
    - _Requirements: FR-P1-04.1, FR-P1-04.4, FR-P1-04.5_

  - [x] 8.2 Create `src/tokenlens/adapters/registry.py` with `AdapterRegistry`
    - `register(adapter)`: first-registration-wins on name collision, log warning on duplicate
    - `discover_entry_points()`: load from `importlib.metadata.entry_points()` under group `tokenlens.adapters`, catch and log failures per entry point
    - `load_builtins()`: register `ClaudeCodeAdapter` explicitly
    - `get_all() -> list[ToolAdapter]`: return all registered adapters
    - `get_available() -> list[ToolAdapter]`: return only adapters where `discover()` returns True, catch exceptions per adapter
    - `get(name) -> ToolAdapter | None`: lookup by name
    - _Requirements: FR-P1-05.1, FR-P1-05.2, FR-P1-05.3, FR-P1-05.4, FR-P1-05.5_

  - [x] 8.3 Write property tests for adapter registry
    - **Property 7: get_available() filters by discover()** — for any set of mock adapters with random `discover()` results, `get_available()` returns exactly the subset where `discover()` is True
    - **Validates: Requirements FR-P1-05.3**
    - **Property 8: First-registration-wins on name collision** — registering two adapters with the same name keeps only the first
    - **Validates: Requirements FR-P1-05.5**
    - _Requirements: FR-P1-05.3, FR-P1-05.5_

- [x] 9. Implement Claude Code Adapter
  - [x] 9.1 Create `src/tokenlens/adapters/claude_code.py` with `ClaudeCodeAdapter`
    - Properties: `name = "claude_code"`, `version = "1.0.0"`
    - `__init__`: accept optional `log_dir` (default `~/.claude/projects`), init `_file_positions: dict[str, int]` and `_turn_counters: dict[str, int]`
    - `discover()`: check if log_dir exists and contains any `.jsonl` files
    - `get_log_paths()`: return sorted list of all `.jsonl` files via `rglob("*.jsonl")`
    - `parse_file(path)`: open file, seek to stored byte offset, iterate lines, parse JSON, call `_parse_entry()`, track `line_start_offset` as `file_byte_offset` for dedup key, update `_file_positions` to `f.tell()` after parsing
    - `_parse_entry(data, path, byte_offset)`: only process `role="assistant"` with non-zero tokens, extract model/input_tokens/output_tokens/cache_read/cache_write/timestamp, call `calculate_cost()`, track turn numbers via `_turn_counters` dict keyed by file path, return `TokenEvent` with `tool=ToolEnum.CLAUDE_CODE`
    - `set_position(path, offset)`: restore position from adapter_state DB on daemon startup
    - `get_last_processed_position(path)`: return stored byte offset for a file
    - Handle `json.JSONDecodeError`: log warning with file name, line number, offset, skip line
    - Handle `FileNotFoundError`: raise with path in message
    - _Requirements: FR-P1-06.1, FR-P1-06.2, FR-P1-06.3, FR-P1-06.4, FR-P1-06.5_

  - [x] 9.2 Write property tests for Claude Code adapter
    - **Property 9: JSONL field extraction correctness** — for any valid JSONL entry with role="assistant", non-negative tokens, and a model string, parsing produces a TokenEvent with matching tool, model, input_tokens, output_tokens
    - **Validates: Requirements FR-P1-06.2**
    - **Property 10: Incremental parsing produces no duplicates** — parsing a file twice without changes returns empty list on second parse
    - **Validates: Requirements FR-P1-06.3**
    - **Property 11: Malformed JSON lines skipped** — a file with N valid assistant entries and M malformed lines produces exactly N TokenEvents
    - **Validates: Requirements FR-P1-06.5**
    - _Requirements: FR-P1-06.2, FR-P1-06.3, FR-P1-06.5_


- [x] 10. Implement session boundary detection and aggregation
  - [x] 10.1 Create `src/tokenlens/agent/session.py` with `SessionManager`
    - `__init__(session_gap_minutes=15)`: store gap as `timedelta`, init `_open_sessions: dict[str, tuple[str, datetime]]` and `_pending_closes: list`
    - `assign_session_id(event)`: check if tool has an open session, if gap between event timestamp and last timestamp is **strictly greater than** `_gap` then close old session and start new one, otherwise update timestamp — a gap of exactly 15 minutes does NOT trigger a new session
    - `_schedule_close(session_id, tool)`: append to `_pending_closes` list
    - `close_pending_sessions()`: iterate `_pending_closes`, call `_aggregate_and_persist()` for each
    - `flush_all_open_sessions()`: close all open sessions (called on daemon shutdown)
    - `_aggregate_and_persist(session_id, tool)`: query `token_events` for matching `session_id`, compute `min(timestamp)`, `max(timestamp)`, `sum(input_tokens)`, `sum(output_tokens)`, `sum(cost_usd)`, `count(id)`, write `SessionRow`
    - _Requirements: FR-P1-02.2, FR-P1-06.6, FR-P1-09.4_

  - [x] 10.2 Write property tests for session boundary detection
    - **Property 12: Session boundary by timestamp gap** — for any ordered sequence of timestamps, events with gaps strictly >15 min get different session_ids, events within ≤15 min gap get the same session_id. A gap of exactly 15 minutes does NOT trigger a new session.
    - **Validates: Requirements FR-P1-06.6, FR-P1-09.4**
    - **Property 4: Session aggregation matches sum of events** — for any list of TokenEvents sharing a session_id, the aggregated Session's totals equal the sums of individual event fields
    - **Validates: Requirements FR-P1-02.2**
    - _Requirements: FR-P1-02.2, FR-P1-06.6, FR-P1-09.4_

- [x] 11. Implement event pipeline with batch, dedup, enrich, and flush
  - [x] 11.1 Create `src/tokenlens/agent/pipeline.py` with `EventPipeline`
    - `__init__(flush_interval=2.0)`: init `_buffer: list[TokenEvent]`, `_lock: asyncio.Lock`, `_total_flushed: int`
    - `add_events(events)`: acquire lock, enrich each event (recalculate cost if 0.0 via `calculate_cost()`), append to buffer
    - `flush()`: acquire lock, copy buffer, clear buffer, release lock, then write batch with retry logic
    - Retry: up to `MAX_FLUSH_RETRIES=10` attempts with `RETRY_DELAY_SECONDS=5` between retries. Batch stays local during retry — do NOT put events back in `_buffer`. New events accumulate independently.
    - `_write_batch(batch)`: use `sqlite_insert().on_conflict_do_nothing(index_elements=["tool", "source_file_path", "file_byte_offset"])` for dedup, count rows with `rowcount > 0`
    - Properties: `pending_count`, `total_flushed`
    - _Requirements: FR-P1-09.3, FR-P1-09.9, FR-P1-09.11_

  - [x] 11.2 Write unit tests for event pipeline
    - Test `add_events()` enriches cost for events with `cost_usd=0.0`
    - Test `flush()` writes events to DB and clears buffer
    - Test dedup: adding same event twice results in one DB row
    - Test retry logic: mock DB failure, verify retry count and delay
    - Test that during retry, new events added to buffer are independent of the retrying batch
    - _Requirements: FR-P1-09.3, FR-P1-09.9, FR-P1-09.11_

- [x] 12. Implement file watcher with watchdog and periodic full-scan
  - [x] 12.1 Create `src/tokenlens/agent/watcher.py` with `LogFileHandler` and `FileWatcher`
    - `LogFileHandler(FileSystemEventHandler)`: `on_modified()` filters for `.jsonl` files, calls callback with `Path`
    - `FileWatcher.__init__(on_file_changed, full_scan_interval_minutes=5)`: create `Observer`, track watched dirs
    - `watch_directory(directory)`: schedule handler with `recursive=True`, skip if already watched
    - `start()` / `stop()`: start/stop the watchdog observer
    - `periodic_full_scan(scan_callback, shutdown_event)`: async loop that runs `scan_callback` via `asyncio.to_thread()` every N minutes, respects shutdown event
    - Uses native OS watching (inotify on Linux, FSEvents on macOS — not polling)
    - _Requirements: FR-P1-09.1, FR-P1-09.12_

  - [x] 12.2 Write unit tests for FileWatcher
    - Test `LogFileHandler.on_modified()` filters non-JSONL files (only `.jsonl` triggers callback)
    - Test `watch_directory()` skips already-watched directories
    - Test `periodic_full_scan()` respects shutdown_event (exits when set)
    - Test `periodic_full_scan()` calls scan_callback at the configured interval
    - _Requirements: FR-P1-09.1, FR-P1-09.12_


- [x] 13. Implement daemon manager with PID, signals, and heartbeat
  - [x] 13.1 Create `src/tokenlens/agent/daemon.py` with `DaemonManager`
    - `__init__()`: resolve `_data_dir` from config, set `_pid_path`, `_health_path`, create `_shutdown_event: asyncio.Event`
    - `is_running() -> tuple[bool, int | None]`: check PID file exists, read PID, check process alive via `os.kill(pid, 0)`, handle stale PID (process dead → remove file, return False)
    - `write_pid()` / `remove_pid()`: write current PID with `chmod 0o600`, unlink on stop
    - `write_heartbeat()`: write UTC ISO timestamp to health file
    - `read_heartbeat() -> datetime | None`: read and parse health file
    - `setup_signal_handlers(loop)`: register SIGTERM and SIGINT handlers that set `_shutdown_event`
    - `shutdown_requested` property, `wait_for_shutdown()` async method
    - `increment_events(count)` / `events_processed` property for tracking
    - Log to `~/.tokenlens/logs/agent.log` via structlog
    - _Requirements: FR-P1-09.5, FR-P1-09.6, FR-P1-09.7, FR-P1-09.10, FR-P1-09.13_

  - [x] 13.2 Implement daemon startup sequence
    - Call `ensure_dirs()`, `init_engine()`, create `AdapterRegistry`, `load_builtins()`, `discover_entry_points()`, `get_available()`
    - Query `adapter_state` table for all rows matching each adapter's name, call `adapter.set_position(path, offset)` for each to restore positions from DB
    - Run initial full parse of all log files via each adapter's `parse_file()` (via `asyncio.to_thread()`), assign session IDs, add events to pipeline, flush
    - After initial parse completes, update `adapter_state` with new positions for all parsed files
    - Acceptance: daemon starts, parses existing JSONL files, events appear in DB with correct session IDs
    - _Requirements: FR-P1-09.8_

  - [x] 13.3 Implement daemon watch loop
    - Wire `FileWatcher` to adapter log directories, on file change call adapter's `parse_file()` via `asyncio.to_thread()` for new data only (using stored read position)
    - Assign session IDs via `SessionManager.assign_session_id()`, add events to `EventPipeline`
    - After successful pipeline flush, update `adapter_state` table with each adapter's current file positions via `get_last_processed_position()` for all parsed files
    - Start `EventPipeline` flush loop (every `batch_write_interval_seconds`), start `periodic_full_scan` task
    - Call `SessionManager.close_pending_sessions()` after each flush cycle
    - Write heartbeat after each successful cycle
    - Acceptance: modifying a JSONL file triggers parsing and DB write within 2 seconds
    - _Requirements: FR-P1-09.1, FR-P1-09.2, FR-P1-09.3, FR-P1-09.12_

  - [x] 13.4 Implement daemon shutdown and periodic scan
    - On SIGTERM/SIGINT: flush all pending events via `EventPipeline.flush()`, close all open sessions via `SessionManager.flush_all_open_sessions()`, update final adapter_state positions, remove PID file, close engine
    - Periodic full-scan: every `full_scan_interval_minutes` (default 5), run full parse of all adapter log files as a fallback in case watchdog missed events
    - Acceptance: SIGTERM flushes pending events and closes sessions before exit; periodic scan catches events missed by watchdog
    - _Requirements: FR-P1-09.5, FR-P1-09.12_

  - [x] 13.5 Write unit tests for daemon manager
    - Test `is_running()` with no PID file, valid PID file, stale PID file
    - Test `write_pid()` and `remove_pid()` lifecycle
    - Test `write_heartbeat()` and `read_heartbeat()` round-trip
    - Test signal handler sets shutdown event
    - _Requirements: FR-P1-09.6, FR-P1-09.13_

- [x] 14. Checkpoint — Ensure all daemon and pipeline tests pass
  - Run `pytest tests/ -v` — all tests pass
  - Run `ruff check src/` — no errors
  - Run `mypy src/tokenlens/` — no errors


- [x] 15. Implement CLI: `tokenlens init`
  - [x] 15.1 Create `src/tokenlens/cli/main.py` with Typer app and `agent` sub-command group
    - Top-level `app = typer.Typer(name="tokenlens", no_args_is_help=True)`
    - `agent_app = typer.Typer(help="Manage the background collection daemon.")`
    - `app.add_typer(agent_app, name="agent")`
    - _Requirements: FR-P1-10.1_

  - [x] 15.2 Create `src/tokenlens/cli/commands/init.py` with `tokenlens init` command
    - Call `ensure_dirs()` to create `~/.tokenlens/`, `logs/`, `models/`
    - Generate default `config.toml` at `~/.tokenlens/config.toml` with all sections from design: `[general]`, `[daemon]`, `[adapters.claude_code]`, `[adapters.kiro]` (enabled=false), `[pricing.models]`, `[api]`, `[alerts]`, `[alerts.thresholds]`, `[alerts.webhooks]`, `[ml]`, `[integrations.kiro]`
    - Run adapter discovery via `AdapterRegistry`, print which tools were found (e.g., "✓ Claude Code adapter found at ~/.claude/projects")
    - If Kiro detected, print MCP config snippet for user to copy-paste into `.kiro/settings/mcp.json`
    - Print success message with next steps
    - _Requirements: FR-P1-10.2_

- [x] 16. Implement CLI: `tokenlens agent start/stop/status`
  - [x] 16.1 Create `src/tokenlens/cli/commands/agent.py` with start, stop, and status commands
    - `agent start [--foreground]`: check `DaemonManager.is_running()` — if running, print "Agent already running (PID: XXXX)" and exit code 1. If stale PID, remove and start. For v0.1, `--foreground` is the primary mode (run in foreground with structlog to stdout). Background mode uses `nohup tokenlens agent start --foreground &` — document this in help text. Full python-daemon integration deferred to later.
    - `agent stop`: read PID from file, send SIGTERM, wait up to 10s for process to exit, print confirmation
    - `agent status`: show running state, PID, last heartbeat timestamp, events processed count (read from health file or direct query)
    - _Requirements: FR-P1-10.1, FR-P1-10.3, FR-P1-10.4, FR-P1-10.5, FR-P1-09.13_

- [x] 17. Implement CLI: `tokenlens status`
  - [x] 17.1 Create `src/tokenlens/cli/commands/status.py` with usage summary command
    - Query DB for today's token events: sum input_tokens + output_tokens per tool
    - Calculate total cost from today's events
    - Use `calculate_burn_rate()` from `core/utils.py` (see below) for burn rate label
    - Format output: "Today: 45,231 tokens | Claude Code: 45K | Cost: $0.42 | Burn: normal"
    - Only show tools with active adapters — Phase 1 shows Claude Code only
    - Handle case where DB doesn't exist yet (print "No data yet. Run `tokenlens init` first.")
    - _Requirements: FR-P1-10.6, FR-P1-07.4_

  - [x] 17.2 Create `src/tokenlens/core/utils.py` with reusable `calculate_burn_rate()` function
    - `calculate_burn_rate(tokens_today: int, hours_elapsed: float) -> str`: returns "slow" (<1K/hr), "normal" (1K-5K/hr), "fast" (5K-10K/hr), "critical" (>10K/hr)
    - This function is used by CLI status, API status endpoint, and WebSocket live push
    - _Requirements: FR-P1-10.6_

  - [x] 17.3 Write unit tests for CLI commands
    - Test `init` creates directory structure and config file
    - Test `agent status` output format with mock daemon state
    - Test `status` output format with mock DB data
    - Test `status` handles empty DB gracefully
    - _Requirements: FR-P1-10.2, FR-P1-10.5, FR-P1-10.6_

- [x] 18. Final checkpoint — Full Phase 1 integration verification
  - Run `pytest tests/ -v` — all tests pass (unit, property, integration)
  - Run `ruff check src/` — no errors
  - Run `mypy src/tokenlens/` — no errors
  - Verify: `tokenlens --help` shows all Phase 1 commands
  - Verify: `tokenlens init` creates config and discovers adapters
  - Verify: the full daemon lifecycle works: start → watch → parse → flush → stop


---

## Phase 2: Intelligence Engine

- [x] 19. ML pipeline foundation and thread safety fixes
  - [x] 19.1 Create `src/tokenlens/ml/base.py` with `MLModule` abstract base class
    - Abstract methods: `train(data: pd.DataFrame) -> Any`, `predict(model: Any, input_data: dict) -> dict`, `evaluate(model: Any, test_data: pd.DataFrame) -> dict[str, float]`, `save(model: Any, path: Path) -> None`, `load(path: Path) -> Any`
    - Add `[ml]` optional dependency check: if sklearn not installed, raise ImportError with helpful message
    - _Requirements: FR-P2-06.1_

  - [x] 19.2 Add thread safety locks to Phase 1 shared state
    - Add `threading.Lock` to `ClaudeCodeAdapter._file_positions` — guard all reads/writes in `parse_file()`, `set_position()`, `get_last_processed_position()`
    - Add `threading.Lock` to `SessionManager._open_sessions` and `_pending_closes` — guard `assign_session_id()`, `_schedule_close()`, `close_pending_sessions()`
    - This prevents race conditions between watchdog thread, periodic scan thread, and MCP server writes
    - _Requirements: FR-P1-09.1 (thread safety for concurrent access)_

  - [x] 19.3 Create `src/tokenlens/ml/scheduler.py` with simple time-based ML task runner
    - NO APScheduler — use simple async time checks integrated into daemon loop
    - `MLTaskRunner` class with: `should_retrain_forecaster(last_trained: datetime) -> bool` (daily), `should_retrain_anomaly(last_trained: datetime) -> bool` (weekly), `should_update_profiles(last_updated: datetime) -> bool` (weekly)
    - `run_due_tasks()` method called from daemon flush_loop after each flush cycle
    - Respect `[ml] enabled` feature flag — skip all tasks if ML disabled
    - Store last-run timestamps in `settings` DB table
    - _Requirements: FR-P2-06.2, FR-P2-06.4_

  - [x] 19.4 Wire ML task runner into daemon watch loop
    - Import MLTaskRunner in `daemon.py`
    - After each flush cycle in `flush_loop()`, call `ml_runner.run_due_tasks()` if ML enabled
    - On daemon startup, run initial ML training if sufficient data exists
    - Graceful degradation: if ML modules fail, log warning and continue with raw data
    - _Requirements: FR-P2-06.2, NFR-04.2_

  - [x] 19.5 Write unit tests at `tokenlens/tests/unit/test_ml_base.py`
    - Test MLModule ABC cannot be instantiated directly
    - Test MLTaskRunner time checks (daily, weekly)
    - Test ML disabled flag skips task execution
    - Test thread locks on adapter and session manager (concurrent access doesn't corrupt state)
    - _Requirements: FR-P2-06.1, FR-P2-06.4_

- [x] 20. Burn rate forecaster and budget forecasting
  - [x] 20.1 Create `src/tokenlens/ml/forecaster.py` with `BurnRateForecaster`
    - Implements MLModule interface
    - `_query_hourly_data(tool: str, days: int) -> pd.DataFrame`: query token_events aggregated by hour
    - `train()`: if ≥7 days → statsmodels ExponentialSmoothing (Holt-Winters) with seasonal_periods=24 as default; if 1-6 days → linear extrapolation (total_today / hours_elapsed × 24); if <1 day → return None ("collecting data")
    - Prophet is optional upgrade: if `prophet` importable, use it instead of ExponentialSmoothing for ≥7 days. This avoids cmdstanpy/C++ compiler install friction.
    - `predict()`: forecast next 24 hours with 80% and 95% confidence bands (ExponentialSmoothing uses simulation intervals, Prophet uses built-in intervals)
    - `_predict_limit_hit(forecast, daily_limit) -> dict`: calculate when limit will be hit
    - Separate models per tool, persist to `~/.tokenlens/models/forecaster_{tool}.joblib`
    - Include `model_type` ("exponential_smoothing" | "prophet" | "linear") in output metadata
    - _Requirements: FR-P2-01.1–FR-P2-01.8_

  - [x] 20.2 Create `src/tokenlens/ml/budget.py` with `BudgetForecaster`
    - Derives cost from token forecast × pricing table (NOT separate model)
    - `project_monthly_cost(token_forecast, pricing_table) -> dict`: apply pricing to forecaster predictions
    - `compute_daily_recommendation(monthly_budget, spent_so_far, remaining_days) -> float`
    - Flag `over_budget` when projected > budget × 1.10
    - NOTE: `what_if_simulate()` deferred to Phase 3 (needs API endpoints to be useful)
    - _Requirements: FR-P2-05.1–FR-P2-05.4_

  - [x] 20.3 Write unit tests at `tokenlens/tests/unit/test_forecaster.py`
    - Test cold start states: <1 day returns None, 1-6 days uses linear, ≥7 days uses ExponentialSmoothing
    - Test linear extrapolation formula: (total_today / hours_elapsed) × 24
    - Test forecast output has correct structure (24 entries, confidence bands)
    - Test budget derives cost from token forecast (not independent model)
    - Test over_budget flag triggers at >10% over
    - Test daily_recommendation formula: (budget - spent) / remaining_days
    - _Requirements: FR-P2-01.1–FR-P2-01.8, FR-P2-05.1–FR-P2-05.4_

- [x] 21. Anomaly detection, efficiency scoring, and behavioral profiling
  - [x] 21.1 Update AnomalyRow docstring in `core/models.py`
    - Remove "NOT created by Base.metadata.create_all()" comment — the table IS already created by the initial migration
    - Update to: "Stores detected anomalies. Created in initial migration, populated by Phase 2 AnomalyDetector."
    - _No Alembic migration needed — table already exists_

  - [x] 21.2 Create `src/tokenlens/ml/anomaly.py` with `AnomalyDetector`
    - Implements MLModule interface
    - `_build_feature_vectors(days: int) -> pd.DataFrame`: hourly vectors with total_tokens, input_ratio, output_ratio, session_count, avg_turn_count, dominant_tool_flag
    - `train()`: IsolationForest on rolling 14-day baseline (or all available if <14 days, flagging reduced confidence)
    - `detect(hourly_data: dict) -> dict`: evaluate against trained model, return is_anomaly, score, classification, severity, description, confidence
    - Classification rules from `[ml.anomaly]` config: input_heavy (ratio >5:1), extended_conversation (turns > config threshold), usage_burst (>config multiplier × avg), new_tool
    - Store anomalies in `anomalies` DB table
    - _Requirements: FR-P2-02.1–FR-P2-02.7_

  - [x] 21.3 Create `src/tokenlens/ml/efficiency.py` with `EfficiencyEngine`
    - `score_session(session_id: str) -> dict`: compute weighted score 0-100
    - Normalization: output/input (0→0, ≥0.5→100), cache hit (0%→0, ≥50%→100), turns (≥50→0, ≤5→100), context growth (≥10%→0, ≤1%→100), cost/output (≥$0.001→0, ≤$0.0001→100)
    - `detect_waste_patterns(session_events: list) -> list[str]`: repeated context loading, excessive back-and-forth, context bloat
    - `generate_recommendations(score: float, patterns: list) -> list[str]`
    - `cross_tool_comparison(days: int) -> dict[str, float]`: avg scores per tool
    - Store scores in sessions table `efficiency_score` column
    - _Requirements: FR-P2-03.1–FR-P2-03.6_

  - [x] 21.4 Create `src/tokenlens/ml/profiler.py` with `BehavioralProfiler`
    - `_build_daily_vectors() -> pd.DataFrame`: peak_hour, total_tokens, session_count, avg_session_duration, dominant_tool, input_output_ratio, first_active_hour, last_active_hour
    - `train()`: KMeans clustering with 3 archetypes (reduced from 5), require minimum 30 days of data (increased from 14 — 14 points for 5 clusters was statistically weak)
    - `classify_archetype(cluster_center) -> str`: map to Morning Sprinter (peak 6-12), Steady Coder (even distribution), Night Owl (peak after 18)
    - `detect_productive_hours() -> list[int]`: top 3 hours by output/input ratio
    - `weekly_drift_report() -> dict`: compare current vs previous week archetype
    - _Requirements: FR-P2-04.1–FR-P2-04.5_

  - [x] 21.5 Write unit tests at `tokenlens/tests/unit/test_ml_modules.py`
    - Test anomaly detector with mock feature vectors (normal and anomalous)
    - Test efficiency scoring formula with known inputs
    - Test waste pattern detection rules
    - Test profiler requires 30 days minimum (returns None with insufficient data)
    - Test archetype classification logic (3 archetypes)
    - _Requirements: FR-P2-02.1–FR-P2-02.7, FR-P2-03.1–FR-P2-03.6, FR-P2-04.1–FR-P2-04.5_

  - [x] 21.6 Write property tests at `tokenlens/tests/property/test_efficiency_properties.py`
    - **Property 15: Efficiency score always 0-100** — for any combination of the 5 input dimensions (fuzzed via Hypothesis), the weighted score is always in [0, 100]
    - **Property 16: Higher output/input ratio → higher score** — monotonicity check on the dominant factor
    - _Requirements: FR-P2-03.1, FR-P2-03.2_

- [x] 22. Kiro MCP Server integration
  - [x] 22.1 Add `mcp` and `tiktoken` to `[ml]` optional dependencies in pyproject.toml
    - Install: `uv pip install -e ".[ml]"` in the .venv
    - _Requirements: FR-P2-07.1_

  - [x] 22.2 Create `src/tokenlens/integrations/mcp_server.py` with MCP server
    - Use `mcp` Python package (Anthropic's official MCP SDK) for stdio transport
    - Implement `log_conversation_turn` tool: accept role, content, model (default "kiro-auto"), timestamp (default now). Estimate tokens via tiktoken cl100k_base. Create TokenEvent with tool="kiro", estimated=true in raw_metadata. Store in DB.
    - Implement `get_token_status` tool: query today's usage summary (total tokens, per_tool, cost, burn_rate)
    - Implement `get_efficiency_tips` tool: return top 3 recommendations from EfficiencyEngine
    - Apply session boundary detection (>15 min gap between log_conversation_turn calls) — use a dedicated SessionManager instance with its own lock
    - _Requirements: FR-P2-07.1–FR-P2-07.4, FR-P2-07.7, FR-P2-07.8_

  - [x] 22.3 Add `tokenlens mcp-serve` CLI command
    - Create `src/tokenlens/cli/commands/mcp.py` with `mcp_serve` command
    - Starts MCP server in stdio mode (for Kiro to connect to)
    - Register on main app
    - _Requirements: FR-P2-07.5, FR-P2-07.6_

  - [x] 22.4 Add `tokenlens ml retrain` CLI command
    - Create `src/tokenlens/cli/commands/ml.py` with `ml retrain [--all|--forecaster|--anomaly|--profiler]`
    - Calls the appropriate ML module's `train()` method
    - Shows progress and result (e.g., "Forecaster retrained on 14 days of data" or "Insufficient data: need 7+ days")
    - Register as `ml_app` sub-command group on main app
    - _Requirements: FR-P2-06.2_

  - [x] 22.5 Write unit tests at `tokenlens/tests/unit/test_mcp_server.py`
    - Test tiktoken estimation produces non-zero token counts
    - Test log_conversation_turn creates TokenEvent with estimated=true
    - Test session boundary detection (>15 min gap = new session)
    - Test get_token_status returns correct structure
    - _Requirements: FR-P2-07.1–FR-P2-07.8_

- [x] 23. Phase 2 checkpoint — Ensure all ML and MCP tests pass
  - Run `pytest tests/ -v` — all tests pass
  - Run `ruff check src/` — no errors
  - Verify: `tokenlens ml retrain --all` works (or shows "insufficient data" gracefully)
  - Verify: `tokenlens mcp-serve` starts without error

**Phase 2 notes:**
- API endpoints for ML data are Phase 3 (FastAPI backend)
- Alert engine is Phase 3 (WebSocket + alerts)
- What-if simulator is Phase 3 (needs API endpoints)
- APScheduler replaces simple time checks in Phase 3 when API server is added

---

## Phase 3: FastAPI Backend

- [x] 24. FastAPI app factory, middleware, and dependency injection
  - [x] 24.1 Install API dependencies: `uv pip install -e ".[ml,api,dev]"` in .venv
  - [x] 24.2 Create `src/tokenlens/api/app.py` — app factory with lifespan, health check at `/health`, OpenAPI at `/docs`, default port 7890
  - [x] 24.3 Create `src/tokenlens/api/middleware.py` — CORS, request ID, rate limiter (100 req/s token bucket, 429 response)
  - [x] 24.4 Create `src/tokenlens/api/deps.py` — dependency injection for DB session and config
  - [x] 24.5 Create `src/tokenlens/api/schemas.py` — all Pydantic response models (StatusResponse, TokenEventResponse, SessionResponse, PaginatedResponse[T], analytics/prediction/efficiency/anomaly/settings models, ErrorResponse)
  - [x] 24.6 Write tests at `tests/unit/test_api_middleware.py` — rate limiter, request ID, CORS, health endpoint
  - _Requirements: FR-P3-01.1–FR-P3-01.7_
  - **NOTE:** All routes under `/api/v1/`. No v2 migration strategy needed yet — when breaking changes arise, add `/api/v2/` routes alongside v1 and deprecate v1 with a sunset header.

- [x] 25. REST API endpoints — Status, Events, Sessions
  - [x] 25.1 Create `src/tokenlens/api/routes/status.py` — GET /api/v1/status
  - [x] 25.2 Create `src/tokenlens/api/routes/events.py` — GET /api/v1/events (paginated, filtered). NO SSE stream — WebSocket /ws/live handles real-time (Task 28.1). SSE deferred to Phase 5 as optional.
  - [x] 25.3 Create `src/tokenlens/api/routes/sessions.py` — GET /api/v1/sessions, GET /api/v1/sessions/{id}
  - [x] 25.4 Write tests at `tests/integration/test_api_status.py` — status, events pagination/filtering, sessions, 422/404 errors
  - _Requirements: FR-P3-02.1, FR-P3-02.2, FR-P3-02.4, FR-P3-02.5, FR-P3-06.6, FR-P3-06.7_

- [x] 26. REST API endpoints — Analytics
  - [x] 26.1 Create `src/tokenlens/api/routes/analytics.py` — timeline, heatmap, tools, models, summary
  - [x] 26.2 Write tests at `tests/integration/test_api_analytics.py`
  - _Requirements: FR-P3-03.1–FR-P3-03.5_

- [x] 27. REST API endpoints — Predictions, Efficiency, Anomalies, Settings, Export
  - [ ] 27.1 Create `src/tokenlens/api/routes/predictions.py` — burnrate, limit, budget, profile. NOTE: whatif endpoint deferred until what_if_simulate() is implemented in budget.py (add it here as part of this task).
  - [ ] 27.1a Implement `what_if_simulate()` in `src/tokenlens/ml/budget.py` — accept scenario dict (context_size, model_switch, usage_pct_change), return projected cost impact. Then wire to POST /api/v1/predictions/whatif.
  - [ ] 27.2 Create `src/tokenlens/api/routes/efficiency.py` — sessions, recommendations, trends
  - [ ] 27.3 Create `src/tokenlens/api/routes/anomalies.py` — list, detail
  - [ ] 27.4 Create `src/tokenlens/api/routes/settings.py` — GET settings (reads config + DB overrides), PUT settings (writes to settings DB table ONLY, does NOT modify config.toml). GET /settings/adapters.
  - [ ] 27.5 Create `src/tokenlens/api/routes/export.py` — events CSV/JSON, report
  - [ ] 27.6 Write tests at `tests/integration/test_api_endpoints.py`
  - _Requirements: FR-P3-04.1–FR-P3-06.7_

- [x] 28. WebSocket endpoints and alert engine
  - [ ] 28.1 Create `src/tokenlens/api/websocket.py` — /ws/live (5s push), /ws/alerts, initial payload, 30s ping timeout
  - [ ] 28.2a Create `src/tokenlens/alerts/engine.py` — threshold triggers (50/75/90/100% of daily token limit and monthly cost budget) + dedup (don't send same threshold twice per billing period)
  - [ ] 28.2b Extend alert engine — anomaly alerts (when AnomalyDetector flags spike), predictive alerts (burn rate projects limit hit <2h), model switch detection mid-session
  - [ ] 28.3 Create `src/tokenlens/alerts/desktop.py` — plyer cross-platform notifications (configurable on/off)
  - [ ] 28.4 Create `src/tokenlens/alerts/webhooks.py` — Slack/Discord/Teams webhook POST via httpx async
  - [ ] 28.5 Create `src/tokenlens/cli/commands/serve.py` — `tokenlens serve [--port 7890] [--ui]` starts uvicorn with FastAPI app. Runs ALONGSIDE daemon (daemon collects data, serve exposes API). With `--ui`: mount built React static files via FastAPI StaticFiles.
  - [ ] 28.6 Write tests at `tests/integration/test_websocket.py` — live push, alerts, dedup, cleanup
  - _Requirements: FR-P3-07.1–FR-P3-08.8_

- [x] 29. Phase 3 checkpoint — bump version to 0.2.0
  - Run all tests — pass. Run ruff — clean.
  - Verify: `tokenlens serve` starts on port 7890, `/docs` shows OpenAPI, `/health` returns ok
  - Update `__version__` to `"0.2.0"` in `__init__.py`

---

## Phase 4: Web Dashboard

- [ ] 30. React app scaffold and infrastructure
  - [x] 30.1 Initialize `tokenlens/ui/` — Vite 6 + React 18 + TypeScript strict, path aliases
  - [ ] 30.2 Install TailwindCSS **v3** + shadcn/ui (v3 is stable and fully supported by shadcn/ui; v4 deferred until shadcn/ui confirms support)
  - [ ] 30.3 Set up Zustand stores (useTokenStore, useSettingsStore, useMLStore), TanStack Query v5, React Router (/, /analytics, /insights, /settings)
  - [ ] 30.4 Implement `useWebSocket` hook (auto-reconnect, exponential backoff), Layout with sidebar nav, dark/light mode toggle
  - [ ] 30.5 Add build integration: `vite build` → output to `tokenlens/ui/dist/`. Add `[ui]` optional extra in pyproject.toml that includes pre-built static files. `tokenlens serve --ui` mounts `dist/` via FastAPI `StaticFiles`.
  - [x] 30.6 Write component tests — useWebSocket, store updates, theme toggle
  - _Requirements: FR-P4-01.1–FR-P4-01.9_
  - **NOTE:** Frontend ships as pre-built static files in the `[ui]` optional extra. No Node.js required at runtime. Build step only needed for development.

- [ ] 31. Home page — Command Center
  - [ ] 31.1 LiveTokenCounter — CSS transition animated number (no Framer Motion — plain CSS `transition: all 0.3s` on number change is sufficient and saves ~30KB gzipped), WebSocket-driven, interpolation between 5s snapshots
  - [x] 31.2 StatsGrid — UsageRingChart (Recharts PieChart), BurnRateGauge (custom SVG), ResetCountdown
  - [ ] 31.3 ToolStatusCards (per tool: icon, tokens, active dot, sparkline, cost) + SmartAlertBanner
  - [ ] 31.4 Write component tests — all components with loading/empty/error states
  - _Requirements: FR-P4-02.1–FR-P4-02.4_

- [ ] 32. Analytics page — Deep Dive
  - [x] 32.1 TimePeriodSelector (24h|7d|30d) + TokenUsageTimeline (Recharts stacked AreaChart with brush zoom)
  - [ ] 32.2 ToolComparisonBarChart (Recharts) + ModelUsagePieChart (Recharts)
  - [ ] 32.3 TokenIntensityHeatmap (D3.js 24×7 matrix, tooltip on hover) — D3 ONLY for heatmap, Recharts for everything else
  - [ ] 32.4 SessionList with expandable rows (per-turn breakdown table, context growth sparkline, cache ratio) — replaces D3 waterfall chart. Simple table delivers same value in 1/5th the time.
  - [x] 32.5 Write component tests — period selector, charts with mock data, expandable row interaction
  - _Requirements: FR-P4-03.1–FR-P4-03.6_

- [ ] 33. Insights page and Settings page
  - [x] 33.1 Insights: ForecastChart (Recharts, confidence bands), PredictionCard, CostProjection, EfficiencyTrend, AnomalyTimeline, WhatIfSimulator, ProfileCard, ColdStartBanner (3 states)
  - [ ] 33.2 Settings: ToolConfig, BudgetLimits, AlertConfig, ModelPricing, DataManagement, About — save via PUT /api/v1/settings (writes to DB only, not TOML)
  - [x] 33.3 Write component tests — cold start states, simulator sliders, settings save
  - _Requirements: FR-P4-04.1–FR-P4-05.7_

- [x] 34. Phase 4 checkpoint — bump version to 0.3.0
  - `npm run build` in ui/ — succeeds. Frontend tests pass.
  - `tokenlens serve --ui` serves dashboard at localhost:7890. All 4 pages render.
  - Update `__version__` to `"0.3.0"`

---

## Phase 5: CLI & Integrations

- [-] 35. Full CLI command suite
  - [ ] 35.1 Implement `tokenlens live` — Textual TUI (top bar, left panel per-tool, center timeline, right session info, bottom alerts, keyboard shortcuts q/r/t/?). Add `textual` to `[tui]` optional extra in pyproject.toml, NOT core deps.
  - [ ] 35.2 Implement `tokenlens report --period today|week|month [--format table|json|markdown]` — formatted report with summaries
  - [ ] 35.3 Implement `tokenlens predict` — burn rate forecast, limit prediction, monthly cost projection (linear fallback if no ML)
  - [ ] 35.4 Implement `tokenlens compare` (tool comparison table), `tokenlens why` (explain last anomaly), `tokenlens optimize` (top 3-5 recommendations)
  - [ ] 35.5 Implement `tokenlens export --format csv|json --period --output` — queries DB directly via `get_session()` (NO temporary in-process server). Simple and reliable.
  - [ ] 35.6 Write tests for all CLI commands with mock data
  - _Requirements: FR-P5-01.1–FR-P5-01.10_

- [ ] 36. Shell prompt integration and Kiro steering
  - [ ] 36.1 Implement `tokenlens shell-hook --shell bash|zsh|fish` — PS1 snippet output
  - [ ] 36.2 Implement `tokenlens status --short` — "42K/100K" format, <200ms, empty string if API unreachable
  - [ ] 36.3 Implement Kiro steering file auto-generation at `.kiro/steering/token-budget.md` — usage, burn rate, tips, cost context. Triggered by `MLTaskRunner.run_due_tasks()` in daemon (every 30 min check alongside ML tasks). Configurable via `[integrations.kiro]`.
  - [ ] 36.4 Create Kiro hook template `.kiro/hooks/tokenlens-session-end.json`
  - [ ] 36.5 Write tests for shell hook, status --short, steering file content
  - _Requirements: FR-P5-02.1–FR-P5-03.4_

- [ ]* 37. MCP Server enhancements (stretch)
  - Add `get_burn_rate_forecast`, `get_session_summary`, `suggest_model_switch`, `log_tool_use` tools
  - _Requirements: FR-P5-04.1–FR-P5-04.2_

- [x] 38. Phase 5 checkpoint — bump version to 0.4.0
  - All tests pass. `tokenlens live` renders TUI. `tokenlens report --period today` works. `tokenlens shell-hook --shell bash` outputs valid snippet.
  - Update `__version__` to `"0.4.0"`

---

## Phase 6: Distribution & Polish

- [ ] 39. PyPI packaging and Docker
  - [ ] 39.1 Finalize pyproject.toml — all extras (`[ml]`, `[ml-prophet]`, `[api]`, `[ui]`, `[tui]`, `[all]`), classifiers, project URLs, verify entry points
  - [ ] 39.2 Create multi-stage `Dockerfile` — two variants: `tokenlens:slim` (no ML, <300MB) and `tokenlens:full` (with ML, <800MB). Full image includes Prophet + pandas + numpy + sklearn + React build.
  - [ ] 39.3 Create `docker-compose.yml` — single service, volume mounts (~/.claude:ro, ~/.kiro:ro, ~/.tokenlens:/data), `docker compose up -d`
  - _Requirements: FR-P6-01.1–FR-P6-02.3_

- [ ] 40. CI/CD pipeline (GitHub Actions)
  - [ ] 40.1 Create `.github/workflows/ci.yml` — ruff, mypy, pytest with tiered coverage gates: **85% overall, 95% for core/adapters/agent, 75% for ml/**. Biome frontend lint, Vitest frontend tests, uv build + Vite build.
  - [ ] 40.2 Create `.github/workflows/release.yml` — build, publish PyPI, Docker GHCR, changelog, GitHub Release
  - [ ] 40.3 Create `dependabot.yml` for weekly updates
  - _Requirements: FR-P6-03.1–FR-P6-03.4_

- [ ] 41. Documentation (MkDocs Material) — written AFTER Phase 5 when all features are locked
  - [ ] 41.1 Set up MkDocs Material at `tokenlens/docs/` with mkdocs.yml
  - [ ] 41.2 Write pages: index, installation, getting-started, configuration, adapters (claude-code, kiro, developing), cli, api (auto-generated from OpenAPI), ml, dashboard, contributing, changelog
  - [ ] 41.3 Create comprehensive README.md — badges, screenshot/GIF, 3-step quick start, features, architecture diagram, MIT license
  - _Requirements: FR-P6-05.1, FR-P6-07.1_

- [ ] 42. Data retention and final testing
  - [ ] 42.1 Implement `tokenlens data archive --before <date>` — export + compress to .tar.gz, remove from DB
  - [ ] 42.2 Implement `tokenlens data prune --keep-days <N>` — delete old events with confirmation
  - [ ] 42.3 Implement 500MB DB size warning in `tokenlens status` and dashboard Settings
  - [ ] 42.4 Final coverage push — `pytest --cov` with tiered gates (85% overall, 95% core, 75% ml), add missing tests
  - _Requirements: FR-P6-06.1, FR-P6-06.2, FR-P6-08.1–FR-P6-08.3_

- [x] 43. Phase 6 checkpoint — bump version to 1.0.0
  - All tests pass with tiered coverage gates. ruff + mypy clean.
  - `pip install tokenlens` works from wheel. `docker compose up -d` starts.
  - `mkdocs serve` renders docs. `tokenlens --help` shows all commands.
  - Update `__version__` to `"1.0.0"`

---

## Notes

- Task 37 (MCP enhancements) is the only optional (`*`) task — stretch goal
- ALL other tasks are mandatory including test tasks
- Phase 1 (tasks 1-18): Complete ✅ — v0.1.0 — 95 tests
- Phase 2 (tasks 19-23): Complete ✅ — v0.1.0 — 162 tests total
- Phase 3 (tasks 24-29): FastAPI backend → v0.2.0
- Phase 4 (tasks 30-34): React dashboard → v0.3.0
- Phase 5 (tasks 35-38): CLI + integrations → v0.4.0
- Phase 6 (tasks 39-43): Distribution → v1.0.0
- Checkpoints at tasks 29, 34, 38, 43 with version bumps
- Coverage gates: 85% overall, 95% core/adapters/agent, 75% ml/
- Key decisions: no SSE (WebSocket only), TailwindCSS v3 (not v4), no Framer Motion (CSS transitions), no D3 waterfall (expandable table), textual as [tui] optional, export queries DB directly, PUT settings writes DB only (not TOML), two Docker images (slim/full)
