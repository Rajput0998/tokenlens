"""Unit tests for CLI commands: init, agent status, status, and calculate_burn_rate."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from tokenlens.cli.main import app
from tokenlens.core.utils import calculate_burn_rate

runner = CliRunner()


# ---------------------------------------------------------------------------
# calculate_burn_rate tests
# ---------------------------------------------------------------------------


class TestCalculateBurnRate:
    """Test calculate_burn_rate() with various inputs."""

    def test_zero_hours_returns_slow(self) -> None:
        assert calculate_burn_rate(10_000, 0) == "slow"

    def test_negative_hours_returns_slow(self) -> None:
        assert calculate_burn_rate(10_000, -1.0) == "slow"

    def test_slow_rate(self) -> None:
        # 500 tokens / 1 hour = 500/hr → slow
        assert calculate_burn_rate(500, 1.0) == "slow"

    def test_normal_rate(self) -> None:
        # 3000 tokens / 1 hour = 3000/hr → normal
        assert calculate_burn_rate(3_000, 1.0) == "normal"

    def test_fast_rate(self) -> None:
        # 7000 tokens / 1 hour = 7000/hr → fast
        assert calculate_burn_rate(7_000, 1.0) == "fast"

    def test_critical_rate(self) -> None:
        # 15000 tokens / 1 hour = 15000/hr → critical
        assert calculate_burn_rate(15_000, 1.0) == "critical"

    def test_boundary_below_1k(self) -> None:
        # 999 tokens / 1 hour = 999/hr → slow
        assert calculate_burn_rate(999, 1.0) == "slow"

    def test_boundary_at_1k(self) -> None:
        # 1000 tokens / 1 hour = 1000/hr → normal
        assert calculate_burn_rate(1_000, 1.0) == "normal"

    def test_boundary_at_5k(self) -> None:
        # 5000 tokens / 1 hour = 5000/hr → fast
        assert calculate_burn_rate(5_000, 1.0) == "fast"

    def test_boundary_at_10k(self) -> None:
        # 10000 tokens / 1 hour = 10000/hr → critical
        assert calculate_burn_rate(10_000, 1.0) == "critical"

    def test_zero_tokens_returns_slow(self) -> None:
        assert calculate_burn_rate(0, 5.0) == "slow"


# ---------------------------------------------------------------------------
# tokenlens init tests
# ---------------------------------------------------------------------------


class TestInitCommand:
    """Test that `tokenlens init` creates directory structure and config file."""

    def test_init_creates_dirs_and_config(self, tmp_path: object) -> None:
        """Init should create ~/.tokenlens/, logs/, models/ and config.toml."""
        from pathlib import Path

        fake_home = Path(str(tmp_path))
        tokenlens_dir = fake_home / ".tokenlens"
        config_path = tokenlens_dir / "config.toml"

        # Mock adapter registry to avoid real filesystem discovery
        mock_registry = MagicMock()
        mock_adapter = MagicMock()
        mock_adapter.name = "claude_code"
        mock_adapter.get_log_paths.return_value = []
        mock_registry.return_value = mock_registry
        mock_registry.get_all.return_value = [mock_adapter]
        mock_registry.get_available.return_value = []
        mock_registry.get.return_value = None

        with (
            patch("tokenlens.core.config.TOKENLENS_DIR", tokenlens_dir),
            patch("tokenlens.core.config.CONFIG_PATH", config_path),
            patch(
                "tokenlens.core.config.get_data_dir",
                return_value=tokenlens_dir,
            ),
            patch(
                "tokenlens.adapters.registry.AdapterRegistry",
                mock_registry,
            ),
        ):
            result = runner.invoke(app, ["init"])

        assert result.exit_code == 0, result.output
        assert tokenlens_dir.exists()
        assert (tokenlens_dir / "logs").exists()
        assert (tokenlens_dir / "models").exists()
        assert config_path.exists()

        # Verify config content has expected sections
        content = config_path.read_text()
        assert "[general]" in content
        assert "[daemon]" in content
        assert "[adapters.claude_code]" in content

    def test_init_skips_existing_config(self, tmp_path: object) -> None:
        """Init should not overwrite an existing config file."""
        from pathlib import Path

        fake_home = Path(str(tmp_path))
        tokenlens_dir = fake_home / ".tokenlens"
        config_path = tokenlens_dir / "config.toml"

        # Pre-create config
        tokenlens_dir.mkdir(parents=True)
        (tokenlens_dir / "logs").mkdir()
        (tokenlens_dir / "models").mkdir()
        config_path.write_text("# existing config\n")

        mock_registry = MagicMock()
        mock_registry.return_value = mock_registry
        mock_registry.get_all.return_value = []
        mock_registry.get_available.return_value = []
        mock_registry.get.return_value = None

        with (
            patch("tokenlens.core.config.TOKENLENS_DIR", tokenlens_dir),
            patch("tokenlens.core.config.CONFIG_PATH", config_path),
            patch(
                "tokenlens.core.config.get_data_dir",
                return_value=tokenlens_dir,
            ),
            patch(
                "tokenlens.adapters.registry.AdapterRegistry",
                mock_registry,
            ),
        ):
            result = runner.invoke(app, ["init"])

        assert result.exit_code == 0
        assert "already exists" in result.output
        # Config should NOT be overwritten
        assert config_path.read_text() == "# existing config\n"


# ---------------------------------------------------------------------------
# tokenlens agent status tests
# ---------------------------------------------------------------------------


class TestAgentStatusCommand:
    """Test `tokenlens agent status` output format with mock daemon state."""

    def test_agent_status_not_running(self) -> None:
        """When agent is not running, show appropriate message."""
        mock_dm = MagicMock()
        mock_dm.is_running.return_value = (False, None)

        with patch(
            "tokenlens.agent.daemon.DaemonManager",
            return_value=mock_dm,
        ):
            result = runner.invoke(app, ["agent", "status"])

        assert result.exit_code == 0
        assert "not running" in result.output

    def test_agent_status_running(self) -> None:
        """When agent is running, show PID and heartbeat."""
        heartbeat_time = datetime(2025, 1, 15, 10, 30, 0, tzinfo=UTC)

        mock_dm = MagicMock()
        mock_dm.is_running.return_value = (True, 12345)
        mock_dm.read_heartbeat.return_value = heartbeat_time

        with patch(
            "tokenlens.agent.daemon.DaemonManager",
            return_value=mock_dm,
        ):
            result = runner.invoke(app, ["agent", "status"])

        assert result.exit_code == 0
        assert "12345" in result.output
        assert "running" in result.output.lower()


# ---------------------------------------------------------------------------
# tokenlens status tests
# ---------------------------------------------------------------------------


class TestStatusCommand:
    """Test `tokenlens status` output format."""

    def test_status_with_data(self) -> None:
        """Status should show formatted token summary when data exists."""
        mock_result = (
            45_231,  # total_tokens
            {"claude_code": 45_231},  # per_tool
            0.42,  # total_cost
            "normal",  # burn_label
        )

        mock_db_path = MagicMock()
        mock_db_path.exists.return_value = True

        with (
            patch(
                "tokenlens.core.config.get_db_path",
                return_value=mock_db_path,
            ),
            patch(
                "asyncio.run",
                return_value=mock_result,
            ),
        ):
            result = runner.invoke(app, ["status"])

        assert result.exit_code == 0
        assert "45,231" in result.output
        assert "Claude Code" in result.output
        assert "$0.42" in result.output
        assert "normal" in result.output

    def test_status_empty_db(self) -> None:
        """Status should handle empty DB gracefully."""
        mock_db_path = MagicMock()
        mock_db_path.exists.return_value = True

        with (
            patch(
                "tokenlens.core.config.get_db_path",
                return_value=mock_db_path,
            ),
            patch(
                "asyncio.run",
                return_value=None,
            ),
        ):
            result = runner.invoke(app, ["status"])

        assert result.exit_code == 0
        assert "No data yet" in result.output

    def test_status_no_db_file(self) -> None:
        """Status should show init message when DB doesn't exist."""
        mock_db_path = MagicMock()
        mock_db_path.exists.return_value = False

        with patch(
            "tokenlens.core.config.get_db_path",
            return_value=mock_db_path,
        ):
            result = runner.invoke(app, ["status"])

        assert result.exit_code == 0
        assert "No data yet" in result.output
        assert "tokenlens init" in result.output
