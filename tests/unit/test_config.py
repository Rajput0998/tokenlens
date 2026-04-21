"""Unit tests for configuration system.

**Validates: Requirements FR-P1-11.1, FR-P1-11.3, FR-P1-11.4**
"""

from __future__ import annotations

import os
from pathlib import Path

import hypothesis.strategies as st
from hypothesis import given, settings

from tokenlens.core.config import (
    DEFAULT_CONFIG_TEMPLATE,
    TOKENLENS_DIR,
    get_data_dir,
    get_db_path,
    get_pricing_table,
    get_session_gap_minutes,
)


class TestDefaults:
    """Test default values when no config file exists."""

    def test_default_data_dir(self) -> None:
        data_dir = get_data_dir()
        assert isinstance(data_dir, Path)
        assert str(data_dir).endswith(".tokenlens")

    def test_default_db_path(self) -> None:
        db_path = get_db_path()
        assert str(db_path).endswith("tokenlens.db")

    def test_default_session_gap(self) -> None:
        gap = get_session_gap_minutes("claude_code")
        assert gap == 15

    def test_default_pricing_table_is_dict(self) -> None:
        table = get_pricing_table()
        assert isinstance(table, dict)

    def test_tokenlens_dir_constant(self) -> None:
        assert TOKENLENS_DIR == Path.home() / ".tokenlens"


class TestConfigTemplate:
    """Test the DEFAULT_CONFIG_TEMPLATE string."""

    def test_template_contains_required_sections(self) -> None:
        assert "[general]" in DEFAULT_CONFIG_TEMPLATE
        assert "[daemon]" in DEFAULT_CONFIG_TEMPLATE
        assert "[adapters.claude_code]" in DEFAULT_CONFIG_TEMPLATE
        assert "[adapters.kiro]" in DEFAULT_CONFIG_TEMPLATE
        assert "[pricing.models]" in DEFAULT_CONFIG_TEMPLATE
        assert "[api]" in DEFAULT_CONFIG_TEMPLATE
        assert "[alerts]" in DEFAULT_CONFIG_TEMPLATE
        assert "[alerts.thresholds]" in DEFAULT_CONFIG_TEMPLATE
        assert "[alerts.webhooks]" in DEFAULT_CONFIG_TEMPLATE
        assert "[ml]" in DEFAULT_CONFIG_TEMPLATE
        assert "[ml.anomaly]" in DEFAULT_CONFIG_TEMPLATE
        assert "[integrations.kiro]" in DEFAULT_CONFIG_TEMPLATE


class TestLoadFromToml:
    """Test loading from a temporary TOML file."""

    def test_load_from_temp_toml(self, tmp_path: Path) -> None:
        from dynaconf import Dynaconf

        config_file = tmp_path / "config.toml"
        config_file.write_text(
            '[general]\nuser_id = "testuser"\ndata_dir = "/tmp/tokenlens-test"\n'
        )
        test_settings = Dynaconf(
            envvar_prefix="TOKENLENS",
            settings_files=[str(config_file)],
            environments=False,
            load_dotenv=False,
        )
        assert test_settings.get("general.user_id") == "testuser"
        assert test_settings.get("general.data_dir") == "/tmp/tokenlens-test"


class TestEnvVarOverrides:
    """Property 14: Environment variable overrides.

    Setting TOKENLENS_ prefixed env var overrides TOML value.

    **Validates: Requirements FR-P1-11.3**
    """

    @given(value=st.text(min_size=1, max_size=20, alphabet=st.characters(categories=("L",))))
    @settings(max_examples=20)
    def test_env_var_overrides_toml(self, value: str) -> None:
        import tempfile

        from dynaconf import Dynaconf

        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write('[general]\nuser_id = "original"\n')
            config_file = f.name

        env_key = "TOKENLENS_GENERAL__USER_ID"
        old_val = os.environ.get(env_key)
        try:
            os.environ[env_key] = value
            test_settings = Dynaconf(
                envvar_prefix="TOKENLENS",
                settings_files=[config_file],
                environments=False,
                load_dotenv=False,
            )
            # dynaconf may auto-cast; compare string representations
            result = str(test_settings.get("general.user_id"))
            assert result == value
        finally:
            if old_val is None:
                os.environ.pop(env_key, None)
            else:
                os.environ[env_key] = old_val
            os.unlink(config_file)
