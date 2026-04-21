# TokenLens — Requirements Document

## 1. Vision & Goals

TokenLens is an open-source, local-first token monitoring and prediction platform for AI coding tools. It collects token usage data from Claude Code (direct JSONL parsing) and Kiro (session parsing + tiktoken estimation), stores it in a unified schema, provides ML-powered predictions, and surfaces insights through a web dashboard and CLI.

**Primary Users:** Individual developers using AI coding assistants who want visibility into token consumption, cost tracking, burn rate predictions, and efficiency insights.

**Core Differentiators vs claude-monitor:**
- Multi-tool support (Claude Code + Kiro day one, extensible adapter SDK for community)
- Web dashboard with real-time WebSocket updates (not terminal-only)
- ML predictions using Prophet and scikit-learn (not just linear extrapolation)
- Context efficiency scoring per session
- Cross-tool comparison analytics
- Plugin adapter SDK for community extensions

## 2. User Stories

### Phase 1 Stories
- **US-P1-01:** As a developer using Claude Code, I want my token usage automatically collected from local JSONL logs, so that I have accurate consumption data without manual tracking.
- **US-P1-02:** ~~Moved to Phase 2~~ See US-P2-07.
- **US-P1-03:** As a developer, I want a unified schema for all token events, so that data from any tool is stored consistently and queryable.
- **US-P1-04:** As a developer, I want a background daemon that watches log files and ingests new events automatically, so that my data is always current.
- **US-P1-05:** As a developer, I want a CLI command to check my current token usage, so that I can quickly see today's consumption from the terminal.
- **US-P1-06:** As a developer, I want sessions auto-detected by activity gaps, so that I can analyze usage per coding session.
- **US-P1-07:** As a developer, I want cost calculated automatically using model pricing, so that I know how much I'm spending.
- **US-P1-08:** As a plugin developer, I want a well-defined adapter SDK, so that I can integrate new AI tools into TokenLens.

### Phase 2 Stories
- **US-P2-01:** As a developer, I want burn rate forecasts with confidence bands, so that I can anticipate when I'll approach usage limits.
- **US-P2-02:** As a developer, I want anomaly detection on my usage, so that I'm aware of unexpected consumption spikes.
- **US-P2-03:** As a developer, I want per-session efficiency scores, so that I can optimize how I use AI tools.
- **US-P2-04:** As a developer, I want behavioral profiling of my usage patterns, so that I can identify my most productive hours.
- **US-P2-05:** As a developer, I want end-of-month cost projections, so that I can manage my AI spending.
- **US-P2-06:** As a developer, I want a what-if simulator, so that I can explore cost impacts of changing my usage habits.
- **US-P2-07:** As a developer using Kiro, I want a TokenLens MCP server I can connect to Kiro, so that my token usage is captured via tiktoken estimation during conversations.

### Phase 3 Stories
- **US-P3-01:** As a dashboard developer, I want a REST API for all platform data, so that the web UI can fetch analytics programmatically.
- **US-P3-02:** As a dashboard user, I want real-time WebSocket updates, so that I can monitor usage live without refreshing.
- **US-P3-03:** As a developer, I want configurable alerts for budget thresholds and anomalies, so that I'm notified before problems occur.
- **US-P3-04:** As a developer, I want webhook support for Slack/Discord/Teams, so that alerts reach me where I work.

### Phase 4 Stories
- **US-P4-01:** As a developer, I want a home dashboard showing live token count, budget status, and burn rate, so that I can assess consumption at a glance.
- **US-P4-02:** As a developer, I want deep analytics with cross-tool timelines, heatmaps, and session waterfalls, so that I can understand usage patterns in depth.
- **US-P4-03:** As a developer, I want an ML insights page with forecast charts and anomaly markers, so that I can plan usage proactively.
- **US-P4-04:** As a developer, I want a settings page to configure adapters, budgets, and alerts, so that I can customize TokenLens.

### Phase 5 Stories
- **US-P5-01:** As a terminal user, I want a full-screen live TUI dashboard, so that I can monitor tokens without leaving the terminal.
- **US-P5-02:** As a developer, I want CLI commands for reports, predictions, comparisons, and optimization tips.
- **US-P5-03:** As a Kiro user, I want auto-generated steering files with budget context, so that token awareness is embedded in my workflow.
- **US-P5-04:** As a developer, I want shell prompt integration showing token count in PS1.

### Phase 6 Stories
- **US-P6-01:** As a user, I want to install TokenLens via pip or Docker with minimal setup.
- **US-P6-02:** As a contributor, I want automated CI/CD with linting, type checking, and 90% test coverage gates.
- **US-P6-03:** As a user, I want comprehensive documentation covering installation, configuration, adapters, CLI, API, and ML.

## 3. Functional Requirements

### Phase 1: Core Data Fabric

#### FR-P1-01: Unified TokenEvent Schema [P1]

1. [P1] THE TokenEvent schema SHALL define a Pydantic v2 model with the following required fields: id (UUID auto-generated), tool (Enum: "claude_code" | "kiro"), model (string), user_id (string), session_id (UUID string), timestamp (datetime with timezone), input_tokens (int), output_tokens (int), cost_usd (float, defaults to 0.0 — calculated by pipeline), context_type (string: "chat" | "code_generation" | "code_review" | "unknown"), and turn_number (int).
2. [P1] THE TokenEvent schema SHALL define the following optional fields with defaults: cache_read_tokens (int, default 0), cache_write_tokens (int, default 0), file_types_in_context (list of strings, default empty), tool_calls (list of strings, default empty), and raw_metadata (JSON dict, default empty).
3. [P1] WHEN a TokenEvent is created with a missing required field, THE schema SHALL reject the event with a Pydantic ValidationError identifying the missing field.
4. [P1] THE TokenEvent schema SHALL enforce that input_tokens, output_tokens, cache_read_tokens, and cache_write_tokens are non-negative integers.
5. [P1] THE TokenEvent schema SHALL enforce that cost_usd is a non-negative float.
6. [P1] WHEN a TokenEvent is serialized to JSON and deserialized back, THE schema SHALL produce an equivalent object (round-trip property).

#### FR-P1-02: Session Model [P1]

