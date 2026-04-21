"""Unit tests for EventPipeline.

Tests add_events enrichment, flush writes, dedup, and retry logic.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import patch

from sqlalchemy import select

from tokenlens.agent.pipeline import EventPipeline
from tokenlens.core.models import TokenEventRow
from tokenlens.core.schema import TokenEvent, ToolEnum


def _make_event(
    *,
    cost_usd: float = 0.0,
    model: str = "claude-sonnet-4",
    input_tokens: int = 1000,
    output_tokens: int = 500,
    source_file_path: str = "/tmp/test.jsonl",
    file_byte_offset: int | None = None,
) -> TokenEvent:
    """Create a test TokenEvent."""
    return TokenEvent(
        id=uuid.uuid4(),
        tool=ToolEnum.CLAUDE_CODE,
        model=model,
        user_id="test",
        timestamp=datetime(2025, 1, 15, 10, 0, 0, tzinfo=UTC),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
        source_file_path=source_file_path,
        file_byte_offset=file_byte_offset if file_byte_offset is not None else 0,
    )


class TestAddEventsEnrichesCost:
    """Test that add_events recalculates cost when cost_usd is 0.0."""

    async def test_enriches_cost_for_known_model(self) -> None:
        pipeline = EventPipeline()
        event = _make_event(cost_usd=0.0, model="claude-sonnet-4")
        assert event.cost_usd == 0.0

        with patch("tokenlens.agent.pipeline.calculate_cost") as mock_calc:
            mock_calc.return_value = (0.0105, True)
            await pipeline.add_events([event])

        # After enrichment, cost should be > 0 for a known model
        assert pipeline.pending_count == 1
        assert pipeline._buffer[0].cost_usd > 0.0

    async def test_does_not_overwrite_existing_cost(self) -> None:
        pipeline = EventPipeline()
        event = _make_event(cost_usd=42.0, model="claude-sonnet-4")

        await pipeline.add_events([event])

        assert pipeline._buffer[0].cost_usd == 42.0


class TestFlushWritesToDB:
    """Test that flush writes events to DB and clears buffer."""

    async def test_flush_writes_and_clears(self, async_engine: object) -> None:
        # Patch get_session to use our test engine
        from tokenlens.core import database as db_mod

        original_engine = db_mod._engine
        original_factory = db_mod._session_factory
        db_mod._engine = async_engine
        from sqlalchemy.ext.asyncio import async_sessionmaker

        db_mod._session_factory = async_sessionmaker(async_engine, expire_on_commit=False)

        try:
            pipeline = EventPipeline()
            event = _make_event(
                cost_usd=0.01,
                source_file_path="/tmp/test.jsonl",
                file_byte_offset=0,
            )
            await pipeline.add_events([event])
            assert pipeline.pending_count == 1

            written = await pipeline.flush()

            assert written == 1
            assert pipeline.pending_count == 0
            assert pipeline.total_flushed == 1

            # Verify in DB
            async with db_mod._session_factory() as session:
                result = await session.execute(select(TokenEventRow))
                rows = result.scalars().all()
                assert len(rows) == 1
                assert rows[0].model == "claude-sonnet-4"
        finally:
            db_mod._engine = original_engine
            db_mod._session_factory = original_factory


class TestDedup:
    """Test that same event twice results in one DB row."""

    async def test_duplicate_event_deduped(self, async_engine: object) -> None:
        from tokenlens.core import database as db_mod

        original_engine = db_mod._engine
        original_factory = db_mod._session_factory
        db_mod._engine = async_engine
        from sqlalchemy.ext.asyncio import async_sessionmaker

        db_mod._session_factory = async_sessionmaker(async_engine, expire_on_commit=False)

        try:
            pipeline = EventPipeline()
            # Two events with same dedup key (tool, source_file_path, file_byte_offset)
            event1 = _make_event(
                cost_usd=0.01,
                source_file_path="/tmp/test.jsonl",
                file_byte_offset=100,
            )
            event2 = _make_event(
                cost_usd=0.02,
                source_file_path="/tmp/test.jsonl",
                file_byte_offset=100,
            )

            await pipeline.add_events([event1])
            await pipeline.flush()

            await pipeline.add_events([event2])
            written = await pipeline.flush()

            # Second write should be deduped (on_conflict_do_nothing)
            assert written == 0

            async with db_mod._session_factory() as session:
                result = await session.execute(select(TokenEventRow))
                rows = result.scalars().all()
                assert len(rows) == 1
        finally:
            db_mod._engine = original_engine
            db_mod._session_factory = original_factory


class TestRetryLogic:
    """Test retry logic with mocked DB failure."""

    async def test_retries_on_failure_then_succeeds(self) -> None:
        pipeline = EventPipeline()
        event = _make_event(cost_usd=0.01, file_byte_offset=0)
        await pipeline.add_events([event])

        call_count = 0

        async def mock_write_batch(batch: list[TokenEvent]) -> int:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RuntimeError("DB unavailable")
            return len(batch)

        with (
            patch.object(pipeline, "_write_batch", side_effect=mock_write_batch),
            patch("tokenlens.agent.pipeline.RETRY_DELAY_SECONDS", 0),
        ):
                written = await pipeline.flush()

        assert written == 1
        assert call_count == 3  # 2 failures + 1 success

    async def test_new_events_independent_during_retry(self) -> None:
        """During retry, new events added to buffer are independent of retrying batch."""
        pipeline = EventPipeline()
        event1 = _make_event(cost_usd=0.01, file_byte_offset=0)
        await pipeline.add_events([event1])

        call_count = 0

        async def mock_write_batch(batch: list[TokenEvent]) -> int:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # During first retry, add a new event to the buffer
                event2 = _make_event(cost_usd=0.02, file_byte_offset=100)
                await pipeline.add_events([event2])
                raise RuntimeError("DB unavailable")
            return len(batch)

        with (
            patch.object(pipeline, "_write_batch", side_effect=mock_write_batch),
            patch("tokenlens.agent.pipeline.RETRY_DELAY_SECONDS", 0),
        ):
                written = await pipeline.flush()

        # First batch (event1) should have been written on retry
        assert written == 1
        # event2 should still be in the buffer, independent
        assert pipeline.pending_count == 1
