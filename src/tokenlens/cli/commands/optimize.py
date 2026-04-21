"""tokenlens optimize — top 3-5 optimization recommendations."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import typer
from rich.console import Console

console = Console()


def register(app: typer.Typer) -> None:
    """Register the optimize command on the top-level app."""
    app.command(name="optimize")(optimize_command)


def optimize_command() -> None:
    """Show top 3-5 optimization recommendations based on usage patterns."""
    recommendations = asyncio.run(_generate_recommendations())

    console.print("\n[bold]Optimization Recommendations[/bold]\n")

    if not recommendations:
        console.print("  [green]✓ No specific optimizations needed. Usage looks efficient![/green]")
        return

    for i, rec in enumerate(recommendations, 1):
        icon = "💡" if rec["priority"] == "low" else "⚡" if rec["priority"] == "medium" else "🔥"
        console.print(f"  {icon} {i}. [bold]{rec['title']}[/bold]")
        console.print(f"     {rec['description']}")
        if rec.get("savings"):
            console.print(f"     [green]Potential savings: {rec['savings']}[/green]")
        console.print()


async def _generate_recommendations() -> list[dict]:
    """Analyze usage and generate optimization recommendations."""
    from sqlalchemy import func, select

    from tokenlens.core.database import get_session, init_engine
    from tokenlens.core.models import SessionRow, TokenEventRow

    await init_engine()

    now = datetime.now(UTC)
    week_ago = now - timedelta(days=7)
    recommendations: list[dict] = []

    try:
        async with get_session() as db:
            # Check input/output ratio
            result = await db.execute(
                select(
                    func.sum(TokenEventRow.input_tokens).label("input"),
                    func.sum(TokenEventRow.output_tokens).label("output"),
                    func.sum(TokenEventRow.cost_usd).label("cost"),
                    func.count(TokenEventRow.session_id.distinct()).label("sessions"),
                )
                .where(TokenEventRow.timestamp >= week_ago)
            )
            row = result.one_or_none()

            if row is None or row.input is None:
                return []

            total_input = int(row.input or 0)
            total_output = int(row.output or 0)
            total_cost = float(row.cost or 0)

            # Recommendation 1: High input/output ratio
            if total_output > 0 and total_input / total_output > 5:
                recommendations.append({
                    "title": "Reduce context size",
                    "description": (
                        f"Your input/output ratio is {total_input / total_output:.1f}:1. "
                        "Consider summarizing context or using smaller file excerpts."
                    ),
                    "priority": "high",
                    "savings": f"~${total_cost * 0.2:.2f}/week",
                })

            # Recommendation 2: Check for long sessions
            result = await db.execute(
                select(func.avg(SessionRow.turn_count).label("avg_turns"))
                .where(SessionRow.start_time >= week_ago)
            )
            avg_turns = result.scalar_one_or_none()
            if avg_turns and float(avg_turns) > 30:
                recommendations.append({
                    "title": "Break up long sessions",
                    "description": (
                        f"Average session length is {float(avg_turns):.0f} turns. "
                        "Starting fresh sessions reduces accumulated context cost."
                    ),
                    "priority": "medium",
                    "savings": f"~${total_cost * 0.15:.2f}/week",
                })

            # Recommendation 3: Check cache utilization
            result = await db.execute(
                select(
                    func.sum(TokenEventRow.cache_read_tokens).label("cache_read"),
                    func.sum(TokenEventRow.input_tokens).label("total_input"),
                )
                .where(TokenEventRow.timestamp >= week_ago)
            )
            cache_row = result.one_or_none()
            if cache_row and cache_row.total_input:
                cache_rate = (int(cache_row.cache_read or 0)) / max(int(cache_row.total_input), 1)
                if cache_rate < 0.1:
                    recommendations.append({
                        "title": "Improve cache utilization",
                        "description": (
                            f"Cache hit rate is only {cache_rate * 100:.0f}%. "
                            "Reusing session context and consistent prompts can improve caching."
                        ),
                        "priority": "medium",
                        "savings": f"~${total_cost * 0.1:.2f}/week",
                    })

            # Recommendation 4: Peak hour optimization
            result = await db.execute(
                select(
                    func.strftime("%H", TokenEventRow.timestamp).label("hour"),
                    func.sum(
                        TokenEventRow.input_tokens + TokenEventRow.output_tokens
                    ).label("tokens"),
                )
                .where(TokenEventRow.timestamp >= week_ago)
                .group_by("hour")
                .order_by(func.sum(TokenEventRow.input_tokens + TokenEventRow.output_tokens).desc())
                .limit(3)
            )
            peak_hours = result.all()
            if peak_hours:
                hours_str = ", ".join(f"{r.hour}:00" for r in peak_hours)
                recommendations.append({
                    "title": "Optimize peak usage hours",
                    "description": (
                        f"Peak usage at {hours_str}. "
                        "Consider batching non-urgent tasks to off-peak hours."
                    ),
                    "priority": "low",
                    "savings": None,
                })

            # Recommendation 5: Model selection
            result = await db.execute(
                select(
                    TokenEventRow.model,
                    func.sum(TokenEventRow.cost_usd).label("cost"),
                    func.count(TokenEventRow.id).label("count"),
                )
                .where(TokenEventRow.timestamp >= week_ago)
                .group_by(TokenEventRow.model)
                .order_by(func.sum(TokenEventRow.cost_usd).desc())
                .limit(1)
            )
            top_model = result.one_or_none()
            if top_model and float(top_model.cost or 0) > total_cost * 0.7:
                recommendations.append({
                    "title": "Consider model alternatives",
                    "description": (
                        f"{top_model.model} accounts for "
                        f"{float(top_model.cost or 0) / max(total_cost, 0.01) * 100:.0f}% "
                        "of cost. For simpler tasks, a lighter model could reduce expenses."
                    ),
                    "priority": "low",
                    "savings": None,
                })

    except Exception:
        pass

    return recommendations[:5]
