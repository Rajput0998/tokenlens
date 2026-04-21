"""tokenlens predict — show burn rate forecast and cost projection."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import typer
from rich.console import Console

console = Console()


def register(app: typer.Typer) -> None:
    """Register the predict command on the top-level app."""
    app.command(name="predict")(predict_command)


def predict_command() -> None:
    """Show burn rate forecast, limit prediction, and monthly cost projection."""
    result = asyncio.run(_run_prediction())
    if result is None:
        console.print("[yellow]Insufficient data for prediction. Need at least 1 day.[/yellow]")
        return

    console.print("\n[bold]Token Burn Rate Forecast[/bold]\n")

    # Current burn rate
    console.print(f"  Current burn rate: {result['burn_rate_per_hour']:,.0f} tokens/hour")
    console.print(f"  Projected daily: {result['projected_daily']:,.0f} tokens")
    console.print(f"  Projected monthly: {result['projected_monthly']:,.0f} tokens")
    console.print()

    # Cost projection
    console.print("[bold]Cost Projection[/bold]\n")
    console.print(f"  Daily cost: ${result['daily_cost']:.2f}")
    console.print(f"  Monthly cost: ${result['monthly_cost']:.2f}")
    console.print()

    # Limit prediction
    if result.get("limit_prediction"):
        lp = result["limit_prediction"]
        if lp["will_hit_limit"]:
            console.print(
                f"  [red]⚠ Will hit daily limit at ~{lp['estimated_time']}[/red]"
            )
        else:
            console.print("  [green]✓ Not projected to hit daily limit today[/green]")
    console.print()

    # Model type
    console.print(f"  [dim]Model: {result.get('model_type', 'linear')}[/dim]")


async def _run_prediction() -> dict | None:
    """Run prediction using ML forecaster or linear fallback."""
    from sqlalchemy import func, select

    from tokenlens.core.config import get_data_dir
    from tokenlens.core.database import get_session, init_engine
    from tokenlens.core.models import TokenEventRow

    await init_engine()

    now = datetime.now(UTC)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    hours_elapsed = max((now - today_start).total_seconds() / 3600, 0.1)

    async with get_session() as db:
        # Get today's totals
        result = await db.execute(
            select(
                func.sum(TokenEventRow.input_tokens + TokenEventRow.output_tokens).label("total"),
                func.sum(TokenEventRow.cost_usd).label("cost"),
            )
            .where(TokenEventRow.timestamp >= today_start)
        )
        row = result.one_or_none()

        if row is None or row.total is None:
            return None

        total_today = int(row.total)
        cost_today = float(row.cost or 0)

    if total_today == 0:
        return None

    # Try ML forecaster first
    model_type = "linear"
    try:
        from tokenlens.ml.forecaster import BurnRateForecaster

        fc = BurnRateForecaster()
        model_path = get_data_dir() / "models" / "forecaster_all.joblib"
        if model_path.exists():
            model = fc.load(model_path)
            if model is not None:
                prediction = fc.predict(model, {"daily_limit": _get_daily_limit()})
                if prediction.get("forecast"):
                    model_type = prediction.get("model_type", "linear")
                    # Use ML forecast for projections
                    hourly_tokens = [f["predicted_tokens"] for f in prediction["forecast"]]
                    projected_daily = total_today + sum(hourly_tokens)
                    burn_rate_per_hour = sum(hourly_tokens) / max(len(hourly_tokens), 1)

                    daily_cost = cost_today * (projected_daily / max(total_today, 1))
                    monthly_cost = daily_cost * 30

                    return {
                        "burn_rate_per_hour": burn_rate_per_hour,
                        "projected_daily": projected_daily,
                        "projected_monthly": projected_daily * 30,
                        "daily_cost": daily_cost,
                        "monthly_cost": monthly_cost,
                        "limit_prediction": prediction.get("limit_prediction"),
                        "model_type": model_type,
                    }
    except Exception:
        pass  # Fall back to linear

    # Linear fallback
    burn_rate_per_hour = total_today / hours_elapsed
    projected_daily = burn_rate_per_hour * 24
    cost_per_token = cost_today / max(total_today, 1)
    daily_cost = projected_daily * cost_per_token
    monthly_cost = daily_cost * 30

    # Simple limit prediction
    daily_limit = _get_daily_limit()
    limit_prediction = None
    if daily_limit:
        if projected_daily > daily_limit:
            hours_to_limit = daily_limit / burn_rate_per_hour
            hit_time = today_start + timedelta(hours=hours_to_limit)
            limit_prediction = {
                "will_hit_limit": True,
                "estimated_time": hit_time.strftime("%H:%M"),
            }
        else:
            limit_prediction = {"will_hit_limit": False}

    return {
        "burn_rate_per_hour": burn_rate_per_hour,
        "projected_daily": projected_daily,
        "projected_monthly": projected_daily * 30,
        "daily_cost": daily_cost,
        "monthly_cost": monthly_cost,
        "limit_prediction": limit_prediction,
        "model_type": model_type,
    }


def _get_daily_limit() -> int | None:
    """Get daily token limit from config."""
    from tokenlens.core.config import settings

    limit = settings.get("alerts.thresholds.daily_token_limit", None)
    return int(limit) if limit else None
