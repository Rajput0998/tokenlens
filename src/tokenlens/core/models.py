"""SQLAlchemy ORM models for TokenLens."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    Float,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


# Define shared enum types once — reused across tables.
# SQLite stores as strings; PostgreSQL creates a single enum type.
_tool_enum = Enum("claude_code", "kiro", name="tool_enum")


class TokenEventRow(Base):
    __tablename__ = "token_events"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tool: Mapped[str] = mapped_column(_tool_enum, nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    session_id: Mapped[str] = mapped_column(String(36), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    context_type: Mapped[str] = mapped_column(
        Enum("chat", "code_generation", "code_review", "unknown", name="context_type_enum"),
        nullable=False,
        default="unknown",
    )
    turn_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Optional fields
    cache_read_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cache_write_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    file_types_in_context: Mapped[dict] = mapped_column(JSON, nullable=False, default=list)
    tool_calls: Mapped[dict] = mapped_column(JSON, nullable=False, default=list)
    raw_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    # Dedup fields
    source_file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_byte_offset: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        Index("ix_token_events_timestamp", "timestamp"),
        Index("ix_token_events_tool", "tool"),
        Index("ix_token_events_model", "model"),
        Index("ix_token_events_user_id", "user_id"),
        Index("ix_token_events_session_id", "session_id"),
        Index("ix_token_events_tool_timestamp", "tool", "timestamp"),
        UniqueConstraint(
            "tool",
            "source_file_path",
            "file_byte_offset",
            name="uq_dedup_key",
        ),
    )


class SessionRow(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tool: Mapped[str] = mapped_column(_tool_enum, nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    total_input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    turn_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    efficiency_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    __table_args__ = (
        Index("ix_sessions_tool", "tool"),
        Index("ix_sessions_start_time", "start_time"),
    )


class AdapterStateRow(Base):
    __tablename__ = "adapter_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    adapter_name: Mapped[str] = mapped_column(String(64), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    byte_offset: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        UniqueConstraint("adapter_name", "file_path", name="uq_adapter_file"),
    )


class SettingRow(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(256), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )


class AnomalyRow(Base):
    """Stores detected anomalies.

    Created in initial migration, populated by Phase 2 AnomalyDetector.
    """

    __tablename__ = "anomalies"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    severity: Mapped[str] = mapped_column(
        Enum("warning", "critical", name="severity_enum"), nullable=False
    )
    classification: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    __table_args__ = (
        Index("ix_anomalies_timestamp", "timestamp"),
        Index("ix_anomalies_severity", "severity"),
    )
