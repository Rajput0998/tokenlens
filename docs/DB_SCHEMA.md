# TokenLens — Database Schema

## Overview

TokenLens uses SQLite with WAL mode via the `aiosqlite` async driver. The database file lives at `~/.tokenlens/tokenlens.db`. Schema is managed by Alembic migrations.

---

## ER Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         token_events                              │
├─────────────────────────────────────────────────────────────────┤
│ PK  id               VARCHAR(36)   UUID                          │
│     tool             ENUM          (claude_code, kiro)            │
│     model            VARCHAR(128)                                 │
│     user_id          VARCHAR(128)                                 │
│ FK  session_id       VARCHAR(36)   → sessions.id                 │
│     timestamp        DATETIME(tz)  NOT NULL                      │
│     input_tokens     INTEGER       NOT NULL                      │
│     output_tokens    INTEGER       NOT NULL                      │
│     cost_usd         FLOAT         NOT NULL DEFAULT 0.0          │
│     context_type     ENUM          (chat, code_generation,       │
│                                     code_review, unknown)        │
│     turn_number      INTEGER       NOT NULL DEFAULT 0            │
│     cache_read_tokens  INTEGER     NOT NULL DEFAULT 0            │
│     cache_write_tokens INTEGER     NOT NULL DEFAULT 0            │
│     file_types_in_context JSON     NOT NULL DEFAULT []           │
│     tool_calls       JSON          NOT NULL DEFAULT []           │
│     raw_metadata     JSON          NOT NULL DEFAULT {}           │
│     source_file_path TEXT          NULLABLE                      │
│     file_byte_offset INTEGER       NULLABLE                      │
├─────────────────────────────────────────────────────────────────┤
│ UQ  uq_dedup_key (tool, source_file_path, file_byte_offset)     │
│ IX  ix_token_events_timestamp (timestamp)                        │
│ IX  ix_token_events_tool (tool)                                  │
│ IX  ix_token_events_model (model)                                │
│ IX  ix_token_events_user_id (user_id)                            │
│ IX  ix_token_events_session_id (session_id)                      │
│ IX  ix_token_events_tool_timestamp (tool, timestamp)  [composite]│
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               │ session_id
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                           sessions                                │
├─────────────────────────────────────────────────────────────────┤
│ PK  id               VARCHAR(36)   UUID                          │
│     tool             ENUM          (claude_code, kiro)            │
│     start_time       DATETIME(tz)  NOT NULL                      │
│     end_time         DATETIME(tz)  NOT NULL                      │
│     total_input_tokens  INTEGER    NOT NULL DEFAULT 0            │
│     total_output_tokens INTEGER    NOT NULL DEFAULT 0            │
│     total_cost_usd   FLOAT         NOT NULL DEFAULT 0.0          │
│     turn_count       INTEGER       NOT NULL DEFAULT 0            │
│     efficiency_score FLOAT         NULLABLE                      │
├─────────────────────────────────────────────────────────────────┤
│ IX  ix_sessions_tool (tool)                                      │
│ IX  ix_sessions_start_time (start_time)                          │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                        adapter_state                              │
├─────────────────────────────────────────────────────────────────┤
│ PK  id               INTEGER       AUTOINCREMENT                 │
│     adapter_name     VARCHAR(64)   NOT NULL                      │
│     file_path        TEXT          NOT NULL                      │
│     byte_offset      INTEGER       NOT NULL DEFAULT 0            │
│     last_processed_at DATETIME(tz) NOT NULL                      │
├─────────────────────────────────────────────────────────────────┤
│ UQ  uq_adapter_file (adapter_name, file_path)                    │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                          settings                                 │
├─────────────────────────────────────────────────────────────────┤
│ PK  key              VARCHAR(256)                                 │
│     value            TEXT          NOT NULL                      │
│     updated_at       DATETIME(tz)  NOT NULL                      │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                          anomalies                                │
├─────────────────────────────────────────────────────────────────┤
│ PK  id               VARCHAR(36)   UUID                          │
│     timestamp        DATETIME(tz)  NOT NULL                      │
│     severity         ENUM          (warning, critical)           │
│     classification   VARCHAR(128)  NOT NULL                      │
│     description      TEXT          NOT NULL                      │
│     score            FLOAT         NOT NULL                      │
│     metadata_json    JSON          NOT NULL DEFAULT {}           │
├─────────────────────────────────────────────────────────────────┤
│ IX  ix_anomalies_timestamp (timestamp)                           │
│ IX  ix_anomalies_severity (severity)                             │
└─────────────────────────────────────────────────────────────────┘
```

---

## Table Details

### token_events

The primary data table. Each row represents one LLM conversation turn with token counts and cost.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | VARCHAR(36) | NO | uuid4() | Primary key |
| tool | ENUM | NO | — | Source tool: `claude_code` or `kiro` |
| model | VARCHAR(128) | NO | — | Model name (e.g., `claude-sonnet-4`) |
| user_id | VARCHAR(128) | NO | — | User identifier |
| session_id | VARCHAR(36) | NO | — | FK to sessions table |
| timestamp | DATETIME(tz) | NO | — | When the event occurred |
| input_tokens | INTEGER | NO | — | Input/prompt token count |
| output_tokens | INTEGER | NO | — | Output/completion token count |
| cost_usd | FLOAT | NO | 0.0 | Calculated cost in USD |
| context_type | ENUM | NO | `unknown` | chat, code_generation, code_review, unknown |
| turn_number | INTEGER | NO | 0 | Turn position within session |
| cache_read_tokens | INTEGER | NO | 0 | Tokens read from cache |
| cache_write_tokens | INTEGER | NO | 0 | Tokens written to cache |
| file_types_in_context | JSON | NO | [] | File extensions in context |
| tool_calls | JSON | NO | [] | Tool calls made in this turn |
| raw_metadata | JSON | NO | {} | Raw adapter-specific metadata |
| source_file_path | TEXT | YES | NULL | Source log file path (for dedup) |
| file_byte_offset | INTEGER | YES | NULL | Byte offset in source file (for dedup) |

### sessions

Aggregated session data. A session is a group of events from the same tool with no gap exceeding `session_gap_minutes` (default 15).

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | VARCHAR(36) | NO | uuid4() | Primary key |
| tool | ENUM | NO | — | Source tool |
| start_time | DATETIME(tz) | NO | — | First event timestamp |
| end_time | DATETIME(tz) | NO | — | Last event timestamp |
| total_input_tokens | INTEGER | NO | 0 | Sum of input tokens |
| total_output_tokens | INTEGER | NO | 0 | Sum of output tokens |
| total_cost_usd | FLOAT | NO | 0.0 | Sum of costs |
| turn_count | INTEGER | NO | 0 | Number of events |
| efficiency_score | FLOAT | YES | NULL | ML-computed score (0-100) |

### adapter_state

Tracks per-file read position for incremental parsing. Allows the daemon to resume from where it left off after restart.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | INTEGER | NO | AUTO | Primary key |
| adapter_name | VARCHAR(64) | NO | — | Adapter identifier |
| file_path | TEXT | NO | — | Absolute path to log file |
| byte_offset | INTEGER | NO | 0 | Last processed byte position |
| last_processed_at | DATETIME(tz) | NO | now() | When last processed |

### settings

Key-value store for runtime settings that override config.toml. Written by the PUT /api/v1/settings endpoint.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| key | VARCHAR(256) | NO | — | Dot-notation key (PK) |
| value | TEXT | NO | — | String-encoded value |
| updated_at | DATETIME(tz) | NO | now() | Last modification time |

### anomalies

Stores detected anomalies from the IsolationForest ML model.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | VARCHAR(36) | NO | uuid4() | Primary key |
| timestamp | DATETIME(tz) | NO | — | When anomaly was detected |
| severity | ENUM | NO | — | `warning` or `critical` |
| classification | VARCHAR(128) | NO | — | Type: Large context loading, Extended conversation, Usage burst, Unclassified anomaly |
| description | TEXT | NO | — | Human-readable description |
| score | FLOAT | NO | — | IsolationForest decision function score |
| metadata_json | JSON | NO | {} | Additional context (feature values, thresholds) |

---

## Indexes

| Index Name | Table | Columns | Type |
|------------|-------|---------|------|
| ix_token_events_timestamp | token_events | timestamp | B-tree |
| ix_token_events_tool | token_events | tool | B-tree |
| ix_token_events_model | token_events | model | B-tree |
| ix_token_events_user_id | token_events | user_id | B-tree |
| ix_token_events_session_id | token_events | session_id | B-tree |
| ix_token_events_tool_timestamp | token_events | tool, timestamp | Composite B-tree |
| ix_sessions_tool | sessions | tool | B-tree |
| ix_sessions_start_time | sessions | start_time | B-tree |
| ix_anomalies_timestamp | anomalies | timestamp | B-tree |
| ix_anomalies_severity | anomalies | severity | B-tree |

The composite index `ix_token_events_tool_timestamp` is the most important for query performance — it covers the common pattern of filtering by tool within a date range.

---

## Unique Constraints

| Constraint Name | Table | Columns | Purpose |
|----------------|-------|---------|---------|
| uq_dedup_key | token_events | tool, source_file_path, file_byte_offset | Prevents duplicate event ingestion from the same file position |
| uq_adapter_file | adapter_state | adapter_name, file_path | One state record per adapter per file |

---

## Relationships

```
token_events.session_id  ──►  sessions.id
```

This is a logical relationship (not enforced by FK constraint in SQLite for performance). The SessionManager assigns `session_id` during event ingestion based on gap detection.

---

## SQLite-Specific Notes

- **WAL mode**: Enabled for concurrent read/write. The daemon writes while the API reads.
- **aiosqlite**: Async driver wrapping sqlite3 in a thread. All DB operations are non-blocking from the event loop's perspective.
- **No FK enforcement**: Foreign keys are not enforced at the DB level for write performance. Referential integrity is maintained by application logic.
- **JSON columns**: Stored as TEXT in SQLite, serialized/deserialized by SQLAlchemy's JSON type.
- **ENUM columns**: Stored as VARCHAR strings in SQLite (no native enum support).
- **Timezone-aware datetimes**: Stored as ISO strings with timezone info. Always use UTC.
- **File size**: Monitor with `tokenlens data` commands. Warn at 500MB. Use `tokenlens data prune` or `tokenlens data archive` for maintenance.
- **Upsert pattern**: `adapter_state` uses SQLite's `INSERT ... ON CONFLICT DO UPDATE` for atomic position updates.
