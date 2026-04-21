# TokenLens — QA Testing Reference

## Feature Matrix

| Feature | Description | How to Test | Expected Behavior |
|---------|-------------|-------------|-------------------|
| Daemon startup | Background agent starts, discovers adapters | `tokenlens agent start --foreground` | Prints adapter discovery, starts watching log dirs |
| Incremental parsing | Only new lines parsed from JSONL | Add lines to a .jsonl file while daemon runs | New events appear in DB within 2s |
| Session detection | Groups events by 15-min gap | Create events with >15 min gap | Different session_id assigned |
| Dedup | Same file+offset not ingested twice | Restart daemon (re-parses same files) | No duplicate events in DB |
| Burn rate forecast | ML prediction of next 24h | `GET /api/v1/predictions/burnrate` | Returns forecast array or `collecting_data` |
| Anomaly detection | IsolationForest flags unusual usage | Generate burst of tokens (3x normal) | Anomaly record created in DB |
| Efficiency scoring | 5-factor session score | Complete a session, check score | Score 0-100 on session record |
| Threshold alerts | Alerts at 50/75/90/100% | Set low daily_limit, generate tokens | Alert broadcast on /ws/alerts |
| Desktop notifications | OS-native notification | Trigger threshold alert | System notification appears |
| WebSocket live | Real-time usage push | Connect to /ws/live | Receives update every 5s |
| MCP integration | Kiro tool calls | Configure MCP, call `get_token_status` | Returns today's usage |
| Kiro steering | Auto-generated .md file | Enable kiro integration, wait 30 min | `.kiro/steering/token-budget.md` created |
| Export CSV | Download events as CSV | `GET /api/v1/export/events?format=csv` | CSV file download |
| What-if simulation | Cost projection scenarios | `POST /api/v1/predictions/whatif` | Returns baseline vs projected cost |
| Behavioral profiling | User archetype classification | `GET /api/v1/predictions/profile` | Returns archetype name |

---

## CLI Commands

### tokenlens init

```bash
$ tokenlens init
✓ Created ~/.tokenlens/ directory structure
✓ Generated default config at ~/.tokenlens/config.toml

Adapter Discovery:
  ✓ claude_code adapter found at /Users/you/.claude/projects

TokenLens initialized!

Next steps:
  1. Start the agent:  tokenlens agent start --foreground
  2. Check status:     tokenlens status
  3. Edit config:      ~/.tokenlens/config.toml
```

### tokenlens status

```bash
$ tokenlens status
Today: 45,231 tokens | Claude Code: 45K | Cost: $0.45 | Burn: moderate

$ tokenlens status --short
45K/500K
```

### tokenlens agent start

```bash
$ tokenlens agent start --foreground
Available adapters: ['claude_code']
Restored position for claude_code: conversation.jsonl @ 12480
Daemon watch loop started.
```

### tokenlens serve

```bash
$ tokenlens serve --port 7890 --ui
Starting TokenLens API on 127.0.0.1:7890
Docs: http://127.0.0.1:7890/docs
Health: http://127.0.0.1:7890/health
Serving UI from /path/to/ui/dist
```

### tokenlens report

```bash
$ tokenlens report --period week
# TokenLens Report — week
Period: 2025-01-08T00:00:00Z to 2025-01-15T14:30:00Z

| Metric | Value |
|--------|-------|
| Total Tokens | 312,450 |
| Total Cost | $3.12 |
| Events | 847 |
| Sessions | 23 |
```

### tokenlens predict

```bash
$ tokenlens predict
Burn Rate Forecast (next 24h):
  Model: exponential_smoothing
  Avg hourly: 2,340 tokens/hour
  Projected daily: 56,160 tokens
  Limit hit: No (at current rate)
```

---

## API Endpoints — curl Examples

### Health Check

```bash
curl http://localhost:7890/health
# {"status":"ok","version":"1.0.0"}
```

### Status

```bash
curl http://localhost:7890/api/v1/status
# {"today_tokens":45231,"per_tool":{"claude_code":45231},"active_sessions":2,"burn_rate":"moderate","cost_today":0.4523,"daemon_healthy":true,"last_heartbeat":"2025-01-15T10:30:00Z"}
```

### Events (paginated)