1. [P1] THE Session model SHALL define: id (UUID), tool (Enum), start_time (datetime), end_time (datetime), total_input_tokens (int), total_output_tokens (int), total_cost_usd (float), turn_count (int), and efficiency_score (float, nullable — populated in Phase 2).
2. [P1] WHEN a session is closed (inactivity gap >15 minutes detected or daemon shutdown), THE system SHALL compute and persist total_input_tokens, total_output_tokens, total_cost_usd, and turn_count by aggregating all TokenEvents with matching session_id. Sessions SHALL NOT be recalculated on every insert or read.

#### FR-P1-03: Model Pricing Table [P1]

1. [P1] THE platform SHALL provide a hardcoded pricing dictionary: Claude Sonnet 4 (input $3/1M, output $15/1M), Claude Opus 4 (input $15/1M, output $75/1M), Claude Haiku 3.5 (input $0.80/1M, output $4/1M), Kiro Auto (same as Claude Sonnet 4 pricing).
2. [P1] THE pricing table SHALL be stored in a TOML config file so users can update pricing without code changes.
3. [P1] WHEN a TokenEvent is created, THE platform SHALL auto-calculate cost_usd from the model pricing table using: (input_tokens * input_price / 1_000_000) + (output_tokens * output_price / 1_000_000).
4. [P1] WHEN the model name from a log entry does not exactly match a pricing table key, THE system SHALL attempt fuzzy matching by stripping version suffixes and date stamps (e.g., "claude-sonnet-4-20250514" → "claude-sonnet-4"). IF no match is found, THE system SHALL set cost_usd to 0.0 and log a warning with the unrecognized model name.

#### FR-P1-04: Adapter SDK [P1]

1. [P1] THE Adapter SDK SHALL define an abstract base class `ToolAdapter` with: `name` (str property), `discover() -> bool`, `get_log_paths() -> list[Path]`, `parse_file(path: Path) -> list[TokenEvent]`, `watch(callback: Callable[[TokenEvent], None])`, and `get_last_processed_position(path: Path) -> int`.
2. [P1] WHEN `discover()` is called, THE adapter SHALL return True if the tool's log files exist on the local machine, False otherwise.
3. [P1] WHEN `parse_file()` is called with a non-existent path, THE adapter SHALL raise FileNotFoundError with the invalid path in the message.
4. [P1] THE Adapter SDK SHALL provide a `version` property returning the semantic version string of the adapter.
5. [P1] Adapter methods (`discover`, `get_log_paths`, `parse_file`, `get_last_processed_position`) are synchronous. THE daemon SHALL execute adapter methods in a thread pool via `asyncio.to_thread()` to avoid blocking the async event loop.

#### FR-P1-05: Adapter Registry [P1]

1. [P1] THE Adapter Registry SHALL auto-discover adapters via Python entry_points under the group `tokenlens.adapters`.
2. [P1] THE Adapter Registry SHALL provide built-in registration for Claude Code and Kiro adapters.
3. [P1] THE Adapter Registry SHALL provide `get_available() -> list[ToolAdapter]` returning only adapters whose `discover()` returns True.
4. [P1] IF a discovered entry_point fails to load, THEN THE Registry SHALL log a warning and continue loading remaining adapters.
5. [P1] IF two adapters register with the same name, THEN THE Registry SHALL log a warning and keep the first registered adapter.

#### FR-P1-06: Claude Code Adapter [P1]

1. [P1] THE Claude Code Adapter SHALL parse `~/.claude/projects/**/*.jsonl` files where each line is a JSON object representing a conversation turn.
2. [P1] THE Claude Code Adapter SHALL extract: role, model, timestamp, input_tokens, output_tokens, cache_creation_input_tokens, and cache_read_input_tokens from each JSONL entry.
3. [P1] THE Claude Code Adapter SHALL track file read position per JSONL file (stored in adapter_state DB table) to avoid reprocessing on subsequent reads.
4. [P1] THE Claude Code Adapter SHALL handle file rotation and new project directories appearing dynamically.
5. [P1] WHEN the adapter encounters a malformed JSON line, THE adapter SHALL skip that line, log a warning with the line number, and continue parsing.
6. [P1] THE Claude Code Adapter SHALL apply session boundary logic: if gap between consecutive turns >15 minutes, start a new session.

#### FR-P1-07: Kiro Adapter — Deferred to Phase 2 [P1]

1. [P1] THE Kiro Adapter SHALL be deferred to Phase 2. Phase 1 ships with Claude Code adapter only.
2. [P1] THE Adapter SDK and Registry SHALL still ship in Phase 1 to support future adapters including Kiro and community-contributed adapters.
3. [P1] THE TokenEvent schema tool Enum SHALL include "kiro" from Phase 1 for forward compatibility, even though the Kiro adapter is not yet available.
4. [P1] THE `tokenlens status` output SHALL only show tools with active adapters. In Phase 1, this means Claude Code only.

**RATIONALE:** Kiro does not store conversation/session data locally in any parseable format. The `~/.kiro/` directory contains only configuration, extensions, skills, and steering files — no chat logs, no JSONL, no session exports. The tiktoken-on-saved-sessions approach originally planned is not feasible. Kiro integration will use an MCP Server approach in Phase 2 (see FR-P2-07).

#### FR-P1-08: SQLite Storage Layer [P1]

1. [P1] THE database layer SHALL use SQLAlchemy 2.0 async engine with aiosqlite, storing the database at `~/.tokenlens/tokenlens.db`.
2. [P1] THE database SHALL define tables: `token_events` (maps to TokenEvent), `sessions` (maps to Session), `adapter_state` (per-file read positions and last processed timestamps), and `settings` (key-value store for user configuration).
3. [P1] THE database layer SHALL use Alembic for all schema migrations from day one, supporting the SQLite dialect.
4. [P1] THE database layer SHALL create indexes on token_events for: timestamp, tool, model, user_id, and session_id.

#### FR-P1-09: Background Collection Daemon [P1]

