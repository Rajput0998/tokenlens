"""Property-based tests for Claude Code adapter.

**Validates: Requirements FR-P1-06.2, FR-P1-06.3, FR-P1-06.5**
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import hypothesis.strategies as st
from hypothesis import given, settings

from tokenlens.adapters.claude_code import ClaudeCodeAdapter
from tokenlens.core.schema import ToolEnum

# Strategy for valid assistant JSONL entries
model_st = st.sampled_from(["claude-sonnet-4", "claude-opus-4", "claude-haiku-3.5"])

valid_assistant_entry_st = st.fixed_dictionaries(
    {
        "role": st.just("assistant"),
        "model": model_st,
        "input_tokens": st.integers(min_value=1, max_value=100_000),
        "output_tokens": st.integers(min_value=1, max_value=100_000),
        "timestamp": st.just("2025-01-15T10:00:00+00:00"),
    },
    optional={
        "cache_read_input_tokens": st.integers(min_value=0, max_value=10_000),
        "cache_creation_input_tokens": st.integers(min_value=0, max_value=10_000),
    },
)


def _write_jsonl(path: Path, entries: list[dict]) -> None:
    """Write a list of dicts as JSONL lines to a file."""
    with open(path, "w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")


class TestJSONLFieldExtraction:
    """Property 9: JSONL field extraction correctness.

    For any valid JSONL entry with role="assistant", non-negative tokens,
    and a model string, parsing produces a TokenEvent with matching fields.

    **Validates: Requirements FR-P1-06.2**
    """

    @given(entry=valid_assistant_entry_st)
    @settings(max_examples=50)
    def test_valid_assistant_entry_produces_matching_event(
        self, entry: dict
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp) / "projects"
            log_dir.mkdir()
            log_file = log_dir / "test.jsonl"
            _write_jsonl(log_file, [entry])

            adapter = ClaudeCodeAdapter(log_dir=log_dir)
            events = adapter.parse_file(log_file)

            assert len(events) == 1
            event = events[0]
            assert event.tool == ToolEnum.CLAUDE_CODE
            assert event.model == entry["model"]
            assert event.input_tokens == entry["input_tokens"]
            assert event.output_tokens == entry["output_tokens"]
            assert event.cache_read_tokens == entry.get("cache_read_input_tokens", 0)
            assert event.cache_write_tokens == entry.get(
                "cache_creation_input_tokens", 0
            )


class TestIncrementalParsing:
    """Property 10: Incremental parsing produces no duplicates.

    Parsing a file twice without changes returns empty list on second parse.

    **Validates: Requirements FR-P1-06.3**
    """

    @given(
        entries=st.lists(valid_assistant_entry_st, min_size=1, max_size=10),
    )
    @settings(max_examples=30)
    def test_second_parse_returns_empty(
        self, entries: list[dict]
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp) / "projects"
            log_dir.mkdir()
            log_file = log_dir / "test.jsonl"
            _write_jsonl(log_file, entries)

            adapter = ClaudeCodeAdapter(log_dir=log_dir)
            first_result = adapter.parse_file(log_file)
            second_result = adapter.parse_file(log_file)

            assert len(first_result) == len(entries)
            assert len(second_result) == 0


class TestMalformedJSONSkipped:
    """Property 11: Malformed JSON lines skipped.

    A file with N valid assistant entries and M malformed lines
    produces exactly N TokenEvents.

    **Validates: Requirements FR-P1-06.5**
    """

    @given(
        valid_entries=st.lists(valid_assistant_entry_st, min_size=1, max_size=5),
        malformed_count=st.integers(min_value=1, max_value=5),
    )
    @settings(max_examples=30)
    def test_malformed_lines_skipped(
        self,
        valid_entries: list[dict],
        malformed_count: int,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp) / "projects"
            log_dir.mkdir()
            log_file = log_dir / "test.jsonl"

            # Interleave valid and malformed lines
            lines: list[str] = []
            for entry in valid_entries:
                lines.append(json.dumps(entry))
            for _ in range(malformed_count):
                lines.append("{this is not valid json!!!")

            with open(log_file, "w", encoding="utf-8") as f:
                for line in lines:
                    f.write(line + "\n")

            adapter = ClaudeCodeAdapter(log_dir=log_dir)
            events = adapter.parse_file(log_file)

            assert len(events) == len(valid_entries)
