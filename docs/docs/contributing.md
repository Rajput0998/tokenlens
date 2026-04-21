# Contributing

## Development Setup

```bash
git clone https://github.com/tokenlens/tokenlens.git
cd tokenlens
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,ml,api,tui]"
pre-commit install
```

## Running Tests

```bash
pytest tests/ -v
```

## Code Quality

```bash
ruff check src/ tests/
ruff format src/ tests/
```

## Coverage Requirements

- **85%** overall
- **95%** for `core/`, `adapters/`, `agent/`
- **75%** for `ml/`

## Pull Request Process

1. Create a feature branch from `main`
2. Write tests for new functionality
3. Ensure all tests pass and coverage gates are met
4. Run `ruff check` and `ruff format`
5. Submit PR with clear description

## Architecture

- `src/tokenlens/core/` — Database, config, models, pricing
- `src/tokenlens/adapters/` — Tool-specific log parsers
- `src/tokenlens/agent/` — Daemon, pipeline, session management
- `src/tokenlens/ml/` — ML modules (forecaster, anomaly, profiler)
- `src/tokenlens/api/` — FastAPI backend
- `src/tokenlens/cli/` — Typer CLI commands
- `src/tokenlens/integrations/` — MCP server, Kiro integration