1. [P1] THE daemon SHALL use watchdog FileSystemEventHandler to monitor log directories (inotify on Linux, FSEvents on macOS — not polling).
2. [P1] WHEN a file change event is detected, THE daemon SHALL call the adapter's parse method for new data only, using the stored read position.
3. [P1] THE daemon SHALL batch events and flush to the database every 2 seconds.
4. [P1] THE daemon SHALL apply session boundary detection: if >15 minutes gap between events from the same tool, close the current session and start a new one.
5. [P1] WHEN the daemon receives SIGTERM or SIGINT, THE daemon SHALL flush all pending events before shutting down.
6. [P1] THE daemon SHALL write a PID file at `~/.tokenlens/agent.pid` and a heartbeat timestamp at `~/.tokenlens/agent.health`.
7. [P1] THE daemon SHALL log to `~/.tokenlens/logs/agent.log` via structlog.
8. [P1] ON startup, THE daemon SHALL auto-discover adapters, run an initial full parse of existing log files, then switch to watch mode.
9. [P1] THE daemon SHALL deduplicate events using the primary key of (tool, source_file_path, file_byte_offset). The adapter_state read position tracking is the primary dedup mechanism; this check is a safety net for edge cases like daemon restart mid-flush.
10. [P1] THE daemon SHALL work without root/sudo privileges.
11. [P1] IF the database is unavailable during a flush, THEN THE daemon SHALL retain pending events in memory and retry after 5 seconds, up to 10 retries.
12. [P1] THE daemon SHALL run a periodic full-scan fallback every 5 minutes in case watchdog loses events.
13. [P1] WHEN `tokenlens agent start` is called and a PID file exists with a running process, THE CLI SHALL print "Agent already running (PID: XXXX)" and exit with code 1. WHEN the PID file exists but the process is dead, THE CLI SHALL remove the stale PID file and start normally.

#### FR-P1-10: Basic CLI (Phase 1 Subset) [P1]

1. [P1] THE CLI SHALL use Typer and provide: `tokenlens init`, `tokenlens agent start [--foreground]`, `tokenlens agent stop`, `tokenlens agent status`, and `tokenlens status`.
2. [P1] `tokenlens init` SHALL create `~/.tokenlens/` directory, generate default `config.toml`, run adapter discovery, and print which tools were found.
3. [P1] `tokenlens agent start` SHALL start the background daemon (daemonize by default, foreground with `--foreground` flag).
4. [P1] `tokenlens agent stop` SHALL stop the daemon via PID file.
5. [P1] `tokenlens agent status` SHALL show daemon running state, last heartbeat, and events processed count.
6. [P1] `tokenlens status` SHALL display a one-line summary showing only active adapters. In Phase 1 (Claude Code only): "Today: 45,231 tokens | Claude Code: 45K | Cost: $0.42 | Burn: normal". When Kiro adapter is active (Phase 2+): "Today: 45,231 tokens | Claude Code: 38K | Kiro: 7K (est.) | Cost: $0.42 | Burn: normal".

#### FR-P1-11: Configuration System [P1]

1. [P1] THE configuration SHALL use dynaconf with TOML format at `~/.tokenlens/config.toml`.
2. [P1] THE config SHALL support sections: `[general]` (user_id, data_dir), `[adapters.claude_code]` (enabled, log_path, session_gap_minutes), `[adapters.kiro]` (enabled, log_path, session_gap_minutes, estimation_model), `[pricing]` (model pricing overrides), `[daemon]` (poll_interval_seconds, batch_write_interval_seconds).
3. [P1] THE configuration SHALL support environment variable overrides with prefix `TOKENLENS_` (e.g., `TOKENLENS_GENERAL__USER_ID`).
4. [P1] THE configuration SHALL provide sensible defaults so TokenLens runs without any config file on first launch.


### Phase 2: Intelligence Engine (ML Layer)

#### FR-P2-01: Burn Rate Forecasting [P2]

1. [P2] WHEN at least 7 days of historical data are available, THE Burn_Rate_Forecaster SHALL train a Prophet time-series model on hourly token consumption with hour-of-day and day-of-week seasonality.
2. [P2] THE Burn_Rate_Forecaster SHALL output predicted token usage for the next 24 hours with 80% and 95% confidence intervals.
3. [P2] THE Burn_Rate_Forecaster SHALL produce a prediction: "At current rate, you will exhaust your daily limit in X hours Y minutes".
4. [P2] WHEN fewer than 7 days of data are available, THE Burn_Rate_Forecaster SHALL fall back to linear extrapolation: (total_today / hours_elapsed * 24).
5. [P2] THE Burn_Rate_Forecaster SHALL auto-retrain daily via APScheduler at midnight local time (configurable).
6. [P2] THE Burn_Rate_Forecaster SHALL persist trained models to `~/.tokenlens/models/forecaster.joblib`.
7. [P2] THE Burn_Rate_Forecaster SHALL train separate models per tool (Claude Code and Kiro).
8. [P2] WHEN the forecaster produces a prediction, THE output SHALL include the model type used (Prophet or linear) in the metadata.

#### FR-P2-02: Anomaly Detection [P2]

1. [P2] THE Anomaly_Detector SHALL use scikit-learn IsolationForest trained on a rolling 14-day personal baseline.
2. [P2] THE feature vector per hour SHALL include: total_tokens, input_ratio, output_ratio, session_count, avg_turn_count, and dominant_tool_flag.
3. [P2] THE Anomaly_Detector SHALL flag an anomaly when the IsolationForest score falls below a configurable threshold (default -0.3).
4. [P2] WHEN an anomaly is detected, THE Anomaly_Detector SHALL classify the spike using configurable rules (defaults: input_tokens >> output_tokens → "Large context loading", turn_count > configurable threshold (default 30) → "Extended conversation", tokens/hour > configurable multiplier (default 3x) of daily average → "Usage burst", new tool appears → "New tool detected"). All classification thresholds SHALL be configurable in config.toml under `[ml.anomaly]`.
5. [P2] THE Anomaly_Detector SHALL store anomaly records in an `anomalies` DB table with: timestamp, severity (warning/critical), classification, and description.
6. [P2] THE Anomaly_Detector SHALL retrain weekly or on-demand via `tokenlens ml retrain`.
7. [P2] IF fewer than 14 days of data are available, THEN THE Anomaly_Detector SHALL use all available data and flag reduced confidence in the anomaly metadata.

#### FR-P2-03: Context Efficiency Engine [P2]

