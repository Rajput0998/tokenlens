"""Integration tests for the database layer.

**Validates: Requirements FR-P1-08.1, FR-P1-09.9**
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from tokenlens.core.database import close_engine, get_session, init_engine
from tokenlens.core.models import Base, TokenEventRow


@pytest.fixture(autouse=True)
async def _reset_engine():
    """Ensure engine is reset before and after each test."""
    await close_engine()
    yield
    await close_engine()


class TestInitEngine:
    async def test_creates_tables_in_memory(self) -> None:
        engine = await init_engine("sqlite+aiosqlite:///:memory:")
        async with engine.connect() as conn:
            # Verify tables exist by querying sqlite_master
            result = await conn.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            tables = {row[0] for row in result}
        assert "token_events" in tables
        assert "sessions" in tables
        assert "adapter_state" in tables
        assert "settings" in tables

    async def test_idempotent_init(self) -> None:
        engine1 = await init_engine("sqlite+aiosqlite:///:memory:")
        engine2 = await init_engine("sqlite+aiosqlite:///:memory:")
        assert engine1 is engine2


class TestGetSession:
    async def test_commits_on_success(self) -> None:
        await init_engine("sqlite+aiosqlite:///:memory:")
        row_id = str(uuid.uuid4())
        async with get_session() as session:
            row = TokenEventRow(
                id=row_id,
                tool="claude_code",
                model="claude-sonnet-4",
                user_id="user1",
                session_id=str(uuid.uuid4()),
                timestamp=datetime.now(UTC),
                input_tokens=100,
                output_tokens=50,
                cost_usd=0.01,
            )
            session.add(row)

        # Read back in a new session to confirm commit
        async with get_session() as session:
            result = await session.execute(
                select(TokenEventRow).where(TokenEventRow.id == row_id)
            )
            found = result.scalar_one_or_none()
        assert found is not None
        assert found.id == row_id

    async def test_rolls_back_on_exception(self) -> None:
        await init_engine("sqlite+aiosqlite:///:memory:")
        row_id = str(uuid.uuid4())
        with pytest.raises(RuntimeError):
            async with get_session() as session:
                row = TokenEventRow(
                    id=row_id,
                    tool="claude_code",
                    model="claude-sonnet-4",
                    user_id="user1",
                    session_id=str(uuid.uuid4()),
                    timestamp=datetime.now(UTC),
                    input_tokens=100,
                    output_tokens=50,
                    cost_usd=0.01,
                )
                session.add(row)
                raise RuntimeError("Simulated failure")

        # Row should not exist after rollback
        async with get_session() as session:
            result = await session.execute(
                select(TokenEventRow).where(TokenEventRow.id == row_id)
            )
            found = result.scalar_one_or_none()
        assert found is None


class TestInsertAndRead:
    async def test_insert_token_event_and_read_back(self) -> None:
        await init_engine("sqlite+aiosqlite:///:memory:")
        row_id = str(uuid.uuid4())
        now = datetime.now(UTC)

        async with get_session() as session:
            row = TokenEventRow(
                id=row_id,
                tool="claude_code",
                model="claude-sonnet-4",
                user_id="testuser",
                session_id=str(uuid.uuid4()),
                timestamp=now,
                input_tokens=500,
                output_tokens=200,
                cost_usd=0.05,
                context_type="code_generation",
                turn_number=3,
            )
            session.add(row)

        async with get_session() as session:
            result = await session.execute(
                select(TokenEventRow).where(TokenEventRow.id == row_id)
            )
            found = result.scalar_one()
        assert found.model == "claude-sonnet-4"
        assert found.input_tokens == 500
        assert found.output_tokens == 200
        assert found.context_type == "code_generation"
        assert found.turn_number == 3


class TestCloseEngine:
    async def test_close_disposes_cleanly(self) -> None:
        await init_engine("sqlite+aiosqlite:///:memory:")
        await close_engine()
        # After close, init_engine should create a new engine
        engine = await init_engine("sqlite+aiosqlite:///:memory:")
        assert engine is not None


class TestDatabaseDedup:
    """Property 13: Database-level dedup.

    Inserting the same (tool, source_file_path, file_byte_offset) twice
    results in exactly one row due to the unique constraint.

    **Validates: Requirements FR-P1-09.9**
    """

    async def test_duplicate_dedup_key_raises_integrity_error(self) -> None:
        await init_engine("sqlite+aiosqlite:///:memory:")
        shared_path = "/home/user/.claude/projects/test.jsonl"
        shared_offset = 1024

        async with get_session() as session:
            row1 = TokenEventRow(
                id=str(uuid.uuid4()),
                tool="claude_code",
                model="claude-sonnet-4",
                user_id="user1",
                session_id=str(uuid.uuid4()),
                timestamp=datetime.now(UTC),
                input_tokens=100,
                output_tokens=50,
                source_file_path=shared_path,
                file_byte_offset=shared_offset,
            )
            session.add(row1)

        with pytest.raises(IntegrityError):
            async with get_session() as session:
                row2 = TokenEventRow(
                    id=str(uuid.uuid4()),
                    tool="claude_code",
                    model="claude-sonnet-4",
                    user_id="user1",
                    session_id=str(uuid.uuid4()),
                    timestamp=datetime.now(UTC),
                    input_tokens=200,
                    output_tokens=100,
                    source_file_path=shared_path,
                    file_byte_offset=shared_offset,
                )
                session.add(row2)

        # Verify only one row exists
        async with get_session() as session:
            result = await session.execute(
                select(TokenEventRow).where(
                    TokenEventRow.source_file_path == shared_path,
                    TokenEventRow.file_byte_offset == shared_offset,
                )
            )
            rows = result.scalars().all()
        assert len(rows) == 1
