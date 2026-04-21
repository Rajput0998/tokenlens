"""Pydantic v2 schemas for TokenLens unified token event data."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class ToolEnum(StrEnum):
    """Supported AI coding tools."""

    CLAUDE_CODE = "claude_code"
    KIRO = "kiro"


class ContextType(StrEnum):
    """Classification of the conversation context."""

    CHAT = "chat"
    CODE_GENERATION = "code_generation"
    CODE_REVIEW = "code_review"
    UNKNOWN = "unknown"


class TokenEvent(BaseModel):
    """Unified token event schema. Validates all token data regardless of source tool."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    tool: ToolEnum
    model: str
    user_id: str
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    cost_usd: float = Field(ge=0.0, default=0.0)
    context_type: ContextType = ContextType.UNKNOWN
    turn_number: int = Field(ge=0, default=0)

    # Optional fields with defaults
    cache_read_tokens: int = Field(ge=0, default=0)
    cache_write_tokens: int = Field(ge=0, default=0)
    file_types_in_context: list[str] = Field(default_factory=list)
    tool_calls: list[str] = Field(default_factory=list)
    raw_metadata: dict[str, Any] = Field(default_factory=dict)

    # Dedup fields (not part of the logical schema, used by pipeline)
    source_file_path: str | None = None
    file_byte_offset: int | None = None

    @field_validator("timestamp", mode="before")
    @classmethod
    def ensure_timezone(cls, v: Any) -> datetime:
        if isinstance(v, datetime) and v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v

    model_config = {"from_attributes": True}


class Session(BaseModel):
    """Aggregated session model. Computed on session close."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    tool: ToolEnum
    start_time: datetime
    end_time: datetime
    total_input_tokens: int = Field(ge=0, default=0)
    total_output_tokens: int = Field(ge=0, default=0)
    total_cost_usd: float = Field(ge=0.0, default=0.0)
    turn_count: int = Field(ge=0, default=0)
    efficiency_score: float | None = None  # Populated in Phase 2

    model_config = {"from_attributes": True}


class AdapterState(BaseModel):
    """Tracks per-file read position for incremental parsing."""

    adapter_name: str
    file_path: str
    byte_offset: int = 0
    last_processed_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC)
    )

    model_config = {"from_attributes": True}
