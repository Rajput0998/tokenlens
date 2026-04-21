"""Event pipeline — batch, dedup, enrich, and flush TokenEvents to the database.

Events are accumulated in memory and flushed periodically.
On DB failure, retries up to MAX_FLUSH_RETRIES times with RETRY_DELAY_SECONDS.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from tokenlens.core.database import get_session
from tokenlens.core.models import TokenEventRow
from tokenlens.core.pricing import calculate_cost

if TYPE_CHECKING:
    from tokenlens.core.schema import TokenEvent

logger = logging.getLogger(__name__)

MAX_FLUSH_RETRIES = 10
RETRY_DELAY_SECONDS = 5


class EventPipeline:
    """Batches, deduplicates, enriches, and flushes TokenEvents to the database.

    Events are accumulated in memory and flushed every `flush_interval` seconds.
    On DB failure, retries up to MAX_FLUSH_RETRIES times with RETRY_DELAY_SECONDS.
    """

    def __init__(self, flush_interval: float = 2.0) -> None:
        self._buffer: list[TokenEvent] = []
        self._lock = asyncio.Lock()
        self._flush_interval = flush_interval
        self._total_flushed: int = 0

    async def add_events(self, events: list[TokenEvent]) -> None:
        """Add events to the buffer, enriching cost if 0.0."""
        async with self._lock:
            for event in events:
                # Enrich: recalculate cost if not set
                if event.cost_usd == 0.0:
                    cost, matched = calculate_cost(
                        event.model, event.input_tokens, event.output_tokens
                    )
                    if not matched:
                        logger.warning(
                            "Unrecognized model '%s'. Cost set to $0.00.",
                            event.model,
                        )
                    event.cost_usd = cost
                self._buffer.append(event)

    async def flush(self) -> int:
        """Flush buffered events to DB. Returns count of events written.

        Retry logic: batch stays LOCAL during retry — do NOT put events back
        in _buffer. New events accumulate in _buffer independently.
        """
        async with self._lock:
            if not self._buffer:
                return 0
            batch = self._buffer.copy()
            self._buffer.clear()

        retries = 0
        while retries <= MAX_FLUSH_RETRIES:
            try:
                written = await self._write_batch(batch)
                self._total_flushed += written
                return written
            except Exception:
                retries += 1
                if retries > MAX_FLUSH_RETRIES:
                    logger.error(
                        "Failed to flush %d events after %d retries. Events lost.",
                        len(batch),
                        MAX_FLUSH_RETRIES,
                    )
                    raise
                logger.warning(
                    "DB flush failed (attempt %d/%d). Retrying in %ds.",
                    retries,
                    MAX_FLUSH_RETRIES,
                    RETRY_DELAY_SECONDS,
                )
                await asyncio.sleep(RETRY_DELAY_SECONDS)

        return 0  # unreachable but satisfies type checker

    async def _write_batch(self, batch: list[TokenEvent]) -> int:
        """Write a batch of events using INSERT OR IGNORE for dedup."""
        written = 0
        async with get_session() as session:
            for event in batch:
                stmt = sqlite_insert(TokenEventRow).values(
                    id=str(event.id),
                    tool=event.tool.value,
                    model=event.model,
                    user_id=event.user_id,
                    session_id=event.session_id,
                    timestamp=event.timestamp,
                    input_tokens=event.input_tokens,
                    output_tokens=event.output_tokens,
                    cost_usd=event.cost_usd,
                    context_type=event.context_type.value,
                    turn_number=event.turn_number,
                    cache_read_tokens=event.cache_read_tokens,
                    cache_write_tokens=event.cache_write_tokens,
                    file_types_in_context=event.file_types_in_context,
                    tool_calls=event.tool_calls,
                    raw_metadata=event.raw_metadata,
                    source_file_path=event.source_file_path,
                    file_byte_offset=event.file_byte_offset,
                ).on_conflict_do_nothing(
                    index_elements=["tool", "source_file_path", "file_byte_offset"]
                )
                result = await session.execute(stmt)
                if result.rowcount > 0:
                    written += 1
        return written

    @property
    def pending_count(self) -> int:
        """Number of events waiting in the buffer."""
        return len(self._buffer)

    @property
    def total_flushed(self) -> int:
        """Total number of events successfully written to DB."""
        return self._total_flushed
