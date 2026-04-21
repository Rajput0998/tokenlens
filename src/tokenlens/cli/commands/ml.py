"""CLI commands for ML operations."""

from __future__ import annotations

import asyncio

import typer
from rich.console import Console

console = Console()

ml_app = typer.Typer(help="ML model management commands.")


@ml_app.command()
def retrain(
    retrain_all: bool = typer.Option(False, "--all", help="Retrain all models"),
    forecaster: bool = typer.Option(
        False, "--forecaster", help="Retrain forecaster"
    ),
    anomaly: bool = typer.Option(
        False, "--anomaly", help="Retrain anomaly detector"
    ),
    profiler: bool = typer.Option(
        False, "--profiler", help="Retrain behavioral profiler"
    ),
) -> None:
    """Retrain ML models.

    If no flags are specified, --all is assumed.
    """
    if not any([retrain_all, forecaster, anomaly, profiler]):
        retrain_all = True

    try:
        from tokenlens.ml.base import _check_ml_deps

        _check_ml_deps()
    except ImportError:
        console.print(
            "[red]ML dependencies not installed.[/red] "
            "Run: pip install 'tokenlens[ml]'"
        )
        raise typer.Exit(1) from None

    asyncio.run(_retrain_async(retrain_all, forecaster, anomaly, profiler))


async def _retrain_async(
    retrain_all: bool, forecaster: bool, anomaly: bool, profiler: bool
) -> None:
    """Async retrain logic — queries DB and calls actual ML module .train()."""
    from datetime import UTC, datetime, timedelta

    import pandas as pd
    from sqlalchemy import func, select

    from tokenlens.core.config import get_data_dir
    from tokenlens.core.database import close_engine, get_session, init_engine
    from tokenlens.core.models import TokenEventRow

    await init_engine()

    try:
        if retrain_all or forecaster:
            console.print("[blue]Retraining forecaster...[/blue]")
            try:
                from tokenlens.ml.forecaster import BurnRateForecaster

                fc = BurnRateForecaster()
                # Query hourly token data for last 30 days
                since = datetime.now(UTC) - timedelta(days=30)
                async with get_session() as db:
                    result = await db.execute(
                        select(
                            func.strftime(
                                "%Y-%m-%d %H:00:00",
                                TokenEventRow.timestamp,
                            ).label("hour"),
                            func.sum(
                                TokenEventRow.input_tokens
                                + TokenEventRow.output_tokens
                            ).label("y"),
                            TokenEventRow.tool,
                        )
                        .where(TokenEventRow.timestamp >= since)
                        .group_by("hour", TokenEventRow.tool)
                        .order_by("hour")
                    )
                    rows = result.all()

                if not rows:
                    console.print(
                        "[yellow]Forecaster: no token events found."
                        " Need 1+ days of data.[/yellow]"
                    )
                else:
                    data = pd.DataFrame([
                        {
                            "ds": pd.Timestamp(r[0], tz="UTC"),
                            "y": float(r[1]),
                            "tool": r[2],
                        }
                        for r in rows
                    ])
                    model = fc.train(data)
                    if model is None:
                        console.print(
                            "[yellow]Forecaster: insufficient data"
                            " (<1 day).[/yellow]"
                        )
                    else:
                        fc.save(
                            model,
                            fc._models_dir / "forecaster_all.joblib",
                        )
                        console.print(
                            "[green]Forecaster trained"
                            f" ({model['model_type']}).[/green]"
                        )
            except Exception as e:
                console.print(f"[red]Forecaster error: {e}[/red]")

        if retrain_all or anomaly:
            console.print("[blue]Retraining anomaly detector...[/blue]")
            try:
                from tokenlens.ml.anomaly import AnomalyDetector

                ad = AnomalyDetector()
                since = datetime.now(UTC) - timedelta(days=14)
                async with get_session() as db:
                    result = await db.execute(
                        select(
                            func.sum(
                                TokenEventRow.input_tokens
                                + TokenEventRow.output_tokens
                            ).label("total_tokens"),
                            func.sum(
                                TokenEventRow.input_tokens
                            ).label("input_tokens"),
                            func.sum(
                                TokenEventRow.output_tokens
                            ).label("output_tokens"),
                            func.count(
                                TokenEventRow.session_id.distinct()
                            ).label("session_count"),
                            func.avg(
                                TokenEventRow.turn_number
                            ).label("avg_turn_count"),
                        )
                        .where(TokenEventRow.timestamp >= since)
                        .group_by(
                            func.strftime(
                                "%Y-%m-%d %H", TokenEventRow.timestamp
                            )
                        )
                    )
                    rows = result.all()

                if not rows:
                    console.print(
                        "[yellow]Anomaly detector:"
                        " no data found.[/yellow]"
                    )
                else:
                    data = pd.DataFrame(
                        [dict(r._mapping) for r in rows]
                    )
                    data["dominant_tool_flag"] = 0
                    model = ad.train(data)
                    if model is None:
                        console.print(
                            "[yellow]Anomaly detector:"
                            " insufficient data.[/yellow]"
                        )
                    else:
                        models_dir = get_data_dir() / "models"
                        ad.save(
                            model,
                            models_dir / "anomaly_detector.joblib",
                        )
                        console.print(
                            "[green]Anomaly detector trained"
                            f" ({model['confidence']}"
                            " confidence).[/green]"
                        )
            except Exception as e:
                console.print(
                    f"[red]Anomaly detector error: {e}[/red]"
                )

        if retrain_all or profiler:
            console.print("[blue]Retraining behavioral profiler...[/blue]")
            try:
                from tokenlens.ml.profiler import BehavioralProfiler

                bp = BehavioralProfiler()
                since = datetime.now(UTC) - timedelta(days=60)
                async with get_session() as db:
                    result = await db.execute(
                        select(
                            func.strftime(
                                "%Y-%m-%d", TokenEventRow.timestamp
                            ).label("day"),
                            func.sum(
                                TokenEventRow.input_tokens
                                + TokenEventRow.output_tokens
                            ).label("total_tokens"),
                            func.count(
                                TokenEventRow.session_id.distinct()
                            ).label("session_count"),
                        )
                        .where(TokenEventRow.timestamp >= since)
                        .group_by("day")
                    )
                    rows = result.all()

                if len(rows) < 30:
                    console.print(
                        "[yellow]Profiler: need 30+ days,"
                        f" found {len(rows)} days.[/yellow]"
                    )
                else:
                    data = pd.DataFrame(
                        [dict(r._mapping) for r in rows]
                    )
                    data["peak_hour"] = 12
                    data["avg_session_duration"] = 30.0
                    data["input_output_ratio"] = 1.5
                    data["first_active_hour"] = 8
                    data["last_active_hour"] = 18
                    model = bp.train(data)
                    if model is None:
                        console.print(
                            "[yellow]Profiler:"
                            " training failed.[/yellow]"
                        )
                    else:
                        console.print(
                            "[green]Profiler trained"
                            f" ({model['training_days']}"
                            " days).[/green]"
                        )
            except Exception as e:
                console.print(f"[red]Profiler error: {e}[/red]")

        console.print("[green]Retrain complete.[/green]")
    finally:
        await close_engine()


def register(app: typer.Typer) -> None:
    """Register the ml sub-command group on the main app."""
    app.add_typer(ml_app, name="ml")
