# TokenLens — Technical Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            TokenLens Platform                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────┐   ┌──────────────┐   ┌──────────────┐   ┌────────────────┐  │
│  │  CLI     │   │  API Server  │   │  Frontend    │   │  MCP Server    │  │
│  │  (Typer) │   │  (FastAPI)   │   │  (React)     │   │  (stdio)       │  │
│  └────┬─────┘   └──────┬───────┘   └──────┬───────┘   └───────┬────────┘  │
│       │                 │                   │                    │           │
│       │         ┌───────┴───────┐           │                   │           │
│       │         │   WebSocket   │◄──────────┘                   │           │
│       │         │  /ws/live     │                               │           │
│       │         │  /ws/alerts   │                               │           │
│       │         └───────┬───────┘                               │           │
│       │                 │                                       │           │
│  ┌────┴─────────────────┴───────────────────────────────────────┴────────┐  │
│  │                         Core Layer                                     │  │
│  │  ┌─────────┐  ┌──────────┐  ┌──────────┐  ┌───────────────────────┐  │  │
│  │  │ Config  │  │ Database │  │  Schema  │  │      Pricing          │  │  │
│  │  │(dynaconf│  │(aiosqlite│  │(Pydantic)│  │  (per-model rates)    │  │  │
│  │  └─────────┘  └────┬─────┘  └──────────┘  └───────────────────────┘  │  │
│  └─────────────────────┼────────────────────────────────────────────────┘  │
│                        │                                                    │
│  ┌─────────────────────┼────────────────────────────────────────────────┐  │
│  │                  Agent (Daemon)                                        │  │
│  │  ┌──────────┐  ┌───┴──────┐  ┌──────────┐  ┌──────────────────────┐  │  │
│  │  │ Watcher  │  │ Pipeline │  │ Session  │  │   ML Task Runner     │  │  │
│  │  │(watchdog)│──│ (dedup,  │──│ Manager  │  │  (scheduled tasks)   │  │  │
│  │  │          │  │  batch)  │  │ (gap det)│  │                      │  │  │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────────────────┘  │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                      Adapters                                        │    │
│  │  ┌────────────────┐  ┌────────────────┐  ┌──────────────────────┐  │    │
│  │  │  Claude Code   │  │     Kiro       │  │  Custom (entry-point)│  │    │
│  │  │  (.jsonl parse)│  │  (MCP + tiktoken│  │                      │  │    │
│  │  └────────────────┘  └────────────────┘  └──────────────────────┘  │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                      ML Pipeline                                     │    │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌─────────────┐  │    │
│  │  │ Forecaster │  │  Anomaly   │  │ Efficiency │  │  Profiler   │  │    │
│  │  │(Holt-Winters│  │(Isolation  │  │  (5-factor │  │ (KMeans     │  │    │
│  │  │ / Prophet) │  │  Forest)   │  │   scoring) │  │  clustering)│  │    │
│  │  └────────────┘  └────────────┘  └────────────┘  └─────────────┘  │    │
│  │  ┌────────────┐                                                     │    │
│  │  │   Budget   │                                                     │    │
│  │  │(cost proj) │                                                     │    │
│  │  └────────────┘                                                     │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                      Alert Engine                                    │    │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌─────────────┐  │    │
│  │  │ Threshold  │  │  Anomaly   │  │ Predictive │  │   Dispatch  │  │    │
│  │  │ (50/75/90%)│  │  Alerts    │  │  (2h warn) │  │ (desktop,   │  │    │
│  │  │            │  │            │  │            │  │  webhook,WS)│  │    │
│  │  └────────────┘  └────────────┘  └────────────┘  └─────────────┘  │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘

External:
  ~/.claude/projects/**/*.jsonl  ──►  Claude Code Adapter
  ~/.kiro/                       ──►  Kiro Adapter (via MCP)
  .kiro/steering/token-budget.md ◄──  Kiro Integration (auto-generated)
```

---

## Component Descriptions

### Core

| Component | File | Responsibility |
|-----------|------|----------------|
| Config | `core/config.py` | Dynaconf-based TOML config with env var overrides (`TOKENLENS_` prefix) |
| Database | `core/database.py` | SQLAlchemy async engine (aiosqlite), session factory, WAL mode |
| Models | `core/models.py` | ORM models: TokenEventRow, SessionRow, AdapterStateRow, SettingRow, AnomalyRow |
| Schema | `core/schema.py` | Pydantic v2 schemas: TokenEvent, Session, AdapterState |
| Pricing | `core/pricing.py` | Cache-aware per-model cost calculation (input/output/cache_creation/cache_read per 1M tokens). Helper `_resolve_cache_rates(entry)` derives cache rates from input rate (creation = 1.25×, read = 0.1×) when not explicitly configured. |

### Adapters

| Adapter | File | Mechanism |
|---------|------|-----------|
| Claude Code | `adapters/claude_code.py` | Parses JSONL conversation logs from `~/.claude/projects/`. Tracks byte offsets per file for incremental parsing. Runs in thread pool via `asyncio.to_thread()`. |
| Kiro | `integrations/mcp_server.py` | MCP server (stdio transport). Estimates tokens via tiktoken `cl100k_base`. Writes directly to DB. |
| Base | `adapters/base.py` | Abstract base class. Adapters are synchronous; daemon wraps in threads. |
| Registry | `adapters/registry.py` | Loads builtins + discovers entry-point plugins. |

### Agent (Daemon)

| Component | File | Responsibility |
|-----------|------|----------------|
| DaemonManager | `agent/daemon.py` | PID file, heartbeat, signal handling (SIGTERM/SIGINT), graceful shutdown |
| EventPipeline | `agent/pipeline.py` | Dedup (unique constraint on tool+file+offset), batch writes every 2s |
| SessionManager | `agent/session.py` | Session boundary detection via `SessionStrategy` protocol with two implementations: `GapBasedStrategy` (gap-based, 15 min default, single session per tool) for non-Claude tools, and `RollingWindowStrategy` (5-hour rolling window, multiple concurrent sessions) for `claude_code`. Assigns session_id to events, handles out-of-order events. |
| FileWatcher | `agent/watcher.py` | Watchdog observer → asyncio.Queue bridge, periodic full scan fallback (5 min) |

### ML Pipeline

| Module | File | Algorithm | Cold Start |
|--------|------|-----------|------------|
| Forecaster | `ml/forecaster.py` | <1 day: None, 1-6 days: linear, ≥7 days: Holt-Winters (or Prophet) | Returns `status: "collecting_data"` |
| Anomaly | `ml/anomaly.py` | IsolationForest on hourly feature vectors (6 features) | Needs ≥24 hours; full confidence at 14 days |
| Efficiency | `ml/efficiency.py` | Weighted 5-factor scoring (0-100) + waste pattern detection | Works immediately (rule-based) |
| Profiler | `ml/profiler.py` | KMeans (k=3) on daily usage patterns → archetypes | Needs ≥30 days |
| Budget | `ml/budget.py` | Token forecast × pricing table; what-if multiplier simulation | Works with any data |

### API (FastAPI)

| Route Group | Prefix | Endpoints |
|-------------|--------|-----------|
| Health | `/health` | GET (version + status) |
| Status | `/api/v1/status` | GET (today's summary) |
| Events | `/api/v1/events` | GET (paginated, filtered) |
| Sessions | `/api/v1/sessions` | GET list, GET /:id detail |
| Analytics | `/api/v1/analytics` | /timeline, /heatmap, /tools, /models, /summary |
| Predictions | `/api/v1/predictions` | /burnrate, /limit, /budget, /profile, POST /whatif |
| Efficiency | `/api/v1/efficiency` | /sessions, /recommendations, /trends |
| Anomalies | `/api/v1/anomalies` | GET list, GET /:id detail |
| Settings | `/api/v1/settings` | GET, PUT, GET /adapters |
| Export | `/api/v1/export` | /events, /report |
| WebSocket | `/ws/live`, `/ws/alerts` | Real-time push |

### CLI

16 commands via Typer: `version`, `init`, `status`, `agent start/stop`, `serve`, `live`, `report`, `predict`, `compare`, `why`, `optimize`, `export`, `mcp-serve`, `ml`, `shell-hook`, `data`.

### Frontend (React)

Vite + TypeScript SPA. Connects to API on port 7890. Uses WebSocket for live updates with client-side interpolation between 5s pushes.

**Pages:**
- **Command Center (Home)** — Live token counter, burn rate gauge, per-tool status cards with real hourly sparklines, smart alert banner. Premium dark/light theme with animated 3D InfoTooltips.
- **Analytics** — Token usage timeline, tool comparison, model usage, heatmap, session list.
- **Insights** — Burn rate forecast, cost projection, efficiency trends, anomaly timeline, what-if simulator, behavioral profile.
- **How It Works** — Interactive explainer with 3 tabs (Claude Code, Kiro, How Tokens Work). Covers data collection pipeline, token estimation, cost formulas, session detection. Collapsible sections with animations, formula blocks, visual timelines.
- **Settings** — Tool configuration, budget limits, alert thresholds, plan selector, model pricing table, data management.

### Integrations

| Integration | Mechanism |
|-------------|-----------|
| MCP Server | FastMCP stdio transport; 4 tools (log_conversation_turn, get_token_status, log_session_summary, get_efficiency_tips) |
| Kiro Steering | Auto-generates `.kiro/steering/token-budget.md` every 30 min with usage data and tips |

---

## Data Flow

```
Log File (.jsonl)
    │
    ▼
┌─────────────────┐     watchdog event OR periodic scan
│  File Watcher   │────────────────────────────────────┐
└────────┬────────┘                                    │
         │ asyncio.Queue (thread-safe bridge)          │
         ▼                                             │
┌─────────────────┐                                    │
│    Adapter      │  asyncio.to_thread(parse_file)     │
│  (incremental   │  reads from last byte offset       │
│   JSONL parse)  │                                    │
└────────┬────────┘                                    │
         │ list[TokenEvent]                            │
         ▼                                             │
┌─────────────────┐                                    │
│ Session Manager │  assigns session_id via gap detect │
└────────┬────────┘                                    │
         │                                             │
         ▼                                             │
┌─────────────────┐                                    │
│ Event Pipeline  │  dedup (unique constraint),        │
│                 │  batch buffer, flush every 2s      │
└────────┬────────┘                                    │
         │ INSERT (batch)                              │
         ▼                                             │
┌─────────────────┐                                    │
│    SQLite DB    │  WAL mode, aiosqlite async driver  │
│  (tokenlens.db) │                                    │
└────────┬────────┘                                    │
         │                                             │
    ┌────┴────────────────────┐                        │
    │                         │                        │
    ▼                         ▼                        │
┌──────────┐          ┌──────────────┐                 │
│ REST API │          │  ML Pipeline │                 │
│ (FastAPI)│          │  (scheduled) │                 │
└────┬─────┘          └──────────────┘                 │
     │                                                 │
     ▼                                                 │
┌──────────┐                                           │
│WebSocket │  live_update every 5s                     │
│  Push    │  alert broadcast on threshold             │
└────┬─────┘                                           │
     │                                                 │
     ▼                                                 │
┌──────────┐                                           │
│ Frontend │  React dashboard with real-time charts    │
└──────────┘                                           │
```

---

## Async Architecture

The daemon runs on a single asyncio event loop with the following concurrent tasks:

```
asyncio.gather(
    process_file_changes(),    # Consumes watchdog queue, parses files
    flush_loop(),              # Flushes pipeline every 2s, runs ML tasks
    full_scan(),               # Periodic full scan every 5 min (fallback)
    process_scan_events(),     # Processes events from full scan queue
    manager.wait_for_shutdown() # Waits for SIGTERM/SIGINT
)
```

**Thread pool usage:**
- Adapter `parse_file()` and `get_log_paths()` run in `asyncio.to_thread()` (synchronous I/O)
- Watchdog observer runs in its own thread, pushes to `asyncio.Queue` (thread-safe)

**Queue architecture:**
- `file_change_queue: asyncio.Queue[Path]` — watchdog → async loop (real-time path)
- `scan_event_queue: asyncio.Queue[list]` — full scan thread → async loop (fallback path)

---

## ML Pipeline

### Training Schedule

ML models are retrained by `MLTaskRunner.run_due_tasks()` which runs inside the daemon's flush loop:

| Model | Retrain Interval | Min Data | Persistence |
|-------|-----------------|----------|-------------|
| Forecaster | Every 6 hours | 1 day | `~/.tokenlens/models/forecaster.joblib` |
| Anomaly | Every 6 hours | 24 hours (full: 14 days) | `~/.tokenlens/models/anomaly.joblib` |
| Profiler | Daily | 30 days | `~/.tokenlens/models/profiler.joblib` |

### Cold Start States

| Data Available | Forecaster | Anomaly | Profiler |
|---------------|------------|---------|----------|
| 0 days | `collecting_data` | `insufficient_data` | `Unknown` archetype |
| 1-6 days | Linear extrapolation | Reduced confidence | `Unknown` archetype |
| 7-13 days | Holt-Winters | Reduced confidence | `Unknown` archetype |
| 14-29 days | Holt-Winters | Full confidence | `Unknown` archetype |
| 30+ days | Holt-Winters/Prophet | Full confidence | KMeans clustering |

### Model Persistence

All models are serialized via `joblib.dump()` to `~/.tokenlens/models/`. On daemon startup, models are loaded from disk if available. If missing, the system operates in cold-start mode until enough data accumulates.

---

## WebSocket Architecture

### /ws/live — Live Usage Push

- Pushes every 5 seconds via `_live_push_loop()` background task
- Payload: `{type: "live_update", data: {today_total, per_tool, per_tool_details, burn_rate, burn_rate_category, active_sessions, cost_today, last_event_timestamp}}`
  - `per_tool_details`: array of `{tool, total_tokens, cost, active, hourly: [{hour, tokens}]}` — provides real hourly sparkline data per tool
  - `burn_rate`: numeric tokens/hour value
  - `burn_rate_category`: string classification (slow/normal/fast/critical)
- Sends `{type: "ping"}` every 30s if no client message received
- Frontend interpolates between pushes for smooth chart updates

### /ws/alerts — Alert Broadcast

- Pushes alerts when triggered by the AlertEngine
- Payload: `{type: "alert", severity, title, message, timestamp, category}`
- Categories: `token_threshold`, `cost_threshold`, `anomaly`, `predictive`, `model_switch`
- Dedup: same alert not sent twice within 24h window

---

## Alert Engine

### Plan-Aware Limits

Alert thresholds are resolved from the configured plan type. The `[plan]` config section controls which limits apply:

| Plan | Daily Token Limit | Monthly Cost Budget |
|------|------------------|-------------------|
| Pro | 19,000 | $18.00 |
| Max5 | 88,000 | $35.00 |
| Max20 | 220,000 | $140.00 |
| Custom | User-defined or fallback to `[alerts.thresholds]` | User-defined or fallback |

Functions: `get_plan_type()`, `get_effective_daily_token_limit()`, `get_effective_monthly_cost_budget()`.

**P90 Auto-Detection:** `detect_plan_limit_p90(session_totals)` computes the P90 percentile of session token totals and snaps to the nearest known plan limit if within 5%. Requires ≥5 samples; falls back to `alerts.thresholds.daily_token_limit` otherwise.

### Trigger Types

| Type | Trigger | Severity |
|------|---------|----------|
| Token threshold | 50/75% of daily limit (plan-aware) | warning |
| Token threshold | 90/100% of daily limit (plan-aware) | critical |
| Cost threshold | 50/75% of monthly budget (plan-aware) | warning |
| Cost threshold | 90/100% of monthly budget (plan-aware) | critical |
| Anomaly | IsolationForest detection | warning/critical |
| Predictive | Limit projected within 2h | warning |
| Model switch | Model changed mid-session | warning |

### Dedup Strategy

- Key-based dedup: `{category}_{threshold}` or `{category}_{classification}`
- Window: 24 hours (same alert not repeated within window)
- Reset: `reset_dedup()` at billing period boundaries

### Dispatch Targets

1. **WebSocket** — broadcast to all `/ws/alerts` clients
2. **Desktop** — native OS notification via `plyer`
3. **Webhooks** — Slack/Discord URLs (configurable in `config.toml`)
