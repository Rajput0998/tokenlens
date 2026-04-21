# API Reference

TokenLens exposes a REST API on port 7890 (configurable).

Start the server: `tokenlens serve [--port 7890]`

API docs available at: `http://localhost:7890/docs`

## Endpoints

### Status
- `GET /health` — Health check
- `GET /api/v1/status` — Today's usage summary

### Events
- `GET /api/v1/events` — Paginated token events (filterable by tool, model, date range)

### Sessions
- `GET /api/v1/sessions` — List sessions
- `GET /api/v1/sessions/{id}` — Session detail

### Analytics
- `GET /api/v1/analytics/timeline` — Token usage over time
- `GET /api/v1/analytics/heatmap` — Usage heatmap (24×7)
- `GET /api/v1/analytics/tools` — Per-tool breakdown
- `GET /api/v1/analytics/models` — Per-model breakdown
- `GET /api/v1/analytics/summary` — Period summary

### Predictions
- `GET /api/v1/predictions/burnrate` — Burn rate forecast
- `GET /api/v1/predictions/limit` — Limit hit prediction
- `GET /api/v1/predictions/budget` — Monthly cost projection
- `POST /api/v1/predictions/whatif` — What-if scenario simulation

### WebSocket
- `WS /ws/live` — Real-time usage updates (5s interval)
- `WS /ws/alerts` — Alert notifications