1. [P2] THE Efficiency_Engine SHALL compute a per-session efficiency score from 0 to 100 using weighted factors: Output/Input ratio (30%), Cache hit rate (25%), Turns to completion (20%), Context growth slope (15%), Cost per output token (10%).
2. [P2] THE Efficiency_Engine SHALL normalize each factor to 0-100 before applying weights using these ranges: Output/Input ratio (0.0 → score 0, ≥0.5 → score 100, linear between), Cache hit rate (0% → 0, ≥50% → 100), Turns to completion (≥50 turns → 0, ≤5 turns → 100), Context growth slope (≥10% growth/turn → 0, ≤1% growth/turn → 100), Cost per output token (≥$0.001 → 0, ≤$0.0001 → 100).
3. [P2] THE Efficiency_Engine SHALL also normalize the final weighted score as a percentile against the user's own historical sessions.
3. [P2] THE Efficiency_Engine SHALL detect waste patterns: "Repeated context loading" (same large input across >5 consecutive turns), "Excessive back-and-forth" (>20 turns with <100 output tokens each), "Context bloat" (input tokens growing >10% per turn consistently).
4. [P2] WHEN a session scores below 30, THE Efficiency_Engine SHALL generate a recommendation describing the waste pattern and a suggested improvement.
5. [P2] THE Efficiency_Engine SHALL provide cross-tool efficiency comparison by computing average scores per tool over a configurable window (default 7 days).
6. [P2] THE Efficiency_Engine SHALL store scores in the sessions table `efficiency_score` column.

#### FR-P2-04: Behavioral Profiling [P2]

1. [P2] THE Behavioral_Profiler SHALL use KMeans clustering on daily usage feature vectors: peak_hour, total_tokens, session_count, avg_session_duration_minutes, dominant_tool, input_output_ratio, first_active_hour, last_active_hour.
2. [P2] THE Behavioral_Profiler SHALL cluster into archetypes: "Morning Sprinter" (peak 6-10 AM), "Steady Coder" (even distribution), "Burst Builder" (long quiet then spikes), "Night Owl" (peak after 8 PM), "Explorer" (frequent tool switching).
3. [P2] THE Behavioral_Profiler SHALL detect productive hours: when the highest output_tokens/input_tokens ratio occurs.
4. [P2] THE Behavioral_Profiler SHALL generate a weekly drift report: "This week you shifted from Steady Coder to Burst Builder pattern".
5. [P2] THE Behavioral_Profiler SHALL require a minimum of 14 days of data to generate profiles.

#### FR-P2-05: Budget Forecasting [P2]

1. [P2] THE Budget_Forecaster SHALL derive cost projections by applying the pricing table to the Burn_Rate_Forecaster's token predictions, NOT by training a separate Prophet model on cost data directly. This ensures token and cost projections are always consistent.
2. [P2] THE Budget_Forecaster SHALL provide per-tool cost attribution breakdown.
3. [P2] THE Budget_Forecaster SHALL compute a smart daily budget recommendation: (monthly_budget - spent_so_far) / remaining_days.
4. [P2] WHEN projected end-of-month cost exceeds the configured monthly budget by >10%, THE Budget_Forecaster SHALL flag the projection as over_budget.
5. [P2] THE What-If Simulator SHALL accept scenario inputs: "reduce average context to X tokens", "switch from Opus to Sonnet for routine tasks", "increase/decrease tool usage by X%" — and return projected cost impact.
6. [P2] THE budget settings SHALL be stored in config: daily_token_limit and monthly_cost_budget per tool.

#### FR-P2-06: ML Service Layer [P2]

1. [P2] ALL ML modules SHALL expose a consistent interface: `train(data) -> model`, `predict(model, input) -> result`, `evaluate(model, test_data) -> metrics`.
2. [P2] THE ML layer SHALL use APScheduler jobs: daily (retrain forecaster, update efficiency scores, refresh budget projections), weekly (retrain anomaly detector, update behavioral profiles), on-demand (`tokenlens ml retrain --all`).
3. [P2] THE ML layer SHALL cache results in DB tables: predictions, anomalies, efficiency_scores, profiles.
4. [P2] THE ML layer SHALL support a feature flag to disable ML entirely for users who just want basic tracking.

#### FR-P2-07: TokenLens MCP Server for Kiro Integration [P2]

1. [P2] THE TokenLens MCP Server SHALL provide a `log_conversation_turn` tool that accepts: role (string: "user" | "assistant"), content (string: message text), model (optional string, default "kiro-auto"), and timestamp (optional datetime, default now).
2. [P2] THE `log_conversation_turn` tool SHALL estimate tokens via tiktoken with `cl100k_base` encoding on the provided content, create a TokenEvent with `tool: "kiro"` and `estimated: true` in raw_metadata, and store it in the database.
3. [P2] THE MCP Server SHALL provide a `get_token_status` tool that returns the current day's usage summary (total tokens, cost, burn rate, per-tool breakdown).
4. [P2] THE MCP Server SHALL provide a `get_efficiency_tips` tool that returns the top 3 optimization recommendations based on recent session patterns.
5. [P2] THE MCP Server SHALL run as a subprocess via stdio transport, configured in `.kiro/settings/mcp.json` with the following config structure:
   ```json
   {
     "mcpServers": {
       "tokenlens": {
         "command": "tokenlens",
         "args": ["mcp-serve"],
         "disabled": false
       }
     }
   }
   ```
6. [P2] THE CLI SHALL provide a `tokenlens mcp-serve` command that starts the MCP server in stdio mode (for Kiro to connect to).
7. [P2] THE MCP Server SHALL apply session boundary detection: if >15 minutes gap between `log_conversation_turn` calls, start a new session.
8. [P2] THE MCP Server SHALL mark all Kiro-originated events with `estimated: true` in raw_metadata and display "(est.)" suffix on Kiro numbers in all UI and CLI outputs.


### Phase 3: FastAPI Backend (API Layer)

#### FR-P3-01: FastAPI Application [P3]

1. [P3] THE API SHALL use FastAPI with an app factory pattern in `api/app.py`.
2. [P3] THE API SHALL use a lifespan handler to initialize DB, start APScheduler, and start adapter watchers.
3. [P3] THE API SHALL include CORS middleware with configurable origins (default localhost).
4. [P3] THE API SHALL include request ID middleware for tracing and structured error response handlers.
5. [P3] THE API SHALL implement basic rate limiting of 100 requests/second per client using an in-memory token bucket, to prevent accidental DB overload from reconnect loops or misbehaving clients.
6. [P3] THE API SHALL serve OpenAPI docs at `/docs` and a health check at `/health`.
7. [P3] THE API SHALL run on `localhost:7890` by default (configurable via config).

#### FR-P3-02: REST Endpoints — Status & Events [P3]

