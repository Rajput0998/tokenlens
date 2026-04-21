# Getting Started

## 1. Initialize TokenLens

```bash
tokenlens init
```

This creates `~/.tokenlens/` with a default configuration file and discovers available adapters.

## 2. Start the Agent

```bash
tokenlens agent start --foreground
```

The agent watches your AI tool log files and records token usage in real-time.

## 3. Check Status

```bash
tokenlens status
```

Output: `Today: 45,231 tokens | Claude Code: 45K | Cost: $0.42 | Burn: normal`

## Next Steps

- Run `tokenlens report --period week` for a detailed usage report
- Run `tokenlens predict` for burn rate forecasting
- Run `tokenlens serve` to start the web dashboard
- Run `tokenlens live` for the terminal UI (requires `[tui]` extra)
