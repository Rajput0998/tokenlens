"""Claude Code adapter — parses JSONL conversation logs.

Each line in a .jsonl file is a JSON object representing a conversation turn.
The adapter tracks byte offsets per file to support incremental parsing.
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tokenlens.adapters.base import ToolAdapter
from tokenlens.core.pricing import calculate_cost
from tokenlens.core.schema import TokenEvent, ToolEnum

logger = logging.getLogger(__name__)

DEFAULT_LOG_DIR = Path.home() / ".claude" / "projects"


class ClaudeCodeAdapter(ToolAdapter):
    """Parses Claude Code JSONL conversation logs.

    Each line in a .jsonl file is a JSON object representing a conversation turn.
    The adapter tracks byte offsets per file to support incremental parsing.
    """

    def __init__(self, log_dir: Path | None = None) -> None:
        self._log_dir = log_dir or DEFAULT_LOG_DIR
        self._file_positions: dict[str, int] = {}  # path → byte offset
        self._turn_counters: dict[str, int] = {}  # file path → turn count
        self._seen_request_ids: set[str] = set()  # dedup by requestId
        self._lock = threading.Lock()

    @property
    def name(self) -> str:
        return "claude_code"

    @property
    def version(self) -> str:
        return "1.0.0"

    def discover(self) -> bool:
        """Check if log_dir exists and contains any .jsonl files."""
        return self._log_dir.exists() and any(self._log_dir.rglob("*.jsonl"))

    def get_log_paths(self) -> list[Path]:
        """Return sorted list of all .jsonl files via rglob."""
        if not self._log_dir.exists():
            return []
        return sorted(self._log_dir.rglob("*.jsonl"))

    def parse_file(self, path: Path) -> list[TokenEvent]:
        """Parse a JSONL file from the stored byte offset.

        Returns new TokenEvents since last parse. Updates internal position.

        Raises:
            FileNotFoundError: If path does not exist.
        """
        if not path.exists():
            raise FileNotFoundError(f"Log file not found: {path}")

        events: list[TokenEvent] = []
        str_path = str(path)

        with self._lock:
            offset = self._file_positions.get(str_path, 0)

        with open(path, encoding="utf-8") as f:
            f.seek(offset)
            line_number = 0
            while True:
                line_start_offset = f.tell()
                line = f.readline()
                if not line:
                    break
                line_number += 1
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    data = json.loads(stripped)
                    event = self._parse_entry(data, path, line_start_offset)
                    if event is not None:
                        events.append(event)
                except json.JSONDecodeError:
                    logger.warning(
                        "Malformed JSON at %s line %d (offset %d). Skipping.",
                        path.name,
                        line_number,
                        line_start_offset,
                    )
                except Exception:
                    logger.warning(
                        "Error parsing entry at %s line %d. Skipping.",
                        path.name,
                        line_number,
                        exc_info=True,
                    )

            with self._lock:
                self._file_positions[str_path] = f.tell()

        return events

    def _parse_entry(
        self, data: dict[str, Any], path: Path, byte_offset: int
    ) -> TokenEvent | None:
        """Convert a single JSONL entry to a TokenEvent, or None if not applicable.

        Supports both legacy flat format and new nested format:
        - Legacy: {"role": "assistant", "model": "...", "input_tokens": N, ...}
        - New:    {"type": "assistant", "message": {"model": "...", "usage": {"input_tokens": N, ...}}, ...}
        """
        # Determine entry type — new format uses "type" field, legacy uses "role"
        entry_type = data.get("type", "")
        role = data.get("role", "")

        # Skip non-assistant entries
        if entry_type == "assistant":
            # New nested format
            message = data.get("message", {})
            if not isinstance(message, dict):
                return None
            msg_role = message.get("role", "")
            if msg_role != "assistant":
                return None

            model = message.get("model", "unknown")
            usage = message.get("usage", {})
            if not isinstance(usage, dict):
                return None

            input_tokens = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)
            cache_read = usage.get("cache_read_input_tokens", 0)
            cache_write = usage.get("cache_creation_input_tokens", 0)

        elif role == "assistant":
            # Legacy flat format
            model = data.get("model", "unknown")
            input_tokens = data.get("input_tokens", 0)
            output_tokens = data.get("output_tokens", 0)
            cache_read = data.get("cache_read_input_tokens", 0)
            cache_write = data.get("cache_creation_input_tokens", 0)

        else:
            # Not an assistant entry — skip
            return None

        if input_tokens == 0 and output_tokens == 0:
            return None

        # Dedup by requestId — new format writes multiple JSONL lines per API call
        # (one for thinking, one for text) with the same usage. Skip duplicates.
        request_id = data.get("requestId", "")
        if request_id:
            if request_id in self._seen_request_ids:
                return None
            self._seen_request_ids.add(request_id)

        timestamp_raw = data.get("timestamp")
        if timestamp_raw:
            timestamp = datetime.fromisoformat(str(timestamp_raw))
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=UTC)
        else:
            timestamp = datetime.now(UTC)

        cost, _matched = calculate_cost(model, input_tokens, output_tokens, cache_creation_tokens=cache_write, cache_read_tokens=cache_read)

        # Track turn numbers per file for ordering within a parse batch
        turn_key = str(path)
        self._turn_counters[turn_key] = self._turn_counters.get(turn_key, 0) + 1

        # Extract Claude's native sessionId for accurate session window tracking
        claude_session_id = data.get("sessionId", "")

        return TokenEvent(
            tool=ToolEnum.CLAUDE_CODE,
            model=model,
            user_id="default",
            timestamp=timestamp,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read,
            cache_write_tokens=cache_write,
            cost_usd=cost,
            turn_number=self._turn_counters[turn_key],
            source_file_path=str(path),
            file_byte_offset=byte_offset,
            raw_metadata={
                "role": "assistant",
                "claude_session_id": claude_session_id,
            },
        )

    def set_position(self, path: Path, offset: int) -> None:
        """Restore position from adapter_state DB table on daemon startup."""
        with self._lock:
            self._file_positions[str(path)] = offset

    def get_last_processed_position(self, path: Path) -> int:
        """Return stored byte offset for a file."""
        with self._lock:
            return self._file_positions.get(str(path), 0)