1. [P3] `GET /api/v1/status` SHALL return: today's tokens per tool, active sessions, burn rate, and daemon health.
2. [P3] `GET /api/v1/events` SHALL return paginated TokenEvents with filters: tool, model, date_from, date_to, session_id. Params: page, per_page (default 50), sort_by, sort_order.
3. [P3] `GET /api/v1/events/stream` SHALL provide an SSE stream of new events as they arrive.
4. [P3] `GET /api/v1/sessions` SHALL return paginated session list with aggregates: total tokens, cost, duration, efficiency score.
5. [P3] `GET /api/v1/sessions/{session_id}` SHALL return per-turn token breakdown, context growth chart data, and cache hit ratio.

#### FR-P3-03: REST Endpoints — Analytics [P3]

1. [P3] `GET /api/v1/analytics/timeline` SHALL return aggregated time-series data with params: period (1h/1d/1w), date_from, date_to, tool, model. Returns: [{timestamp, input_tokens, output_tokens, cost_usd, tool}].
2. [P3] `GET /api/v1/analytics/heatmap` SHALL return an hour-of-day (0-23) × day-of-week (0-6) token intensity matrix.
3. [P3] `GET /api/v1/analytics/tools` SHALL return per-tool comparison: {tool, total_tokens, total_cost, session_count, avg_efficiency}.
4. [P3] `GET /api/v1/analytics/models` SHALL return per-model breakdown: {model, total_tokens, total_cost, usage_count, avg_input, avg_output}.
5. [P3] `GET /api/v1/analytics/summary` SHALL return rolling totals: today, this_week, this_month, all_time — per-tool and aggregate.

#### FR-P3-04: REST Endpoints — ML Predictions [P3]

1. [P3] `GET /api/v1/predictions/burnrate` SHALL return forecast for next 24h: [{hour, predicted_tokens, lower_80, upper_80, lower_95, upper_95}].
2. [P3] `GET /api/v1/predictions/limit` SHALL return "Will hit limit at HH:MM" with confidence percentage.
3. [P3] `GET /api/v1/predictions/budget` SHALL return: {projected_cost, budget_remaining, daily_recommendation, per_tool_breakdown}.
4. [P3] `POST /api/v1/predictions/whatif` SHALL accept scenario params in request body and return projected impact.
5. [P3] `GET /api/v1/predictions/profile` SHALL return current behavioral archetype and productive hours.

#### FR-P3-05: REST Endpoints — Efficiency & Anomalies [P3]

1. [P3] `GET /api/v1/efficiency/sessions` SHALL return sessions ranked by efficiency score with filters.
2. [P3] `GET /api/v1/efficiency/recommendations` SHALL return top 5 actionable suggestions based on recent patterns.
3. [P3] `GET /api/v1/efficiency/trends` SHALL return efficiency score trend: [{date, avg_score, tool}].
4. [P3] `GET /api/v1/anomalies` SHALL return detected anomalies with filters: severity, date_from, date_to, classification.
5. [P3] `GET /api/v1/anomalies/{id}` SHALL return single anomaly detail with context.

#### FR-P3-06: REST Endpoints — Settings & Export [P3]

1. [P3] `GET /api/v1/settings` SHALL return current configuration.
2. [P3] `PUT /api/v1/settings` SHALL update configuration (budget limits, alert thresholds, adapter paths).
3. [P3] `GET /api/v1/settings/adapters` SHALL return discovered adapters and their status.
4. [P3] `GET /api/v1/export/events` SHALL download events as CSV or JSON with params: format, date_from, date_to, tool.
5. [P3] `GET /api/v1/export/report` SHALL generate a usage report with params: period (today/week/month), format (json/csv/markdown).
6. [P3] WHEN an API request contains invalid query parameters, THE API SHALL return 422 with a JSON body listing each invalid parameter and the validation error.
7. [P3] WHEN an API request targets a non-existent resource, THE API SHALL return 404 with a JSON error message.

#### FR-P3-07: WebSocket Endpoints [P3]

1. [P3] `/ws/live` SHALL push real-time token data every 5 seconds (configurable) with payload: {type, data: {today_total, per_tool, burn_rate, active_sessions, cost_today, last_event_timestamp}}.
2. [P3] THE frontend animated counter SHALL interpolate between WebSocket snapshots using linear estimation based on the current burn rate, rather than waiting idle for the next push. This provides perceived real-time responsiveness with 5-second actual data intervals.
2. [P3] `/ws/alerts` SHALL push alert events when triggered with payload: {type, severity, title, message, timestamp}.
3. [P3] WHEN a client connects to `/ws/live`, THE server SHALL send the current state as an initial payload.
4. [P3] IF a WebSocket client does not send a ping within 30 seconds, THEN THE server SHALL close the connection.
5. [P3] WHEN a client disconnects, THE server SHALL clean up connection resources within 5 seconds.

#### FR-P3-08: Alert Engine [P3]

1. [P3] THE Alert_Engine SHALL evaluate threshold triggers at 50%, 75%, 90%, and 100% of configured daily token limit and monthly cost budget.
2. [P3] WHEN a threshold is crossed, THE Alert_Engine SHALL generate an alert with threshold level, current usage, and budget limit.
3. [P3] WHEN the Anomaly_Detector reports a new anomaly, THE Alert_Engine SHALL generate an anomaly alert with classification and magnitude.
4. [P3] THE Alert_Engine SHALL generate a predictive alert when burn rate projects hitting the daily limit in <2 hours.
5. [P3] THE Alert_Engine SHALL detect model switches mid-session and generate an alert.
6. [P3] THE Alert_Engine SHALL dispatch alerts via: WebSocket (always), desktop notification via plyer (configurable), and webhook POST to configured URLs (Slack, Discord, Teams format support).
7. [P3] THE Alert_Engine SHALL NOT send duplicate alerts for the same threshold crossing within a single billing period.
8. [P3] THE alert configuration SHALL be stored in config.toml under `[alerts]`, `[alerts.thresholds]`, and `[alerts.webhooks]` sections.


### Phase 4: Web Dashboard (React Frontend)

#### FR-P4-01: App Shell & Infrastructure [P4]

