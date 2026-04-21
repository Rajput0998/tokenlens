"""Simple time-based ML task runner — NO APScheduler.

Checks elapsed time since last training and runs ML modules when due.
Integrated into the daemon flush loop.
"""

from __future__ import annotations

import contextlib
from datetime import UTC, datetime, timedelta

import structlog

from tokenlens.core.config import settings

logger = structlog.get_logger()

# Retrain intervals
_FORECASTER_INTERVAL = timedelta(days=1)
_ANOMALY_INTERVAL = timedelta(weeks=1)
_PROFILE_INTERVAL = timedelta(weeks=1)

# Settings keys for last-run timestamps
_KEY_LAST_FORECASTER = "ml.last_forecaster_train"
_KEY_LAST_ANOMALY = "ml.last_anomaly_train"
_KEY_LAST_PROFILE = "ml.last_profile_update"


class MLTaskRunner:
    """Runs ML training tasks on a simple time-based schedule.

    No APScheduler — just checks elapsed time since last run.
    Called from the daemon flush loop after each flush cycle.
    """

    def __init__(self) -> None:
        self._last_forecaster_train: datetime | None = None
        self._last_anomaly_train: datetime | None = None
        self._last_profile_update: datetime | None = None

    @staticmethod
    def is_ml_enabled() -> bool:
        """Check if ML features are enabled via config."""
        return bool(settings.get("ml.enabled", True))

    def should_retrain_forecaster(self) -> bool:
        """Return True if forecaster retraining is due (daily)."""
        if self._last_forecaster_train is None:
            return True
        return (
            datetime.now(UTC) - self._last_forecaster_train
        ) >= _FORECASTER_INTERVAL

    def should_retrain_anomaly(self) -> bool:
        """Return True if anomaly detector retraining is due (weekly)."""
        if self._last_anomaly_train is None:
            return True
        return (
            datetime.now(UTC) - self._last_anomaly_train
        ) >= _ANOMALY_INTERVAL

    def should_update_profiles(self) -> bool:
        """Return True if behavioral profile update is due (weekly)."""
        if self._last_profile_update is None:
            return True
        return (
            datetime.now(UTC) - self._last_profile_update
        ) >= _PROFILE_INTERVAL

    async def _load_timestamps(self) -> None:
        """Load last-run timestamps from the settings DB table."""
        from sqlalchemy import select

        from tokenlens.core.database import get_session
        from tokenlens.core.models import SettingRow

        async with get_session() as db:
            for key, attr in [
                (_KEY_LAST_FORECASTER, "_last_forecaster_train"),
                (_KEY_LAST_ANOMALY, "_last_anomaly_train"),
                (_KEY_LAST_PROFILE, "_last_profile_update"),
            ]:
                result = await db.execute(
                    select(SettingRow.value).where(
                        SettingRow.key == key
                    )
                )
                row = result.scalar_one_or_none()
                if row is not None:
                    with contextlib.suppress(ValueError, TypeError):
                        setattr(
                            self, attr, datetime.fromisoformat(row)
                        )

    async def _save_timestamp(self, key: str, ts: datetime) -> None:
        """Persist a last-run timestamp to the settings DB table."""
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert

        from tokenlens.core.database import get_session
        from tokenlens.core.models import SettingRow

        async with get_session() as db:
            stmt = (
                sqlite_insert(SettingRow)
                .values(
                    key=key,
                    value=ts.isoformat(),
                    updated_at=ts,
                )
                .on_conflict_do_update(
                    index_elements=["key"],
                    set_={
                        "value": ts.isoformat(),
                        "updated_at": ts,
                    },
                )
            )
            await db.execute(stmt)

    async def run_due_tasks(self) -> None:
        """Check each ML task and run if due. Called from daemon flush loop.

        Also triggers Kiro steering file update if enabled.
        """
        # Kiro steering runs regardless of ML enabled flag
        await self._maybe_update_kiro_steering()

        if not self.is_ml_enabled():
            return

        # Load timestamps from DB on first run
        if (
            self._last_forecaster_train is None
            and self._last_anomaly_train is None
            and self._last_profile_update is None
        ):
            try:
                await self._load_timestamps()
            except Exception:
                logger.warning(
                    "Failed to load ML timestamps from DB.",
                    exc_info=True,
                )

        now = datetime.now(UTC)

        if self.should_retrain_forecaster():
            try:
                logger.info("Running forecaster retraining...")
                await self._retrain_forecaster()
                self._last_forecaster_train = now
                await self._save_timestamp(_KEY_LAST_FORECASTER, now)
                logger.info("Forecaster retraining complete.")
            except Exception:
                logger.warning(
                    "Forecaster retraining failed.", exc_info=True
                )

        if self.should_retrain_anomaly():
            try:
                logger.info("Running anomaly detector retraining...")
                await self._retrain_anomaly()
                self._last_anomaly_train = now
                await self._save_timestamp(_KEY_LAST_ANOMALY, now)
                logger.info("Anomaly detector retraining complete.")
            except Exception:
                logger.warning(
                    "Anomaly detector retraining failed.",
                    exc_info=True,
                )

        if self.should_update_profiles():
            try:
                logger.info("Running behavioral profile update...")
                await self._update_profiles()
                self._last_profile_update = now
                await self._save_timestamp(_KEY_LAST_PROFILE, now)
                logger.info("Behavioral profile update complete.")
            except Exception:
                logger.warning(
                    "Behavioral profile update failed.",
                    exc_info=True,
                )

    async def _maybe_update_kiro_steering(self) -> None:
        """Update Kiro steering file if enabled and due."""
        try:
            from tokenlens.integrations.kiro import (
                generate_steering_file,
                is_kiro_integration_enabled,
                should_update_steering,
            )

            if not is_kiro_integration_enabled():
                return

            # Load last update timestamp
            from sqlalchemy import select

            from tokenlens.core.database import get_session
            from tokenlens.core.models import SettingRow

            last_updated = None
            async with get_session() as db:
                result = await db.execute(
                    select(SettingRow.value).where(
                        SettingRow.key == "integrations.kiro.last_steering_update"
                    )
                )
                row = result.scalar_one_or_none()
                if row is not None:
                    with contextlib.suppress(ValueError, TypeError):
                        last_updated = datetime.fromisoformat(row)

            if await should_update_steering(last_updated):
                await generate_steering_file()
                now = datetime.now(UTC)
                await self._save_timestamp(
                    "integrations.kiro.last_steering_update", now
                )
                logger.info("Kiro steering file updated.")
        except Exception:
            logger.warning(
                "Kiro steering update failed.", exc_info=True
            )

    async def _retrain_forecaster(self) -> None:
        """Query hourly data and retrain the burn rate forecaster."""
        from datetime import timedelta

        import pandas as pd
        from sqlalchemy import func, select

        from tokenlens.core.database import get_session
        from tokenlens.core.models import TokenEventRow
        from tokenlens.ml.forecaster import BurnRateForecaster

        fc = BurnRateForecaster()
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
            logger.info(
                "Forecaster: no data available for training."
            )
            return

        data = pd.DataFrame([
            {
                "ds": pd.Timestamp(r[0], tz="UTC"),
                "y": float(r[1]),
                "tool": r[2],
            }
            for r in rows
        ])
        model = fc.train(data)
        if model is not None:
            fc.save(
                model, fc._models_dir / "forecaster_all.joblib"
            )
            logger.info(
                "Forecaster model saved (%s).",
                model["model_type"],
            )

    async def _retrain_anomaly(self) -> None:
        """Query hourly data and retrain the anomaly detector."""
        from datetime import timedelta

        import pandas as pd
        from sqlalchemy import func, select

        from tokenlens.core.config import get_data_dir
        from tokenlens.core.database import get_session
        from tokenlens.core.models import TokenEventRow
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
            logger.info(
                "Anomaly detector: no data available for training."
            )
            return

        data = pd.DataFrame([dict(r._mapping) for r in rows])
        data["dominant_tool_flag"] = 0
        model = ad.train(data)
        if model is not None:
            models_dir = get_data_dir() / "models"
            ad.save(
                model, models_dir / "anomaly_detector.joblib"
            )
            logger.info(
                "Anomaly detector model saved (%s confidence).",
                model["confidence"],
            )

    async def _update_profiles(self) -> None:
        """Query daily data and update behavioral profiles."""
        from datetime import timedelta

        import pandas as pd
        from sqlalchemy import func, select

        from tokenlens.core.database import get_session
        from tokenlens.core.models import TokenEventRow
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
            logger.info(
                "Profiler: need 30+ days, found %d.", len(rows)
            )
            return

        data = pd.DataFrame([dict(r._mapping) for r in rows])
        data["peak_hour"] = 12
        data["avg_session_duration"] = 30.0
        data["input_output_ratio"] = 1.5
        data["first_active_hour"] = 8
        data["last_active_hour"] = 18
        model = bp.train(data)
        if model is not None:
            logger.info(
                "Profiler model trained (%d days).",
                model["training_days"],
            )
