# Configuration

TokenLens uses a TOML configuration file at `~/.tokenlens/config.toml`.

## Default Configuration

```toml
[general]
user_id = "default"
data_dir = "~/.tokenlens"

[daemon]
batch_write_interval_seconds = 2
full_scan_interval_minutes = 5
session_gap_minutes = 15

[adapters.claude_code]
enabled = true
log_path = "~/.claude/projects"
session_gap_minutes = 15

[adapters.kiro]
enabled = false
log_path = "~/.kiro"
session_gap_minutes = 15

[pricing.models]
# Per-model pricing in USD per million tokens.
# Optional cache_creation and cache_read fields override derived rates.
# Default derived rates: cache_creation = input × 1.25, cache_read = input × 0.1
"claude-sonnet-4"  = { input = 3.0,  output = 15.0, cache_creation = 3.75, cache_read = 0.30 }
"claude-opus-4"    = { input = 15.0, output = 75.0, cache_creation = 18.75, cache_read = 1.50 }
"claude-haiku-3.5" = { input = 0.80, output = 4.0, cache_creation = 1.0, cache_read = 0.08 }
"kiro-auto"        = { input = 3.0,  output = 15.0 }

[api]
host = "127.0.0.1"
port = 7890

[alerts]
enabled = true
desktop_notifications = true

[alerts.thresholds]
daily_token_limit = 500000
monthly_cost_budget = 50.0
warning_percentages = [50, 75, 90, 100]

# [plan]
# type = "custom"  # "pro" | "max5" | "max20" | "custom"
# custom_token_limit = 500000
# custom_cost_limit = 50.0

[ml]
enabled = true

[integrations.kiro]
enabled = false
steering_update_interval_minutes = 30
```

## Environment Variable Overrides

All settings can be overridden via environment variables with the `TOKENLENS_` prefix:

```bash
export TOKENLENS_API__PORT=8080
export TOKENLENS_ML__ENABLED=false
```