1. [P4] THE dashboard SHALL use Vite 6 + React 18 + TypeScript in strict mode.
2. [P4] THE dashboard SHALL use TailwindCSS v4 + shadcn/ui for components.
3. [P4] THE dashboard SHALL use Zustand stores: useTokenStore (live data), useSettingsStore, useMLStore.
4. [P4] THE dashboard SHALL use TanStack Query v5 for all API calls with stale-while-revalidate.
5. [P4] THE dashboard SHALL implement a custom `useWebSocket` hook with auto-reconnect that parses messages and updates Zustand stores.
6. [P4] THE dashboard SHALL support dark/light mode toggle with system preference detection via `prefers-color-scheme`.
7. [P4] THE dashboard SHALL be responsive for screen widths 1280px+ (developer desktop, not mobile-first).
8. [P4] THE dashboard SHALL use route structure: `/` (home), `/analytics`, `/insights`, `/settings` with sidebar navigation and tool status indicators.
9. [P4] ALL dashboard chart and data components SHALL implement three states: loading (skeleton/spinner), empty (descriptive message with guidance), and error (retry button with error description). No chart SHALL render a blank area without explanation.

#### FR-P4-02: Home Page — Command Center [P4]

1. [P4] THE Home page SHALL display a large animated real-time token counter driven by WebSocket, with subtitle "across N tools today" (Framer Motion number animation).
2. [P4] THE Home page SHALL display a 3-column grid: Today's Usage Ring Chart (Recharts PieChart — tokens used vs daily limit, colored by tool), Burn Rate Gauge (custom SVG — slow/green, normal/blue, fast/orange, critical/red), and Next Reset Countdown (hours:minutes:seconds until daily limit resets).
3. [P4] THE Home page SHALL display per-tool status cards showing: tool icon + name, today's tokens (animated counter), active session indicator (green dot), mini sparkline of last 6 hours, and cost today.
4. [P4] THE Home page SHALL display a Smart Alert Banner showing the single most important ML-driven insight (e.g., "You're on pace to exceed your daily limit by 3 PM").

#### FR-P4-03: Analytics Page — Deep Dive [P4]

1. [P4] THE Analytics page SHALL provide a tab selector (24h | 7d | 30d) that applies to all charts on the page.
2. [P4] THE Analytics page SHALL display a Token Usage Timeline (Recharts stacked AreaChart, one layer per tool, with tooltip and brush zoom/pan).
3. [P4] THE Analytics page SHALL display a Tool Comparison Bar Chart (side-by-side bars per tool: total tokens, total cost, session count) and a Model Usage Pie Chart (breakdown by model).
4. [P4] THE Analytics page SHALL display a Token Intensity Heatmap (D3.js, 24h × 7d matrix, white to deep blue/red, tooltip on hover).
5. [P4] THE Analytics page SHALL display a Session Waterfall Chart (D3.js custom, sessions as horizontal blocks: x=time, width=duration, height=tokens, color=tool).
6. [P4] WHEN a user clicks a session in the waterfall chart, THE page SHALL display a Session Detail Modal with: per-turn token breakdown table, context size growth line chart, and cache hit ratio bar.

#### FR-P4-04: Insights Page — ML Predictions [P4]

