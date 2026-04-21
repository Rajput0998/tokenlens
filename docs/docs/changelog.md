# Changelog

## [1.1.0] — 2026-04-19

### Added
- Cache-aware cost calculation (cache_creation + cache_read tokens)
- Claude 5-hour rolling window session model
- Plan-aware alert limits (Pro/Max5/Max20/Custom)
- P90 auto-detection for custom plan limits
- `log_session_summary` MCP tool for batch session logging
- "How It Works" page with interactive token calculation explainers
- Premium dark/light theme with Inter + JetBrains Mono fonts
- 3D animated InfoTooltips on all dashboard sections
- Multi-color burn rate gauge (green→yellow→orange→red)
- Real hourly sparkline data in tool status cards
- Plan selector in Settings page
- Model pricing table in Settings page

### Fixed
- Agent start crash (ml_runner unpacking mismatch)
- WebSocket per_tool data shape (object → array transform)
- Analytics timeline 422 error (period validation)
- Analytics data unwrapping (bare array vs envelope)
- MLStore snake_case → camelCase field mapping
- InfoTooltip overlap with charts (portal-based positioning)

## [1.0.0] — 2024-XX-XX

### Added
- Data retention: `tokenlens data archive` and `tokenlens data prune`
- 500MB DB size warning in status and dashboard
- Docker images (slim and full variants)
- GitHub Actions CI/CD pipeline
- MkDocs Material documentation
- Comprehensive README

### Changed
- Version bump to 1.0.0 (stable release)

## [0.4.0] — 2024-XX-XX

### Added
- `tokenlens live` — Textual TUI dashboard
- `tokenlens report` — Formatted usage reports (table/json/markdown)
- `tokenlens predict` — Burn rate forecast and cost projection
- `tokenlens compare` — Side-by-side tool comparison
- `tokenlens why` — Anomaly explanation in plain English
- `tokenlens optimize` — Top optimization recommendations
- `tokenlens export` — CSV/JSON data export
- `tokenlens shell-hook` — Shell prompt integration (bash/zsh/fish)
- `tokenlens status --short` — Compact status for shell prompts
- Kiro steering file auto-generation
- Kiro hook template

## [0.3.0] — 2024-XX-XX

### Added
- React web dashboard with 4 pages
- Real-time WebSocket updates
- Dark/light mode toggle

## [0.2.0] — 2024-XX-XX

### Added
- FastAPI REST API with full endpoint coverage
- WebSocket live push and alerts
- Alert engine with threshold triggers
- Desktop notifications via plyer

## [0.1.0] — 2024-XX-XX

### Added
- Core data fabric (SQLAlchemy + SQLite)
- Claude Code adapter with incremental parsing
- Session boundary detection
- Event pipeline with batch writes and dedup
- File watcher with watchdog
- Daemon manager with PID and heartbeat
- ML pipeline: forecaster, anomaly detector, efficiency engine, profiler
- MCP server for Kiro integration
- CLI: init, agent start/stop/status, status, ml retrain, mcp-serve
