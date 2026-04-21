# CLI Reference

## Core Commands

| Command | Description |
|---------|-------------|
| `tokenlens init` | Initialize TokenLens configuration |
| `tokenlens status` | Show today's token usage summary |
| `tokenlens status --short` | Compact output for shell prompts |
| `tokenlens version` | Show version |

## Agent Commands

| Command | Description |
|---------|-------------|
| `tokenlens agent start [--foreground]` | Start the collection daemon |
| `tokenlens agent stop` | Stop the daemon |
| `tokenlens agent status` | Show daemon status |

## Analytics Commands

| Command | Description |
|---------|-------------|
| `tokenlens report --period today\|week\|month [--format table\|json\|markdown]` | Generate usage report |
| `tokenlens predict` | Show burn rate forecast and cost projection |
| `tokenlens compare [--period week]` | Side-by-side tool comparison |
| `tokenlens why` | Explain the last anomaly |
| `tokenlens optimize` | Top optimization recommendations |

## Data Commands

| Command | Description |
|---------|-------------|
| `tokenlens export --format csv\|json --period today\|week\|month\|all [--output path]` | Export token data |
| `tokenlens data archive --before <date>` | Archive old data |
| `tokenlens data prune --keep-days <N>` | Delete old events |

## Integration Commands

| Command | Description |
|---------|-------------|
| `tokenlens serve [--port 7890] [--ui]` | Start API server |
| `tokenlens mcp-serve` | Start MCP server (stdio) |
| `tokenlens live` | Launch TUI dashboard |
| `tokenlens shell-hook --shell bash\|zsh\|fish` | Output shell prompt snippet |

## ML Commands

| Command | Description |
|---------|-------------|
| `tokenlens ml retrain [--all\|--forecaster\|--anomaly\|--profiler]` | Retrain ML models |
