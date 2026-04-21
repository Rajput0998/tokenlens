"""Unit tests for SQLAlchemy ORM models."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from tokenlens.core.models import (
    AdapterStateRow,
    AnomalyRow,
    Base,
    SessionRow,
    SettingRow,
    TokenEventRow,
    _tool_enum,
)


class TestTokenEventRow:
    def test_instantiation_with_valid_data(self) -> None:
        row = TokenEventRow(
            id=str(uuid.uuid4()),
            tool="claude_code",
            model="claude-sonnet-4",
            user_id="user1",
            session_id=str(uuid.uuid4()),
            timestamp=datetime.now(UTC),
            input_tokens=100,
            output_tokens=50,
            cost_usd=0.01,
        )
        assert row.tool == "claude_code"
        assert row.input_tokens == 100

    def test_table_name(self) -> None:
        assert TokenEventRow.__tablename__ == "token_events"

    def test_columns_exist(self) -> None:
        col_names = {c.name for c in TokenEventRow.__table__.columns}
        expected = {
            "id", "tool", "model", "user_id", "session_id", "timestamp",
            "input_tokens", "output_tokens", "cost_usd", "context_type",
            "turn_number", "cache_read_tokens", "cache_write_tokens",
            "file_types_in_context", "tool_calls", "raw_metadata",
            "source_file_path", "file_byte_offset",
        }
        assert expected.issubset(col_names)


class TestSessionRow:
    def test_instantiation_with_valid_data(self) -> None:
        now = datetime.now(UTC)
        row = SessionRow(
            id=str(uuid.uuid4()),
            tool="kiro",
            start_time=now,
            end_time=now,
            total_input_tokens=500,
            total_output_tokens=200,
            total_cost_usd=0.05,
            turn_count=10,
        )
        assert row.tool == "kiro"
        assert row.turn_count == 10

    def test_table_name(self) -> None:
        assert SessionRow.__tablename__ == "sessions"

    def test_efficiency_score_nullable(self) -> None:
        now = datetime.now(UTC)
        row = SessionRow(
            id=str(uuid.uuid4()),
            tool="claude_code",
            start_time=now,
            end_time=now,
        )
        assert row.efficiency_score is None


class TestAdapterStateRow:
    def test_instantiation_with_valid_data(self) -> None:
        row = AdapterStateRow(
            adapter_name="claude_code",
            file_path="/home/user/.claude/projects/test.jsonl",
            byte_offset=1024,
            last_processed_at=datetime.now(UTC),
        )
        assert row.adapter_name == "claude_code"
        assert row.byte_offset == 1024

    def test_table_name(self) -> None:
        assert AdapterStateRow.__tablename__ == "adapter_state"


class TestSettingRow:
    def test_instantiation_with_valid_data(self) -> None:
        row = SettingRow(
            key="daily_token_limit",
            value="500000",
            updated_at=datetime.now(UTC),
        )
        assert row.key == "daily_token_limit"
        assert row.value == "500000"

    def test_table_name(self) -> None:
        assert SettingRow.__tablename__ == "settings"


class TestAnomalyRow:
    def test_instantiation_with_valid_data(self) -> None:
        row = AnomalyRow(
            id=str(uuid.uuid4()),
            timestamp=datetime.now(UTC),
            severity="warning",
            classification="Usage burst",
            description="Token usage 3x above average",
            score=-0.5,
        )
        assert row.severity == "warning"
        assert row.score == -0.5

    def test_table_name(self) -> None:
        assert AnomalyRow.__tablename__ == "anomalies"


class TestSharedToolEnum:
    def test_tool_enum_is_shared_across_tables(self) -> None:
        """The _tool_enum type object should be the same instance
        used by both TokenEventRow and SessionRow."""
        te_tool_col = TokenEventRow.__table__.c.tool
        sr_tool_col = SessionRow.__table__.c.tool
        assert te_tool_col.type is sr_tool_col.type
        assert te_tool_col.type is _tool_enum


class TestBaseDeclarative:
    def test_all_models_registered(self) -> None:
        table_names = set(Base.metadata.tables.keys())
        expected = {"token_events", "sessions", "adapter_state", "settings", "anomalies"}
        assert expected.issubset(table_names)
