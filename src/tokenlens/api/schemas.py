"""Pydantic response/request models for the TokenLens REST API."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field, field_validator

T = TypeVar("T")


def _ensure_utc(v: datetime | None) -> datetime | None:
    """Tag naive datetimes as UTC (SQLite returns tz-naive datetimes)."""
    if v is not None and v.tzinfo is None:
        return v.replace(tzinfo=UTC)
    return v


# --- Pagination ---


class PaginationMeta(BaseModel):
    page: int
    per_page: int
    total: int
    total_pages: int


class PaginatedResponse(BaseModel, Generic[T]):  # noqa: UP046
    data: list[T]
    meta: PaginationMeta


# --- Error ---


class ErrorResponse(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None


# --- Status ---


class StatusResponse(BaseModel):
    today_tokens: int
    per_tool: dict[str, int]
    active_sessions: int
    burn_rate: str
    cost_today: float
    daemon_healthy: bool
    last_heartbeat: datetime | None
    session: dict[str, Any] | None = None


# --- Events ---


class TokenEventResponse(BaseModel):
    id: str
    tool: str
    model: str
    timestamp: datetime
    input_tokens: int
    output_tokens: int
    cost_usd: float
    session_id: str
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0

    _utc_timestamp = field_validator("timestamp", mode="before")(_ensure_utc)

    model_config = {"from_attributes": True}


# --- Sessions ---


class SessionResponse(BaseModel):
    id: str
    tool: str
    start_time: datetime
    end_time: datetime
    total_input_tokens: int
    total_output_tokens: int
    total_cost_usd: float
    turn_count: int
    efficiency_score: float | None = None

    _utc_start = field_validator("start_time", mode="before")(_ensure_utc)
    _utc_end = field_validator("end_time", mode="before")(_ensure_utc)

    model_config = {"from_attributes": True}


class SessionDetailResponse(SessionResponse):
    events: list[TokenEventResponse] = Field(default_factory=list)


# --- Analytics ---


class TimelinePoint(BaseModel):
    timestamp: datetime
    tokens: int
    cost: float
    tool: str | None = None
    model: str | None = None

    _utc_timestamp = field_validator("timestamp", mode="before")(_ensure_utc)


class HeatmapCell(BaseModel):
    day_of_week: int  # 0=Monday, 6=Sunday
    hour: int  # 0-23
    value: float


class ToolComparison(BaseModel):
    tool: str
    total_tokens: int
    total_cost: float
    session_count: int
    avg_efficiency: float | None = None


class ModelBreakdown(BaseModel):
    model: str
    total_tokens: int
    total_cost: float
    event_count: int


class SummaryResponse(BaseModel):
    today: dict[str, Any]
    week: dict[str, Any]
    month: dict[str, Any]
    all_time: dict[str, Any]


# --- Predictions ---


class BurnRateForecastResponse(BaseModel):
    model_type: str | None = None
    tool: str | None = None
    forecast: list[dict[str, Any]] = Field(default_factory=list)
    status: str | None = None


class LimitPrediction(BaseModel):
    will_hit_limit: bool
    estimated_time: datetime | None = None
    confidence_pct: float = 80.0
    current_usage: int = 0
    daily_limit: int = 0

    _utc_estimated = field_validator("estimated_time", mode="before")(_ensure_utc)


class BudgetProjection(BaseModel):
    projected_monthly_cost: float
    daily_cost: float
    daily_tokens: float
    monthly_budget: float
    is_over_budget: bool
    recommended_daily_spend: float


class WhatIfRequest(BaseModel):
    context_size: float | None = None  # multiplier, e.g. 1.5 = 50% more context
    model_switch: str | None = None  # target model name
    usage_pct_change: float | None = None  # e.g. -0.2 = 20% less usage


class WhatIfResponse(BaseModel):
    baseline_monthly_cost: float
    projected_monthly_cost: float
    cost_difference: float
    pct_change: float
    scenario: dict[str, Any]


# --- Efficiency ---


class SessionEfficiency(BaseModel):
    session_id: str
    tool: str
    score: float
    start_time: datetime
    end_time: datetime
    turn_count: int
    total_tokens: int

    _utc_start = field_validator("start_time", mode="before")(_ensure_utc)
    _utc_end = field_validator("end_time", mode="before")(_ensure_utc)


class Recommendation(BaseModel):
    message: str
    priority: str = "medium"  # low, medium, high


class EfficiencyTrend(BaseModel):
    date: datetime
    avg_score: float
    session_count: int

    _utc_date = field_validator("date", mode="before")(_ensure_utc)


# --- Anomalies ---


class AnomalyResponse(BaseModel):
    id: str
    timestamp: datetime
    severity: str
    classification: str
    description: str
    score: float

    _utc_timestamp = field_validator("timestamp", mode="before")(_ensure_utc)

    model_config = {"from_attributes": True}


class AnomalyDetailResponse(AnomalyResponse):
    metadata_json: dict[str, Any] = Field(default_factory=dict)


# --- Settings ---


class SettingsResponse(BaseModel):
    settings: dict[str, Any]


class SettingsUpdate(BaseModel):
    settings: dict[str, Any]


class AdapterStatus(BaseModel):
    name: str
    enabled: bool
    available: bool
    last_processed_at: datetime | None = None
