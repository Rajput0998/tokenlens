# TokenLens

[![CI](https://github.com/tokenlens/tokenlens/actions/workflows/ci.yml/badge.svg)](https://github.com/tokenlens/tokenlens/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/tokenlens)](https://pypi.org/project/tokenlens/)
[![Python](https://img.shields.io/pypi/pyversions/tokenlens)](https://pypi.org/project/tokenlens/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Universal AI token monitoring and prediction platform for coding tools.**

TokenLens tracks token consumption across AI coding assistants, provides real-time cost monitoring, burn rate forecasting, anomaly detection, and efficiency recommendations — all running locally on your machine.

## Quick Start

```bash
# 1. Install
pip install "tokenlens[all]"

# 2. Initialize
tokenlens init

# 3. Start monitoring
tokenlens agent start --foreground
```

## Features

| Feature | Description |
|---------|-------------|
| Real-time monitoring | Track tokens as they're consumed across all AI tools |
| Cost forecasting | ML-powered predictions of daily and monthly spend |
| Anomaly detection | Automatic alerts when usage deviates from baseline |
| Efficiency scoring | Session-level scoring with actionable recommendations |
| Multi-tool support | Plugin architecture for Claude Code, Kiro, and custom adapters |
| Web dashboard | React-based UI with live charts and analytics |
| Terminal UI | Textual-based TUI with real-time updates |
| Shell integration | Token counter in your shell prompt |
| MCP integration | Native Model Context Protocol server for Kiro |
| Data export | CSV/JSON export with flexible date ranges |

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                       TokenLens                           │
├───────────┬───────────┬───────────┬────────────────────┤
│  Adapters │   Agent   │    ML     │        API          │
│           │           │           │                     │
│ Claude    │  Daemon   │ Forecast  │ FastAPI + WebSocket  │
│ Kiro      │  Pipeline │ Anomaly   │ React Dashboard      │
│ Custom    │  Sessions │ Profiler  │ MCP Server           │
└───────────┴───────────┴───────────┴────────────────────┘
                        │
                ┌───────┴───────┐
                │   SQLite DB   │
                │ ~/.tokenlens/ │
                └───────────────┘
```

## CLI Commands

```bash
tokenlens status              # Today's usage summary
tokenlens status --short      # Compact: "42K/100K"
tokenlens report --period week --format markdown
tokenlens predict             # Burn rate forecast
tokenlens compare             # Tool comparison table
tokenlens optimize            # Top recommendations
tokenlens export --format csv --period month
tokenlens live                # Terminal UI dashboard
tokenlens serve --ui          # Web dashboard
tokenlens shell-hook --shell zsh  # Shell prompt integration
```

## Installation Options

```bash
pip install tokenlens              # Core only
pip install "tokenlens[ml]"        # + ML forecasting
pip install "tokenlens[api]"       # + REST API & dashboard
pip install "tokenlens[tui]"       # + Terminal UI
pip install "tokenlens[all]"       # Everything
```

## Docker

```bash
# Slim image (no ML, <300MB)
docker run -v ~/.claude:/root/.claude:ro \
           -v tokenlens-data:/data \
           ghcr.io/tokenlens/tokenlens:slim

# Full image (with ML, <800MB)
docker compose up -d
```

## Configuration

TokenLens uses `~/.tokenlens/config.toml`:

```toml
[adapters.claude_code]
enabled = true
log_path = "~/.claude/projects"

[alerts.thresholds]
daily_token_limit = 500000
monthly_cost_budget = 50.0

[ml]
enabled = true
```

## Documentation

Full documentation: [tokenlens.github.io/tokenlens](https://tokenlens.github.io/tokenlens/)

## License

MIT
