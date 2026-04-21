"""Settings endpoints: GET reads config + DB overrides, PUT writes to DB only."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tokenlens.api.deps import get_db_session
from tokenlens.api.schemas import AdapterStatus, SettingsResponse, SettingsUpdate
from tokenlens.core.config import settings as app_settings
from tokenlens.core.models import SettingRow

router = APIRouter(prefix="/settings", tags=["settings"])

# Allowlist of writable settings keys with expected types
WRITABLE_SETTINGS: dict[str, type] = {
    "alerts.thresholds.daily_token_limit": int,
    "alerts.thresholds.monthly_cost_budget": float,
    "alerts.enabled": bool,
    "alerts.desktop_notifications": bool,
    "plan.type": str,
    "plan.custom_token_limit": int,
    "plan.custom_cost_limit": float,
    "ml.enabled": bool,
    "integrations.kiro.enabled": bool,
    "integrations.kiro.steering_update_interval_minutes": int,
}


@router.get("", response_model=SettingsResponse)
async def get_settings(
    session: AsyncSession = Depends(get_db_session),
):
    """Get merged settings: config.toml base + DB overrides."""
    # Base settings from config
    base = {
        "general": {
            "user_id": app_settings.get("general.user_id", "default"),
            "data_dir": app_settings.get("general.data_dir", "~/.tokenlens"),
        },
        "daemon": {
            "batch_write_interval_seconds": app_settings.get(
                "daemon.batch_write_interval_seconds", 2
            ),
            "full_scan_interval_minutes": app_settings.get(
                "daemon.full_scan_interval_minutes", 5
            ),
        },
        "alerts": {
            "enabled": app_settings.get("alerts.enabled", True),
            "desktop_notifications": app_settings.get("alerts.desktop_notifications", True),
            "thresholds": {
                "daily_token_limit": app_settings.get(
                    "alerts.thresholds.daily_token_limit", 500000
                ),
                "monthly_cost_budget": app_settings.get(
                    "alerts.thresholds.monthly_cost_budget", 50.0
                ),
            },
        },
        "ml": {
            "enabled": app_settings.get("ml.enabled", True),
        },
        "api": {
            "host": app_settings.get("api.host", "127.0.0.1"),
            "port": app_settings.get("api.port", 7890),
        },
    }

    # Apply DB overrides
    stmt = select(SettingRow)
    result = await session.execute(stmt)
    db_settings = result.scalars().all()

    overrides: dict[str, str] = {}
    for row in db_settings:
        overrides[row.key] = row.value

    # Merge overrides into base (flat key format: "alerts.thresholds.daily_token_limit")
    merged = base.copy()
    merged["_overrides"] = overrides

    return SettingsResponse(settings=merged)


@router.put("", response_model=SettingsResponse)
async def update_settings(
    update: SettingsUpdate,
    session: AsyncSession = Depends(get_db_session),
):
    """Write settings to DB table ONLY. Does NOT modify config.toml.

    Only keys in WRITABLE_SETTINGS allowlist are accepted.
    """
    now = datetime.now(UTC)
    rejected: list[str] = []

    for key, value in update.settings.items():
        # Validate key is in allowlist
        if key not in WRITABLE_SETTINGS:
            rejected.append(key)
            continue

        # Validate type
        expected_type = WRITABLE_SETTINGS[key]
        try:
            if expected_type is bool:
                coerced = str(value).lower() in ("true", "1", "yes")
                str_value = str(coerced)
            elif expected_type is int:
                str_value = str(int(value))
            elif expected_type is float:
                str_value = str(float(value))
            else:
                str_value = str(value)
        except (ValueError, TypeError):
            rejected.append(key)
            continue

        # Upsert into settings table
        stmt = select(SettingRow).where(SettingRow.key == key)
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            existing.value = str_value
            existing.updated_at = now
        else:
            new_setting = SettingRow(
                key=key, value=str_value, updated_at=now
            )
            session.add(new_setting)

    if rejected:
        from fastapi import HTTPException

        await session.commit()
        raise HTTPException(
            status_code=422,
            detail=f"Rejected keys (not in allowlist): {rejected}",
        )

    await session.commit()

    # Return updated settings
    return await get_settings(session=session)


@router.get("/adapters", response_model=list[AdapterStatus])
async def get_adapter_status():
    """Get status of all registered adapters."""
    from tokenlens.adapters.registry import AdapterRegistry

    registry = AdapterRegistry()
    registry.load_builtins()

    adapters = registry.get_all()
    statuses = []
    for adapter in adapters:
        try:
            available = adapter.discover()
        except Exception:
            available = False

        statuses.append(
            AdapterStatus(
                name=adapter.name,
                enabled=app_settings.get(f"adapters.{adapter.name}.enabled", False),
                available=available,
            )
        )

    return statuses