```bash
curl "http://localhost:7890/api/v1/events?page=1&per_page=10&sort_by=timestamp&sort_order=desc"
# {"data":[...],"meta":{"page":1,"per_page":10,"total":847,"total_pages":85}}
```

### Events (filtered)

```bash
curl "http://localhost:7890/api/v1/events?tool=claude_code&date_from=2025-01-15T00:00:00Z"
```

### Sessions

```bash
curl http://localhost:7890/api/v1/sessions
curl http://localhost:7890/api/v1/sessions/abc-123-uuid
```

### Analytics

```bash
curl "http://localhost:7890/api/v1/analytics/timeline?period=1h"
curl http://localhost:7890/api/v1/analytics/heatmap
curl http://localhost:7890/api/v1/analytics/tools
curl http://localhost:7890/api/v1/analytics/models
curl http://localhost:7890/api/v1/analytics/summary
```

### Predictions

```bash
curl http://localhost:7890/api/v1/predictions/burnrate
curl http://localhost:7890/api/v1/predictions/limit
curl http://localhost:7890/api/v1/predictions/budget
curl http://localhost:7890/api/v1/predictions/profile

# What-if simulation
curl -X POST http://localhost:7890/api/v1/predictions/whatif \
  -H "Content-Type: application/json" \
  -d '{"context_size": 1.5, "model_switch": "claude-haiku-3.5", "usage_pct_change": -0.2}'
```

### Efficiency

```bash
curl http://localhost:7890/api/v1/efficiency/sessions
curl http://localhost:7890/api/v1/efficiency/recommendations
curl "http://localhost:7890/api/v1/efficiency/trends?date_from=2025-01-01T00:00:00Z"
```

### Anomalies

```bash
curl "http://localhost:7890/api/v1/anomalies?severity=critical"
curl http://localhost:7890/api/v1/anomalies/abc-123-uuid
```

### Settings

```bash
# Read
curl http://localhost:7890/api/v1/settings

# Update
curl -X PUT http://localhost:7890/api/v1/settings \
  -H "Content-Type: application/json" \
  -d '{"settings": {"alerts.thresholds.daily_token_limit": 750000}}'

# Adapters
curl http://localhost:7890/api/v1/settings/adapters
```

### Export

```bash
curl -o events.csv "http://localhost:7890/api/v1/export/events?format=csv"
curl -o report.md "http://localhost:7890/api/v1/export/report?period=week&format=markdown"
```

---

## WebSocket Testing

### Live Updates (wscat)

```bash
# Install wscat
npm install -g wscat

# Connect to live feed
wscat -c ws://localhost:7890/ws/live

# Expected output (every 5s):
< {"type":"live_update","data":{"today_total":45231,"per_tool":{"claude_code":45231},"burn_rate":"moderate","active_sessions":2,"cost_today":0.4523,"last_event_timestamp":"2025-01-15T10:30:00Z"}}

# Periodic ping:
< {"type":"ping"}
```

### Alerts (wscat)

```bash
wscat -c ws://localhost:7890/ws/alerts

# Trigger by exceeding threshold (set daily_token_limit low):
curl -X PUT http://localhost:7890/api/v1/settings \
  -H "Content-Type: application/json" \
  -d '{"settings": {"alerts.thresholds.daily_token_limit": 100}}'

# Expected alert:
< {"type":"alert","severity":"critical","title":"100% of daily limit reached","message":"You've used 45,231 of 100 daily tokens.","timestamp":"2025-01-15T10:30:00Z","threshold_pct":100,"category":"token_threshold"}
```

---

## Alert Scenarios

| Alert Type | How to Trigger | Expected Alert |
|------------|---------------|----------------|
| Token 50% | Set limit to 2× current usage | `"50% of daily limit reached"` |
| Token 75% | Set limit to 1.33× current usage | `"75% of daily limit reached"` |
| Token 90% | Set limit to 1.11× current usage | `"90% of daily limit reached"` (critical) |
| Token 100% | Set limit below current usage | `"100% of daily limit reached"` (critical) |
| Cost 50% | Set budget to 2× current monthly cost | `"50% of monthly budget reached"` |
| Anomaly | Generate 3× normal hourly tokens | `"Anomaly detected: Usage burst"` |
| Predictive | High burn rate + low remaining limit | `"Daily limit projected within 2 hours"` |
| Model switch | Use different model mid-session | `"Model switch detected"` |

