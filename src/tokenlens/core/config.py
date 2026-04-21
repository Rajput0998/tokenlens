"""Configuration system using dynaconf with TOML format."""

from __future__ import annotations

import shutil
import statistics
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from dynaconf import Dynaconf

TOKENLENS_DIR = Path.home() / ".tokenlens"
CONFIG_PATH = TOKENLENS_DIR / "config.toml"


def _ensure_valid_config() -> None:
    """Check config.toml is readable UTF-8; if not, back it up and recreate it.

    A corrupted (non-UTF-8) config file causes dynaconf to raise a
    ``UnicodeDecodeError`` at import time.  We detect that condition early,
    rename the bad file to ``config.toml.bak.<timestamp>`` so it isn't lost,
    and write a fresh default so the process can continue.
    """
    if not CONFIG_PATH.exists():
        return
    try:
        CONFIG_PATH.read_text(encoding="utf-8")
    except (UnicodeDecodeError, ValueError):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = CONFIG_PATH.with_name(f"config.toml.bak.{timestamp}")
        shutil.move(str(CONFIG_PATH), str(backup))
        # Write a minimal valid config so dynaconf can load cleanly.
        # The full DEFAULT_CONFIG_TEMPLATE is written by the CLI init command.
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(
            '[general]\nuser_id = "default"\ndata_dir = "~/.tokenlens"\n',
            encoding="utf-8",
        )


_ensure_valid_config()

settings = Dynaconf(
    envvar_prefix="TOKENLENS",
    settings_files=[str(CONFIG_PATH)],
    environments=False,
    load_dotenv=False,
)


def get_data_dir() -> Path:
    """Return the data directory, defaulting to ~/.tokenlens."""
    return Path(settings.get("general.data_dir", str(TOKENLENS_DIR))).expanduser()


def get_db_path() -> Path:
    """Return the database file path."""
    return get_data_dir() / "tokenlens.db"


def get_pricing_table() -> dict[str, dict[str, float]]:
    """Return the model pricing table from config."""
    return settings.get("pricing.models", {})


def get_session_gap_minutes(tool: str) -> int:
    """Return session gap minutes for a given tool."""
    return settings.get(f"adapters.{tool}.session_gap_minutes", 15)


def ensure_dirs() -> None:
    """Create ~/.tokenlens and subdirectories if they don't exist."""
    data_dir = get_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "logs").mkdir(exist_ok=True)
    (data_dir / "models").mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# Plan-aware alert limits
# ---------------------------------------------------------------------------

PLAN_LIMITS: dict[str, dict[str, float]] = {
    "pro": {"daily_tokens": 19_000, "monthly_cost": 18.00, "message_limit": 250},
    "max5": {"daily_tokens": 88_000, "monthly_cost": 35.00, "message_limit": 1000},
    "max20": {"daily_tokens": 220_000, "monthly_cost": 140.00, "message_limit": 2000},
}


@dataclass
class PlanConfig:
    """Computed plan data resolved from config."""

    type: str  # "pro" | "max5" | "max20" | "custom"
    daily_token_limit: int  # resolved from plan type or custom override
    monthly_cost_budget: float  # resolved from plan type or custom override


def get_plan_type() -> str:
    """Return configured plan type, defaulting to 'custom'."""
    raw = settings.get("plan.type", "custom")
    if not isinstance(raw, str) or raw not in (*PLAN_LIMITS, "custom"):
        return "custom"
    return raw


def get_effective_daily_token_limit() -> int:
    """Return daily token limit for the configured plan.

    For known plans (pro/max5/max20), returns the plan-specific limit.
    For 'custom', uses ``plan.custom_token_limit`` if positive, otherwise
    falls back to ``alerts.thresholds.daily_token_limit``.
    """
    plan_type = get_plan_type()
    if plan_type in PLAN_LIMITS:
        return int(PLAN_LIMITS[plan_type]["daily_tokens"])

    # Custom plan — try explicit override first
    custom_limit = settings.get("plan.custom_token_limit", 0)
    if isinstance(custom_limit, (int, float)) and custom_limit > 0:
        return int(custom_limit)

    # Fallback to alerts.thresholds
    return int(settings.get("alerts.thresholds.daily_token_limit", 500_000))


def get_effective_monthly_cost_budget() -> float:
    """Return monthly cost budget for the configured plan.

    For known plans (pro/max5/max20), returns the plan-specific budget.
    For 'custom', uses ``plan.custom_cost_limit`` if positive, otherwise
    falls back to ``alerts.thresholds.monthly_cost_budget``.
    """
    plan_type = get_plan_type()
    if plan_type in PLAN_LIMITS:
        return float(PLAN_LIMITS[plan_type]["monthly_cost"])

    # Custom plan — try explicit override first
    custom_budget = settings.get("plan.custom_cost_limit", 0.0)
    if isinstance(custom_budget, (int, float)) and custom_budget > 0:
        return float(custom_budget)

    # Fallback to alerts.thresholds
    return float(settings.get("alerts.thresholds.monthly_cost_budget", 50.0))


def get_effective_message_limit() -> int:
    """Return message limit for the configured plan.

    For known plans (pro/max5/max20), returns the plan-specific limit.
    For 'custom', defaults to 250.
    """
    plan_type = get_plan_type()
    if plan_type in PLAN_LIMITS:
        return int(PLAN_LIMITS[plan_type].get("message_limit", 250))
    return 250


def detect_plan_limit_p90(session_totals: list[int]) -> int:
    """Compute P90 of session totals and snap to nearest known limit if within 5%.

    Returns the fallback ``daily_token_limit`` from ``[alerts.thresholds]``
    if fewer than 5 samples are provided.
    """
    fallback = int(settings.get("alerts.thresholds.daily_token_limit", 500_000))

    if len(session_totals) < 5:
        return fallback

    # P90 via stdlib: quantiles(data, n=10) returns 9 cut points; last is P90
    p90 = statistics.quantiles(session_totals, n=10)[-1]

    # Snap to nearest known plan limit if within 5%
    known_limits = [
        int(v["daily_tokens"]) for v in PLAN_LIMITS.values()
    ]  # [19000, 88000, 220000]
    for limit in known_limits:
        if abs(p90 - limit) / limit <= 0.05:
            return limit

    return int(round(p90))


DEFAULT_CONFIG_TEMPLATE = """\
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
estimation_model = "cl100k_base"

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
cors_origins = ["http://localhost:5173", "http://localhost:7890"]

[alerts]
enabled = true
desktop_notifications = true

[alerts.thresholds]
daily_token_limit = 500000
monthly_cost_budget = 50.0
warning_percentages = [50, 75, 90, 100]

[alerts.webhooks]
# slack_url = "https://hooks.slack.com/..."
# discord_url = "https://discord.com/api/webhooks/..."

# [plan]
# type = "custom"  # "pro" | "max5" | "max20" | "custom"
# custom_token_limit = 500000
# custom_cost_limit = 50.0

[ml]
enabled = true

[ml.anomaly]
threshold = -0.3
input_heavy_classification = "Large context loading"
extended_conversation_turns = 30
usage_burst_multiplier = 3.0

[integrations.kiro]
enabled = false
steering_update_interval_minutes = 30
"""
