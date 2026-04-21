# TokenLens

Universal AI token monitoring and prediction platform for coding tools. TokenLens tracks token consumption from Claude Code and Kiro, provides ML-powered forecasting, anomaly detection, efficiency scoring, and real-time alerts — all from a single daemon.

---

## For Users (Direct Usage)

### Quick Start

```bash
# Install
pip install tokenlens

# Initialize config and discover adapters
tokenlens init

# Start the background collection daemon
tokenlens agent start --foreground

# Check today's usage
tokenlens status
```

### Docker

```bash
# Run with Docker Compose (mounts ~/.claude and ~/.kiro read-only)
docker compose up -d

# Check health
curl http://localhost:7890/health
```

The container exposes port 7890 and persists data in a named volume.

### CLI Commands Reference

| Command | Description | Example |
|---------|-------------|---------|
| `tokenlens version` | Show version | `tokenlens version` |
| `tokenlens init` | Initialize config, discover adapters | `tokenlens init` |
| `tokenlens status` | Today's token usage summary | `tokenlens status --short` |
| `tokenlens agent start` | Start background daemon | `tokenlens agent start --foreground` |
| `tokenlens agent stop` | Stop background daemon | `tokenlens agent stop` |
| `tokenlens serve` | Start API server | `tokenlens serve --port 7890 --ui` |
| `tokenlens live` | Launch real-time TUI dashboard | `tokenlens live` |
| `tokenlens report` | Generate usage report | `tokenlens report --period week` |
| `tokenlens predict` | Show burn rate forecast | `tokenlens predict` |
| `tokenlens compare` | Compare tools side-by-side | `tokenlens compare` |
| `tokenlens why` | Explain a cost spike | `tokenlens why` |
| `tokenlens optimize` | Get optimization suggestions | `tokenlens optimize` |
| `tokenlens export` | Export data (CSV/JSON) | `tokenlens export --format csv` |
| `tokenlens mcp-serve` | Start MCP server (stdio) | `tokenlens mcp-serve` |
| `tokenlens ml` | ML model management | `tokenlens ml train --force` |
| `tokenlens shell-hook` | Install shell integration | `tokenlens shell-hook install` |
| `tokenlens data` | Database management | `tokenlens data prune --days 90` |

### Web Dashboard

```bash
# Start API server with built-in React UI
tokenlens serve --ui

# Open in browser
open http://localhost:7890
```

The dashboard shows real-time token usage, cost trends, heatmaps, efficiency scores, and anomaly alerts via WebSocket. Includes a "How It Works" page with interactive explainers for token calculation, cost formulas, and session detection across Claude Code and Kiro.

### MCP Integration (Kiro)

Add to `.kiro/settings/mcp.json`:

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

This exposes four MCP tools to Kiro:
- `log_conversation_turn` — log a turn with token estimation
- `get_token_status` — get today's usage summary
- `log_session_summary` — log an entire conversation as a batch (tokenizes each turn separately)
- `get_efficiency_tips` — get optimization recommendations

TokenLens also auto-generates `.kiro/steering/token-budget.md` every 30 minutes with usage data and tips (when `integrations.kiro.enabled = true`).

---

## For Developers (Setup & Debugging)

### Development Setup

```bash
# Clone
git clone https://github.com/tokenlens/tokenlens.git
cd tokenlens

# Create virtual environment
uv venv
source .venv/bin/activate

# Install with all extras
uv pip install -e ".[ml,api,tui,dev]"
```

### Running Tests

```bash
.venv/bin/pytest tests/ -v
```

### Running the Frontend

```bash
cd ui
npm install
npm run dev
# Opens at http://localhost:5173, proxies API to :7890
```

### Running the API Server

```bash
tokenlens serve --port 7890
# Swagger docs at http://localhost:7890/docs
```

### Running the Daemon

```bash
tokenlens agent start --foreground
# Watches ~/.claude/projects for JSONL changes in real-time
```

### Project Structure

```
tokenlens/
├── src/tokenlens/
│   ├── adapters/       # Tool adapters (claude_code, kiro)
│   ├── agent/          # Daemon: pipeline, session manager, watcher
│   ├── alerts/         # Alert engine, desktop notifications, webhooks
│   ├── api/            # FastAPI app, routes, schemas, WebSocket
│   ├── cli/            # Typer CLI commands
│   ├── core/           # Config, models, schema, database, pricing
│   ├── integrations/   # MCP server, Kiro steering
│   └── ml/             # Forecaster, anomaly, efficiency, profiler, budget
├── ui/                 # React frontend (Vite + TypeScript)
├── tests/              # pytest test suite
├── docs/               # Documentation
├── pyproject.toml      # Package config
├── Dockerfile          # Multi-stage (slim/full variants)
└── docker-compose.yml  # Production-ready compose
```

### Creating a Custom Adapter

1. Create a class extending `tokenlens.adapters.base.ToolAdapter`
2. Implement: `name`, `version`, `discover()`, `get_log_paths()`, `parse_file()`, `get_last_processed_position()`
3. Register via entry point in `pyproject.toml`:

```toml
[project.entry-points."tokenlens.adapters"]
my_tool = "my_package.adapter:MyToolAdapter"
```

The daemon will auto-discover and load your adapter on startup.

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TOKENLENS_GENERAL__DATA_DIR` | `~/.tokenlens` | Data directory path |
| `TOKENLENS_API__HOST` | `127.0.0.1` | API server bind host |
| `TOKENLENS_API__PORT` | `7890` | API server port |
| `TOKENLENS_ADAPTERS__CLAUDE_CODE__LOG_PATH` | `~/.claude/projects` | Claude Code log directory |
| `TOKENLENS_ADAPTERS__KIRO__ENABLED` | `false` | Enable Kiro adapter |
| `TOKENLENS_ALERTS__ENABLED` | `true` | Enable alert system |
| `TOKENLENS_ALERTS__THRESHOLDS__DAILY_TOKEN_LIMIT` | `500000` | Daily token limit |
| `TOKENLENS_ALERTS__THRESHOLDS__MONTHLY_COST_BUDGET` | `50.0` | Monthly cost budget (USD) |
| `TOKENLENS_ML__ENABLED` | `true` | Enable ML features |

All config can also be set in `~/.tokenlens/config.toml` (TOML format). Environment variables override file config using dynaconf's `TOKENLENS_` prefix with `__` as section separator.