---

## ML Features — Cold Start Behavior

### With 0 days of data

| Endpoint | Response |
|----------|----------|
| GET /predictions/burnrate | `{"status": "collecting_data", "forecast": []}` |
| GET /predictions/limit | `{"will_hit_limit": false, "current_usage": 0, "daily_limit": 500000}` |
| GET /predictions/budget | `{"projected_monthly_cost": 0, "is_over_budget": false}` |
| GET /predictions/profile | `{"archetype": "Unknown", "reason": "Insufficient data"}` |
| GET /anomalies | `{"data": [], "meta": {"total": 0}}` |
| GET /efficiency/recommendations | `["Start using TokenLens to get personalized recommendations."]` |

### With 1-6 days of data

| Feature | Behavior |
|---------|----------|
| Forecaster | Linear extrapolation (hourly_rate × 24) |
| Anomaly | Reduced confidence, may produce false positives |
| Efficiency | Works fully (rule-based, no training needed) |
| Profiler | Returns "Unknown" archetype |
| Budget | Works (simple daily average × 30) |

### With 7+ days of data

| Feature | Behavior |
|---------|----------|
| Forecaster | Holt-Winters with 24h seasonality (or Prophet if installed) |
| Anomaly | Full confidence after 14 days |
| Efficiency | Works fully |
| Profiler | KMeans clustering after 30 days |
| Budget | Accurate monthly projection |

---

## Edge Cases

### Empty Database

- `tokenlens status` → "No data yet. Run `tokenlens init` first."
- All API endpoints return empty arrays/zero values (never error)
- WebSocket /ws/live sends `{"type":"live_update","data":{"today_total":0,...}}`

### Malformed JSONL

- Adapter logs warning: `"Malformed JSON at file.jsonl line N (offset X). Skipping."`
- Skips the bad line, continues parsing subsequent lines
- Does not crash the daemon

### Concurrent Access

- SQLite WAL mode allows concurrent reads during writes
- Daemon writes, API reads — no lock contention
- Multiple API requests served concurrently via asyncio

### Large Files

- Incremental parsing: only reads from last byte offset
- Memory: processes one line at a time (no full file load)
- DB size warning at 500MB via `tokenlens status`
- `tokenlens data prune --days 90` removes old events

### Daemon Already Running

- `tokenlens agent start` checks PID file
- If process alive: prints "Daemon already running (PID: X)"
- If stale PID file (process dead): removes file, starts fresh

### Adapter Not Found

- `tokenlens init` shows: `✗ kiro adapter not found` (dimmed)
- Daemon starts with available adapters only
- No error — graceful degradation

---

## Error Scenarios

### HTTP 422 — Validation Error

```bash
# Invalid sort column
curl "http://localhost:7890/api/v1/events?sort_by=invalid_column"
# sort_by silently falls back to "timestamp" (allowlist)

# Invalid per_page
curl "http://localhost:7890/api/v1/events?per_page=999"
# 422: {"detail":[{"msg":"ensure this value is less than or equal to 200",...}]}

# Invalid settings key
curl -X PUT http://localhost:7890/api/v1/settings \
  -H "Content-Type: application/json" \
  -d '{"settings": {"invalid.key": "value"}}'
# 422: {"detail":"Rejected keys (not in allowlist): ['invalid.key']"}
```

### HTTP 404 — Not Found

```bash
curl http://localhost:7890/api/v1/sessions/nonexistent-uuid
# 404: {"detail":"Session not found"}

curl http://localhost:7890/api/v1/anomalies/nonexistent-uuid
# 404: {"detail":"Anomaly not found"}
```

### HTTP 429 — Rate Limit

The API includes rate limiting middleware. When exceeded:

```bash
# Response:
# 429: {"detail":"Rate limit exceeded. Try again in X seconds."}
# Headers: Retry-After: 60
```

### WebSocket Disconnect

- Client disconnects → removed from broadcast set
- No error logged (expected behavior)
- Reconnect: client simply opens new WebSocket connection

### Database Locked

- Rare with WAL mode
- If occurs: retry logic in pipeline flush (exponential backoff)
- Daemon logs warning but does not crash
