# TokenLens

**Universal AI token monitoring and prediction platform for coding tools.**

TokenLens tracks token consumption across AI coding assistants (Claude Code, Kiro, and more), provides real-time cost monitoring, burn rate forecasting, anomaly detection, and efficiency recommendations.

## Features

- **Real-time monitoring** — Track tokens as they're consumed across all your AI tools
- **Cost forecasting** — ML-powered predictions of daily and monthly spend
- **Anomaly detection** — Automatic alerts when usage patterns deviate from baseline
- **Efficiency scoring** — Session-level scoring with actionable recommendations
- **Multi-tool support** — Plugin architecture for Claude Code, Kiro, and custom adapters
- **Web dashboard** — React-based UI with live charts and analytics
- **CLI tools** — Rich terminal interface with TUI, reports, and shell integration
- **MCP integration** — Native Model Context Protocol server for Kiro

## Quick Start

```bash
pip install tokenlens
tokenlens init
tokenlens agent start --foreground
```

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    TokenLens                          │
├──────────┬──────────┬──────────┬───────────────────┤
│ Adapters │  Agent   │    ML    │       API          │
│          │          │          │                    │
│ Claude   │ Daemon   │ Forecast │ FastAPI + WebSocket│
│ Kiro     │ Pipeline │ Anomaly  │ React Dashboard    │
│ Custom   │ Sessions │ Profiler │ MCP Server         │
└──────────┴──────────┴──────────┴───────────────────┘
                      │
              ┌───────┴───────┐
              │   SQLite DB   │
              │ ~/.tokenlens/ │
              └───────────────┘
```
