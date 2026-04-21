"""Tests for Phase 5 CLI commands."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from tokenlens.cli.main import app

runner = CliRunner()


# --- Shell Hook Tests ---


class TestShellHook:
    """Tests for tokenlens shell-hook command."""

    def test_bash_hook_output(self):
        result = runner.invoke(app, ["shell-hook", "--shell", "bash"])
        assert result.exit_code == 0
        assert "PS1" in result.output
        assert "tokenlens status --short" in result.output

    def test_zsh_hook_output(self):
        result = runner.invoke(app, ["shell-hook", "--shell", "zsh"])
        assert result.exit_code == 0
        assert "precmd_functions" in result.output
        assert "tokenlens status --short" in result.output

    def test_fish_hook_output(self):
        result = runner.invoke(app, ["shell-hook", "--shell", "fish"])
        assert result.exit_code == 0
        assert "fish_right_prompt" in result.output
        assert "tokenlens status --short" in result.output

    def test_unsupported_shell(self):
        result = runner.invoke(app, ["shell-hook", "--shell", "powershell"])
        assert result.exit_code == 1


# --- Status --short Tests ---


class TestStatusShort:
    """Tests for tokenlens status --short."""

    @patch("tokenlens.cli.commands.status.asyncio.run")
    def test_short_with_limit(self, mock_run):
        mock_run.return_value = (42000, {"claude_code": 42000}, 1.5, "normal")

        with (
            patch("tokenlens.core.config.get_db_path") as mock_db_path,
            patch("tokenlens.core.config.settings") as mock_settings,
        ):
            mock_path = MagicMock()
            mock_path.exists.return_value = True
            mock_db_path.return_value = mock_path
            mock_settings.get.return_value = 100000

            result = runner.invoke(app, ["status", "--short"])
            assert result.exit_code == 0
            assert "42K/100K" in result.output

    @patch("tokenlens.cli.commands.status.asyncio.run")
    def test_short_without_limit(self, mock_run):
        mock_run.return_value = (42000, {"claude_code": 42000}, 1.5, "normal")

        with (
            patch("tokenlens.core.config.get_db_path") as mock_db_path,
            patch("tokenlens.core.config.settings") as mock_settings,
        ):
            mock_path = MagicMock()
            mock_path.exists.return_value = True
            mock_db_path.return_value = mock_path
            mock_settings.get.return_value = None

            result = runner.invoke(app, ["status", "--short"])
            assert result.exit_code == 0
            assert "42K" in result.output

    def test_short_no_db(self):
        with patch("tokenlens.core.config.get_db_path") as mock_db_path:
            mock_path = MagicMock()
            mock_path.exists.return_value = False
            mock_db_path.return_value = mock_path

            result = runner.invoke(app, ["status", "--short"])
            assert result.exit_code == 0
            # Should output empty string
            assert result.output.strip() == ""


# --- Report Tests ---


class TestReport:
    """Tests for tokenlens report command."""

    @patch("tokenlens.cli.commands.report.asyncio.run")
    def test_report_no_data(self, mock_run):
        mock_run.return_value = None
        result = runner.invoke(app, ["report", "--period", "today"])
        assert result.exit_code == 0
        assert "No data" in result.output

    @patch("tokenlens.cli.commands.report.asyncio.run")
    def test_report_json_format(self, mock_run):
        mock_run.return_value = {
            "period": "today",
            "since": "2024-01-01T00:00:00+00:00",
            "total_input_tokens": 1000,
            "total_output_tokens": 500,
            "total_tokens": 1500,
            "total_cost": 0.05,
            "per_tool": [
                {
                    "tool": "claude_code",
                    "input_tokens": 1000,
                    "output_tokens": 500,
                    "cost": 0.05,
                    "events": 10,
                }
            ],
            "per_model": [{"model": "claude-sonnet-4", "total_tokens": 1500, "cost": 0.05}],
            "top_sessions": [],
            "avg_efficiency": 75.0,
        }
        result = runner.invoke(app, ["report", "--period", "today", "--format", "json"])
        assert result.exit_code == 0
        assert "total_tokens" in result.output

    @patch("tokenlens.cli.commands.report.asyncio.run")
    def test_report_markdown_format(self, mock_run):
        mock_run.return_value = {
            "period": "today",
            "since": "2024-01-01T00:00:00+00:00",
            "total_input_tokens": 1000,
            "total_output_tokens": 500,
            "total_tokens": 1500,
            "total_cost": 0.05,
            "per_tool": [
                {
                    "tool": "claude_code",
                    "input_tokens": 1000,
                    "output_tokens": 500,
                    "cost": 0.05,
                    "events": 10,
                }
            ],
            "per_model": [{"model": "claude-sonnet-4", "total_tokens": 1500, "cost": 0.05}],
            "top_sessions": [],
            "avg_efficiency": 75.0,
        }
        result = runner.invoke(app, ["report", "--period", "today", "--format", "markdown"])
        assert result.exit_code == 0
        assert "# TokenLens Report" in result.output


# --- Export Tests ---


class TestExport:
    """Tests for tokenlens export command."""

    @patch("tokenlens.cli.commands.export.asyncio.run")
    def test_export_csv(self, mock_run):
        mock_run.return_value = [
            {
                "id": "abc123",
                "tool": "claude_code",
                "model": "claude-sonnet-4",
                "session_id": "sess1",
                "timestamp": "2024-01-01T12:00:00+00:00",
                "input_tokens": 100,
                "output_tokens": 50,
                "cost_usd": 0.01,
                "turn_number": 1,
            }
        ]
        result = runner.invoke(app, ["export", "--format", "csv"])
        assert result.exit_code == 0
        assert "id,tool,model" in result.output
        assert "abc123" in result.output

    @patch("tokenlens.cli.commands.export.asyncio.run")
    def test_export_json(self, mock_run):
        mock_run.return_value = [
            {
                "id": "abc123",
                "tool": "claude_code",
                "model": "claude-sonnet-4",
                "session_id": "sess1",
                "timestamp": "2024-01-01T12:00:00+00:00",
                "input_tokens": 100,
                "output_tokens": 50,
                "cost_usd": 0.01,
                "turn_number": 1,
            }
        ]
        result = runner.invoke(app, ["export", "--format", "json"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert len(parsed) == 1
        assert parsed[0]["id"] == "abc123"

    @patch("tokenlens.cli.commands.export.asyncio.run")
    def test_export_no_data(self, mock_run):
        mock_run.return_value = []
        result = runner.invoke(app, ["export"])
        assert result.exit_code == 0
        assert "No data" in result.output


# --- Predict Tests ---


class TestPredict:
    """Tests for tokenlens predict command."""

    @patch("tokenlens.cli.commands.predict.asyncio.run")
    def test_predict_no_data(self, mock_run):
        mock_run.return_value = None
        result = runner.invoke(app, ["predict"])
        assert result.exit_code == 0
        assert "Insufficient data" in result.output

    @patch("tokenlens.cli.commands.predict.asyncio.run")
    def test_predict_with_data(self, mock_run):
        mock_run.return_value = {
            "burn_rate_per_hour": 2500.0,
            "projected_daily": 60000,
            "projected_monthly": 1800000,
            "daily_cost": 0.54,
            "monthly_cost": 16.2,
            "limit_prediction": {"will_hit_limit": False},
            "model_type": "linear",
        }
        result = runner.invoke(app, ["predict"])
        assert result.exit_code == 0
        assert "2,500" in result.output
        assert "$0.54" in result.output
        assert "linear" in result.output


# --- Kiro Steering Tests ---


class TestKiroSteering:
    """Tests for Kiro steering file generation."""

    def test_render_steering_content(self):
        from tokenlens.integrations.kiro import _render_steering_content

        data = {
            "timestamp": "2024-01-01T12:00:00+00:00",
            "today_tokens": 42000,
            "today_cost": 1.5,
            "weekly_tokens": 200000,
            "weekly_cost": 7.5,
            "burn_rate": "normal",
            "daily_limit": 100000,
            "monthly_budget": 50.0,
            "limit_pct": 42,
            "tips": ["Usage is within normal parameters."],
        }

        content = _render_steering_content(data)
        assert "# Token Budget Status" in content
        assert "42,000 tokens" in content
        assert "normal" in content
        assert "100,000 tokens (42% used)" in content

    def test_generate_tips_critical(self):
        from tokenlens.integrations.kiro import _generate_tips

        data = {
            "burn_rate": "critical",
            "limit_pct": 90,
            "today_tokens": 90000,
            "weekly_tokens": 350000,
        }
        tips = _generate_tips(data)
        assert any("critical" in t.lower() for t in tips)

    def test_generate_tips_normal(self):
        from tokenlens.integrations.kiro import _generate_tips

        data = {
            "burn_rate": "slow",
            "limit_pct": 10,
            "today_tokens": 5000,
            "weekly_tokens": 35000,
        }
        tips = _generate_tips(data)
        assert any("normal" in t.lower() for t in tips)

    def test_is_kiro_integration_disabled_by_default(self):
        from tokenlens.integrations.kiro import is_kiro_integration_enabled

        # Default config has kiro integration disabled
        assert is_kiro_integration_enabled() is False


# --- Live TUI Tests ---


class TestLiveTUI:
    """Tests for tokenlens live command."""

    def test_live_command_registered(self):
        """Verify the live command is registered."""
        result = runner.invoke(app, ["--help"])
        assert "live" in result.output

    def test_textual_import_check(self):
        """Verify textual is importable (installed via [tui] extra)."""
        from tokenlens.cli.live import _check_textual_installed

        # Should not raise since textual is installed
        _check_textual_installed()

    def test_fetch_live_data_returns_dict(self):
        """Test that _fetch_live_data returns expected structure."""
        from tokenlens.cli.live import _fetch_live_data

        # Will return defaults since no DB is set up
        data = asyncio.run(_fetch_live_data())
        assert "total_tokens" in data
        assert "burn_rate" in data
        assert "per_tool" in data
