# Installation

## Requirements

- Python 3.12+
- pip or uv package manager

## Basic Install

```bash
pip install tokenlens
```

## With ML Features

```bash
pip install "tokenlens[ml]"
```

## With API Server

```bash
pip install "tokenlens[api]"
```

## With TUI Dashboard

```bash
pip install "tokenlens[tui]"
```

## Full Install (All Features)

```bash
pip install "tokenlens[all]"
```

## Development Install

```bash
git clone https://github.com/tokenlens/tokenlens.git
cd tokenlens
pip install -e ".[dev,ml,api,tui]"
```

## Docker

```bash
# Slim image (no ML, <300MB)
docker pull ghcr.io/tokenlens/tokenlens:slim

# Full image (with ML, <800MB)
docker pull ghcr.io/tokenlens/tokenlens:latest
```

## Optional Extras

| Extra | Description | Key Dependencies |
|-------|-------------|-----------------|
| `[ml]` | ML forecasting and anomaly detection | scikit-learn, pandas, statsmodels |
| `[ml-prophet]` | Enhanced forecasting with Prophet | prophet |
| `[api]` | REST API and web dashboard backend | FastAPI, uvicorn |
| `[tui]` | Terminal UI dashboard | textual |
| `[all]` | Everything above | All dependencies |
| `[dev]` | Development tools | pytest, ruff, mypy |
