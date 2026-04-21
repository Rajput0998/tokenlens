# Claude Code Adapter

The Claude Code adapter reads JSONL log files from `~/.claude/projects/` and extracts token usage data.

## Configuration

```toml
[adapters.claude_code]
enabled = true
log_path = "~/.claude/projects"
session_gap_minutes = 15
```

## How It Works

1. Watches for `.jsonl` files in the configured log path
2. Parses assistant responses with token counts
3. Calculates cost using the model pricing table
4. Detects session boundaries (>15 min gap = new session)

## Supported Fields

- `input_tokens` / `output_tokens`
- `cache_read_tokens` / `cache_write_tokens`
- Model name and timestamp
- Turn number tracking per session