1. [P4] THE Insights page SHALL display a Burn Rate Forecast Chart (Recharts line chart with Prophet prediction + shaded 80% and 95% confidence bands, actual usage overlaid as dots).
2. [P4] THE Insights page SHALL display a Prediction Card: "You'll hit your daily limit at HH:MM (X% confidence)" with countdown, or "At current pace, you'll use X% of daily limit".
3. [P4] THE Insights page SHALL display a Monthly Cost Projection Chart (actual daily cost line + projected trajectory dashed line + budget limit line).
4. [P4] THE Insights page SHALL display an Efficiency Score Trend chart (daily average per tool, click a point to see that day's sessions).
5. [P4] THE Insights page SHALL display an Anomaly Timeline (token timeline with red markers at anomaly points, click for popup with classification and explanation).
6. [P4] THE Insights page SHALL display a What-If Simulator Card with sliders for context size, model choice dropdown, and tool usage percentage — showing real-time projected cost change.
7. [P4] THE Insights page SHALL display a Behavioral Profile Card showing current archetype label, description, productive hours highlight, and week-over-week change indicator.
8. [P4] THE Insights page SHALL handle ML cold start with three states: (a) <1 day of data: display "Collecting data... predictions available after 24 hours of usage" with a progress indicator, (b) 1-6 days: show linear extrapolation with a banner "Using simplified predictions — full ML insights unlock after 7 days", (c) ≥7 days: full Prophet predictions with no banner.

#### FR-P4-05: Settings Page [P4]

1. [P4] THE Settings page SHALL display a Tool Configuration section: auto-detected adapter paths with manual override, enable/disable toggle per adapter, test connection button.
2. [P4] THE Settings page SHALL provide Budget Limits inputs: daily token limit (per tool + global), monthly cost budget (per tool + global) with positive number validation.
3. [P4] THE Settings page SHALL provide Alert Configuration: threshold percentage checkboxes, desktop notification toggle, webhook URL inputs for Slack/Discord/Teams with test button.
4. [P4] THE Settings page SHALL provide a Model Pricing section: editable pricing table (model name, input $/1M, output $/1M) with reset-to-defaults button.
5. [P4] THE Settings page SHALL provide Data Management: export buttons (CSV, JSON) with date range picker, clear data button with confirmation dialog, database size indicator.
6. [P4] THE Settings page SHALL provide an About section: version, docs/GitHub links, daemon status indicator.
7. [P4] WHEN the user saves settings, THE page SHALL send updated config to `PUT /api/v1/settings` and display a success or error notification.


### Phase 5: CLI & Tool Integrations

#### FR-P5-01: Full CLI Command Suite [P5]

1. [P5] THE CLI SHALL use Typer + Rich and provide all Phase 1 commands plus: `tokenlens live`, `tokenlens report`, `tokenlens predict`, `tokenlens compare`, `tokenlens why`, `tokenlens optimize`, `tokenlens export`, `tokenlens serve`, and `tokenlens ml retrain`.
2. [P5] `tokenlens live` SHALL display a full-screen Textual TUI dashboard with: top bar (total tokens, cost, burn rate), left panel (per-tool live counters with sparklines), center panel (rolling 2-hour ASCII token timeline), right panel (active session info), bottom bar (last 3 alerts). Auto-refresh every 5 seconds. Keyboard shortcuts: q=quit, r=refresh, t=toggle tool filter, ?=help.
3. [P5] `tokenlens report --period today|week|month [--format table|json|markdown]` SHALL generate a formatted report with: period summary, per-tool breakdown, per-model breakdown, top 5 sessions by token usage, and efficiency score average.
4. [P5] `tokenlens predict` SHALL show burn rate forecast, limit prediction with confidence, and monthly cost projection. If ML models not trained: show linear extrapolation with a note.
5. [P5] `tokenlens compare` SHALL display a side-by-side tool comparison table with columns: Tool, Tokens Today, Cost Today, Avg Efficiency, Sessions, Avg Session Length — highlighting the more efficient tool.
6. [P5] `tokenlens why` SHALL explain the last anomaly in plain English (e.g., "At 2:14 PM, token usage spiked to 3.2x your hourly average. Cause: Extended conversation (47 turns) in Claude Code session.").
7. [P5] `tokenlens optimize` SHALL list top 3-5 actionable efficiency recommendations based on recent patterns.
8. [P5] `tokenlens export --format csv|json --period today|week|month|all [--output path]` SHALL export token events to file by calling the `GET /api/v1/export/events` endpoint (not reimplementing export logic). Default output: `./tokenlens-export-{date}.{format}`. IF the API server is not running, THE CLI SHALL start a temporary in-process server for the export.
9. [P5] `tokenlens serve [--port 7890] [--ui]` SHALL start the FastAPI server. With `--ui`: also serve the built React frontend at root `/`.
10. [P5] `tokenlens ml retrain [--all|--forecaster|--anomaly|--profiler]` SHALL manually trigger ML model retraining.

#### FR-P5-02: Shell Prompt Integration [P5]

1. [P5] `tokenlens shell-hook --shell bash|zsh|fish` SHALL output a shell script snippet that adds token count to PS1/PROMPT.
2. [P5] `tokenlens status --short` SHALL output a compact string: "42K/100K" (tokens used / limit), completing within 200 milliseconds.
3. [P5] IF the API server is unreachable, THEN `tokenlens status --short` SHALL output an empty string rather than an error.

#### FR-P5-03: Kiro Native Integration [P5]

1. [P5] THE Kiro Integration SHALL auto-generate `.kiro/steering/token-budget.md` containing: current day's usage vs limit, burn rate, estimated remaining tokens, efficiency tips, average context size, cache utilization, today's cost, monthly projection, and budget remaining.
2. [P5] THE steering file SHALL be updated via APScheduler every 30 minutes during active hours.
3. [P5] THE Kiro Integration SHALL be configurable via `[integrations.kiro]` in config.toml (enable/disable).
4. [P5] THE Kiro Integration SHALL provide a hook template `.kiro/hooks/tokenlens-session-end.json` that fires `tokenlens log-session` on session end.

#### FR-P5-04: TokenLens MCP Server Enhancements (Stretch Goal) [P5]

1. [P5]* THE MCP Server (shipped in Phase 2 as FR-P2-07) MAY be extended with additional tools: `get_burn_rate_forecast` (current prediction with confidence), `get_session_summary` (current session stats), and `suggest_model_switch` (recommend cheaper model for current task type).
2. [P5]* THE MCP Server MAY support a `log_tool_use` tool that captures tool call metadata from Kiro for richer analytics.

### Phase 6: Distribution & Polish

#### FR-P6-01: PyPI Package [P6]

1. [P6] THE package SHALL be named `tokenlens` with entry points: `tokenlens` → CLI main, `tokenlens-agent` → daemon entry point.
2. [P6] THE package SHALL support optional extras: `tokenlens[ml]` (Prophet, scikit-learn), `tokenlens[ui]` (frontend build), `tokenlens[all]` (everything).
3. [P6] THE minimum install (no ML, no UI) SHALL include only adapters + CLI + SQLite for a lightweight footprint.
4. [P6] THE package SHALL be installable via `pip install tokenlens` and `uv tool install tokenlens`.

#### FR-P6-02: Docker [P6]

1. [P6] THE distribution SHALL include a `docker-compose.yml` with a single combined service running agent + API + serving UI.
2. [P6] THE Docker setup SHALL use volume mounts: `~/.claude:/home/user/.claude:ro`, `~/.kiro:/home/user/.kiro:ro`, `~/.tokenlens:/data`.
3. [P6] THE Docker setup SHALL support one-command startup: `docker compose up -d`.

#### FR-P6-03: CI/CD Pipeline [P6]

1. [P6] THE CI pipeline (`ci.yml`) SHALL run on push/PR: ruff lint + format check, mypy strict, pytest with 90% coverage gate, Biome frontend lint, Vitest frontend tests, uv build + Vite build.
2. [P6] THE release pipeline (`release.yml`) SHALL run on tag push (v*): build Python package, publish to PyPI, build Docker image, push to GHCR, generate changelog, create GitHub Release.
3. [P6] THE repo SHALL include `dependabot.yml` for weekly dependency updates.
4. [P6] THE CI/CD SHALL use GitHub Actions as the platform.

#### FR-P6-04: Pre-commit Hooks [P6]

1. [P6] THE repo SHALL include `.pre-commit-config.yaml` with: ruff (lint + format), mypy, Biome (frontend), conventional-commits check, and detect-secrets.

#### FR-P6-05: Documentation [P6]

1. [P6] THE documentation SHALL use MkDocs Material with pages: overview/quick-start, installation, getting-started, configuration reference, per-adapter docs, adapter development guide, CLI reference, REST API reference (auto-generated from OpenAPI), ML model docs, dashboard guide, contributing guide, and auto-generated changelog.

#### FR-P6-06: Testing Strategy [P6]

1. [P6] Backend tests SHALL include: unit tests (adapters, ML modules, schema, cost calculation), integration tests (API endpoints, WebSocket), factory fixtures (factory-boy for TokenEvent, Session), async tests (pytest-asyncio). Coverage target: 90%.
2. [P6] Frontend tests SHALL include: component tests (Vitest + Testing Library), hook tests (useWebSocket, useTokenStream), integration tests (mock API, verify UI state). Coverage target: 80%.

#### FR-P6-07: README [P6]

1. [P6] THE README SHALL include: hero section with badges, screenshot/GIF of dashboard and CLI, 3-step quick start, features list, supported tools table, architecture diagram, configuration guide, CLI reference, contributing section, and MIT license.

#### FR-P6-08: Data Retention & Archival [P6]

1. [P6] THE CLI SHALL provide `tokenlens data archive --before <date>` to export and compress old events to a `.tar.gz` file, then remove them from the database.
2. [P6] THE CLI SHALL provide `tokenlens data prune --keep-days <N>` to delete events older than N days (default 90) with a confirmation prompt.
3. [P6] WHEN the SQLite database exceeds 500MB, THE platform SHALL display a warning in `tokenlens status` and the dashboard Settings page recommending archival.

## 4. Non-Functional Requirements

### NFR-01: Performance

1. [P1] Daemon event collection latency: <500ms from file change to DB write.
2. [P3] API response time: <200ms for standard queries, <1s for analytics aggregations.
3. [P3] WebSocket push interval: configurable, default 5 seconds.
4. [P2] ML model training: <30 seconds for forecaster, <10 seconds for anomaly detector.
5. [P1] SQLite DB size: warn user at 500MB, support archiving old data.
6. [P5] `tokenlens status --short` SHALL complete within 200 milliseconds.

### NFR-02: Platform Support

1. [P1] macOS (primary — Apple Silicon + Intel).
2. [P1] Linux (Ubuntu 22.04+, Fedora 38+).
3. [P1] Windows (best-effort, WSL recommended).
4. [P1] Python 3.12+.

### NFR-03: Security

1. [P1] All data stored locally — never sent to external servers.
2. [P1] No telemetry unless explicitly opted in.
3. [P1] Config file permissions: 600 (user read/write only).
4. [P1] DB file permissions: 600.
5. [P3] No credentials stored in plain text — use system keyring for webhook secrets if needed.

### NFR-04: Reliability

1. [P1] Daemon auto-recovery: if crash, restart on next `tokenlens` command.
2. [P2] Graceful degradation: if ML models fail, still show raw data.
3. [P1] Corrupted DB recovery: detect and offer rebuild from source log files.
4. [P1] File watcher recovery: if watchdog loses events, periodic full-scan fallback every 5 minutes.

### NFR-05: Accessibility [P4+]

1. [P4] THE Dashboard SHALL meet WCAG 2.1 Level AA for all interactive elements.
2. [P4] THE Dashboard SHALL support keyboard navigation for all interactive elements.
3. [P4] THE Dashboard SHALL use semantic HTML and ARIA attributes for chart components.

## 5. Data Sources & Schemas

### Claude Code JSONL Format
- **Location:** `~/.claude/projects/**/*.jsonl`
- **Format:** One JSON object per line, each representing a conversation turn
- **Key fields:** `role`, `model`, `timestamp`, `input_tokens`, `output_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`
- **Session boundary:** >15 minute gap between consecutive turns

### Kiro Session Format — Via MCP Server (Phase 2)
- **Location:** No local log files. Kiro does not store conversation data locally.
- **Verified `~/.kiro/` contents:** agents/, extensions/, powers/, settings/, skills/, steering/, argv.json — configuration only, no chat logs.
- **Integration method:** TokenLens MCP Server (FR-P2-07). Kiro calls `log_conversation_turn` tool during conversations, passing message content.
- **Token estimation:** tiktoken with `cl100k_base` encoding applied to message content received via MCP.
- **Session boundary:** >15 minute gap between MCP `log_conversation_turn` calls.
- **Note:** All Kiro token counts are ESTIMATED — marked with `estimated: true` in raw_metadata, displayed with "(est.)" suffix in UI/CLI.

### Unified TokenEvent Schema
See FR-P1-01 for the complete Pydantic v2 model definition.

## 6. Tech Stack (Locked)

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12+, FastAPI, SQLAlchemy 2.0 async, Alembic, Pydantic v2, APScheduler, watchdog, structlog, dynaconf |
| ML | scikit-learn (IsolationForest, KMeans), Prophet, pandas, numpy, tiktoken, joblib, statsmodels (ARIMA fallback) |
| Database | SQLite via aiosqlite (local), PostgreSQL 16 via asyncpg (future team mode) |
| Frontend | React 18 + TypeScript, Vite 6, TailwindCSS v4, shadcn/ui, Zustand, TanStack Query v5, Recharts, D3.js v7, Framer Motion, Lucide React |
| CLI | Typer, Rich, Textual |
| DevOps | uv, Docker + docker-compose, GitHub Actions, ruff, mypy, Biome, pytest + pytest-asyncio + factory-boy, Vitest + Testing Library, pre-commit, python-semantic-release, MkDocs Material |
| Notifications | plyer (desktop), httpx (webhooks) |

## 7. Out of Scope for v1.0

- Team mode / multi-user / PostgreSQL
- Cursor, Continue, GitHub Copilot, Cody adapters (future community adapters via SDK)
- Proxy/intercept mode for universal token capture
- Mobile app
- Cloud-hosted SaaS version
- Real-time code analysis / code quality correlation
- VS Code extension (Phase 5 MCP server is the alternative integration path)
- GPU/model inference cost tracking
- API key management for provider billing APIs

## 8. Open Questions (Resolved)

1. **Kiro log format stability:** RESOLVED — Add a `format_version` field to the adapter. If the parser encounters an unrecognized structure, log a warning and skip. Don't try auto-detection.
2. **tiktoken accuracy for Kiro:** RESOLVED — Yes, show "(est.)" suffix on all Kiro numbers in UI and CLI. Already reflected in `tokenlens status` example output.
3. **Claude Code JSONL schema changes:** RESOLVED — Same as #1: version-aware parsing with graceful degradation. Unknown fields are ignored, missing expected fields trigger a warning.
4. **WebSocket interval tuning:** RESOLVED — Keep 5 seconds. SQLite handles a simple aggregate query every 5s easily. Frontend interpolation (FR-P3-07 point 2) handles perceived responsiveness.
5. **ML cold start UX:** RESOLVED — Three states defined in FR-P4-04 point 8: <1 day (collecting data message), 1-6 days (linear fallback with banner), ≥7 days (full Prophet).

## 9. Remaining Open Questions (Resolved)

1. **Kiro MCP auto-config:** RESOLVED — Don't auto-modify `.kiro/settings/mcp.json`. Instead, `tokenlens init` detects Kiro, prints the MCP config snippet to the terminal, and says "Add this to your .kiro/settings/mcp.json to enable Kiro integration." User copy-pastes. Safer, more transparent.
2. **MCP server lifecycle:** RESOLVED — Separate process via `tokenlens mcp-serve`. Kiro's stdio transport requires a dedicated process. The daemon (`tokenlens-agent`) and MCP server (`tokenlens mcp-serve`) are two separate processes sharing the same SQLite database.
