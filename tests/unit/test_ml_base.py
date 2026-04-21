"""Tests for ML base module, scheduler, and thread safety locks."""

from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from tokenlens.ml.base import MLModule


# ---------------------------------------------------------------------------
# 19.1 — MLModule ABC
# ---------------------------------------------------------------------------


class TestMLModuleABC:
    """Test that MLModule cannot be instantiated directly."""

    def test_cannot_instantiate_abc(self) -> None:
        with pytest.raises(TypeError, match="abstract"):
            MLModule()  # type: ignore[abstract]

    def test_concrete_subclass_works(self) -> None:
        import pandas as pd

        class DummyModule(MLModule):
            def train(self, data: pd.DataFrame):
                return "model"

            def predict(self, model, input_data: dict):
                return {"result": 1}

            def evaluate(self, model, test_data: pd.DataFrame):
                return {"mae": 0.1}

            def save(self, model, path: Path):
                pass

            def load(self, path: Path):
                return "model"

        m = DummyModule()
        assert m.train(pd.DataFrame()) == "model"


# ---------------------------------------------------------------------------
# 19.3 — MLTaskRunner time checks
# ---------------------------------------------------------------------------


class TestMLTaskRunner:
    """Test MLTaskRunner schedule logic."""

    def test_should_retrain_forecaster_first_run(self) -> None:
        from tokenlens.ml.scheduler import MLTaskRunner

        runner = MLTaskRunner()
        # First run — no last timestamp → should retrain
        assert runner.should_retrain_forecaster() is True

    def test_should_retrain_forecaster_recent(self) -> None:
        from tokenlens.ml.scheduler import MLTaskRunner

        runner = MLTaskRunner()
        runner._last_forecaster_train = datetime.now(UTC) - timedelta(hours=12)
        assert runner.should_retrain_forecaster() is False

    def test_should_retrain_forecaster_overdue(self) -> None:
        from tokenlens.ml.scheduler import MLTaskRunner

        runner = MLTaskRunner()
        runner._last_forecaster_train = datetime.now(UTC) - timedelta(days=2)
        assert runner.should_retrain_forecaster() is True

    def test_should_retrain_anomaly_first_run(self) -> None:
        from tokenlens.ml.scheduler import MLTaskRunner

        runner = MLTaskRunner()
        assert runner.should_retrain_anomaly() is True

    def test_should_retrain_anomaly_recent(self) -> None:
        from tokenlens.ml.scheduler import MLTaskRunner

        runner = MLTaskRunner()
        runner._last_anomaly_train = datetime.now(UTC) - timedelta(days=3)
        assert runner.should_retrain_anomaly() is False

    def test_should_retrain_anomaly_overdue(self) -> None:
        from tokenlens.ml.scheduler import MLTaskRunner

        runner = MLTaskRunner()
        runner._last_anomaly_train = datetime.now(UTC) - timedelta(weeks=2)
        assert runner.should_retrain_anomaly() is True

    def test_should_update_profiles_first_run(self) -> None:
        from tokenlens.ml.scheduler import MLTaskRunner

        runner = MLTaskRunner()
        assert runner.should_update_profiles() is True

    def test_should_update_profiles_recent(self) -> None:
        from tokenlens.ml.scheduler import MLTaskRunner

        runner = MLTaskRunner()
        runner._last_profile_update = datetime.now(UTC) - timedelta(days=3)
        assert runner.should_update_profiles() is False


class TestMLDisabledFlag:
    """Test that ML disabled flag skips task execution."""

    @pytest.mark.asyncio
    async def test_ml_disabled_skips_tasks(self) -> None:
        from tokenlens.ml.scheduler import MLTaskRunner

        runner = MLTaskRunner()
        with patch.object(MLTaskRunner, "is_ml_enabled", return_value=False):
            # Should return immediately without doing anything
            await runner.run_due_tasks()
            # Timestamps should remain None (no work done)
            assert runner._last_forecaster_train is None
            assert runner._last_anomaly_train is None
            assert runner._last_profile_update is None


# ---------------------------------------------------------------------------
# 19.2 — Thread safety locks
# ---------------------------------------------------------------------------


class TestAdapterThreadSafety:
    """Test that concurrent parse_file calls don't corrupt _file_positions."""

    def test_concurrent_parse_file_no_corruption(self, tmp_path: Path) -> None:
        from tokenlens.adapters.claude_code import ClaudeCodeAdapter

        # Create a JSONL file with assistant entries
        log_dir = tmp_path / ".claude" / "projects" / "test"
        log_dir.mkdir(parents=True)
        log_file = log_dir / "test.jsonl"

        lines = []
        for i in range(50):
            lines.append(
                f'{{"role":"assistant","model":"claude-sonnet-4",'
                f'"input_tokens":{100 + i},"output_tokens":{50 + i},'
                f'"timestamp":"2025-01-01T{i % 24:02d}:00:00Z"}}'
            )
        log_file.write_text("\n".join(lines) + "\n")

        adapter = ClaudeCodeAdapter(log_dir=tmp_path / ".claude" / "projects")
        errors: list[Exception] = []

        def parse_worker() -> None:
            try:
                # Reset position so each thread re-parses
                adapter.set_position(log_file, 0)
                adapter.parse_file(log_file)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=parse_worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors during concurrent parse: {errors}"
        # Position should be set to end of file
        pos = adapter.get_last_processed_position(log_file)
        assert pos > 0


class TestSessionManagerThreadSafety:
    """Test that concurrent assign_session_id doesn't corrupt _open_sessions."""

    def test_concurrent_assign_session_id(self) -> None:
        from tokenlens.agent.session import SessionManager
        from tokenlens.core.schema import TokenEvent, ToolEnum

        sm = SessionManager(session_gap_minutes=15)
        errors: list[Exception] = []
        session_ids: list[str] = []
        lock = threading.Lock()

        def assign_worker(idx: int) -> None:
            try:
                event = TokenEvent(
                    tool=ToolEnum.CLAUDE_CODE,
                    model="claude-sonnet-4",
                    user_id="test",
                    timestamp=datetime(2025, 1, 1, 12, 0, idx, tzinfo=UTC),
                    input_tokens=100,
                    output_tokens=50,
                )
                sid = sm.assign_session_id(event)
                with lock:
                    session_ids.append(sid)
            except Exception as e:
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=assign_worker, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Errors during concurrent assign: {errors}"
        assert len(session_ids) == 20
        # All should be the same session (timestamps within 20 seconds)
        assert len(set(session_ids)) == 1
