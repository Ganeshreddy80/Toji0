"""Comprehensive tests for R51 Central Configuration Framework."""

from __future__ import annotations

import os
import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class TestConfigModels:
    def test_central_config_defaults(self):
        from research_platform.config.models import CentralConfig
        cfg = CentralConfig()
        assert cfg.version == 1
        assert cfg.database.host == "localhost"
        assert cfg.database.port == 5432
        assert cfg.runtime.mode == "PAPER"
        assert cfg.risk.max_order_size == 1000.0

    def test_database_config_fields(self):
        from research_platform.config.models import DatabaseConfig
        db = DatabaseConfig(host="myhost", port=5433, database="mydb")
        assert db.host == "myhost"
        assert db.port == 5433
        assert db.database == "mydb"

    def test_exchange_config_fields(self):
        from research_platform.config.models import ExchangeConfig
        ex = ExchangeConfig(api_key="key123", symbol_filters=["BTC"])
        assert ex.api_key == "key123"
        assert "BTC" in ex.symbol_filters

    def test_strategy_config(self):
        from research_platform.config.models import StrategyConfig
        s = StrategyConfig(strategy_id="momentum-v1", allocation_pct=0.5)
        assert s.strategy_id == "momentum-v1"
        assert s.allocation_pct == 0.5

    def test_risk_config_bounds(self):
        from research_platform.config.models import RiskConfig
        risk = RiskConfig(max_order_size=500.0, max_daily_drawdown_pct=0.03)
        assert risk.max_order_size == 500.0

    def test_runtime_config_modes(self):
        from research_platform.config.models import RuntimeConfig
        for mode in ["DEV", "PAPER", "PROD"]:
            rt = RuntimeConfig(mode=mode)
            assert rt.mode == mode

    def test_monitoring_config(self):
        from research_platform.config.models import MonitoringConfig
        m = MonitoringConfig(latency_threshold_ms=25.0, cpu_limit_pct=75.0)
        assert m.latency_threshold_ms == 25.0

    def test_recovery_config(self):
        from research_platform.config.models import RecoveryConfig
        r = RecoveryConfig(checkpoint_interval_sec=15.0, max_recovery_retries=5)
        assert r.checkpoint_interval_sec == 15.0

    def test_central_config_serialization(self):
        from research_platform.config.models import CentralConfig
        cfg = CentralConfig()
        d = cfg.model_dump()
        assert "database" in d
        assert "risk" in d
        assert "runtime" in d

    def test_central_config_roundtrip(self):
        from research_platform.config.models import CentralConfig
        cfg = CentralConfig()
        d = cfg.model_dump()
        restored = CentralConfig.model_validate(d)
        assert restored.version == cfg.version
        assert restored.database.host == cfg.database.host


# ---------------------------------------------------------------------------
# Defaults & Profiles
# ---------------------------------------------------------------------------

class TestDefaults:
    def test_dev_profile_mode(self):
        from research_platform.config.defaults import DEFAULT_DEV_PROFILE
        assert DEFAULT_DEV_PROFILE["runtime"]["mode"] == "DEV"

    def test_paper_profile_mode(self):
        from research_platform.config.defaults import DEFAULT_PAPER_PROFILE
        assert DEFAULT_PAPER_PROFILE["runtime"]["mode"] == "PAPER"

    def test_prod_profile_mode(self):
        from research_platform.config.defaults import DEFAULT_PROD_PROFILE
        assert DEFAULT_PROD_PROFILE["runtime"]["mode"] == "PROD"

    def test_prod_has_larger_order_size(self):
        from research_platform.config.defaults import DEFAULT_PROD_PROFILE, DEFAULT_DEV_PROFILE
        assert DEFAULT_PROD_PROFILE["risk"]["max_order_size"] > DEFAULT_DEV_PROFILE["risk"]["max_order_size"]


class TestProfiles:
    def test_paper_profile_loads(self):
        from research_platform.config.profiles import ConfigProfileLoader
        p = ConfigProfileLoader.get_profile_defaults("PAPER")
        assert p["runtime"]["mode"] == "PAPER"

    def test_dev_profile_loads(self):
        from research_platform.config.profiles import ConfigProfileLoader
        p = ConfigProfileLoader.get_profile_defaults("DEV")
        assert p["runtime"]["mode"] == "DEV"

    def test_prod_profile_loads(self):
        from research_platform.config.profiles import ConfigProfileLoader
        p = ConfigProfileLoader.get_profile_defaults("PROD")
        assert p["runtime"]["mode"] == "PROD"

    def test_unknown_profile_defaults_to_paper(self):
        from research_platform.config.profiles import ConfigProfileLoader
        p = ConfigProfileLoader.get_profile_defaults("UNKNOWN")
        assert p["runtime"]["mode"] == "PAPER"

    def test_case_insensitive(self):
        from research_platform.config.profiles import ConfigProfileLoader
        p = ConfigProfileLoader.get_profile_defaults("prod")
        assert p["runtime"]["mode"] == "PROD"


# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

class TestEnvironmentLoader:
    def test_env_parses_integer(self):
        from research_platform.config.environment import EnvironmentLoader
        with patch.dict(os.environ, {"TOJI_DATABASE_PORT": "9999"}):
            overrides = EnvironmentLoader.load_from_env()
        assert overrides.get("database", {}).get("port") == 9999

    def test_env_parses_float(self):
        from research_platform.config.environment import EnvironmentLoader
        with patch.dict(os.environ, {"TOJI_RISK_SLIPPAGE": "0.03"}):
            overrides = EnvironmentLoader.load_from_env()
        assert overrides.get("risk", {}).get("slippage") == 0.03

    def test_env_parses_bool_true(self):
        from research_platform.config.environment import EnvironmentLoader
        with patch.dict(os.environ, {"TOJI_REPORTING_ENABLED": "TRUE"}):
            overrides = EnvironmentLoader.load_from_env()
        assert overrides.get("reporting", {}).get("enabled") is True

    def test_env_parses_bool_false(self):
        from research_platform.config.environment import EnvironmentLoader
        with patch.dict(os.environ, {"TOJI_REPORTING_ENABLED": "FALSE"}):
            overrides = EnvironmentLoader.load_from_env()
        assert overrides.get("reporting", {}).get("enabled") is False

    def test_env_parses_string(self):
        from research_platform.config.environment import EnvironmentLoader
        with patch.dict(os.environ, {"TOJI_DATABASE_HOST": "myserver"}):
            overrides = EnvironmentLoader.load_from_env()
        assert overrides.get("database", {}).get("host") == "myserver"

    def test_non_toji_env_ignored(self):
        from research_platform.config.environment import EnvironmentLoader
        with patch.dict(os.environ, {"SOME_OTHER_VAR": "value"}):
            overrides = EnvironmentLoader.load_from_env()
        assert "SOME_OTHER_VAR" not in overrides


# ---------------------------------------------------------------------------
# Secrets
# ---------------------------------------------------------------------------

class TestSecretsManager:
    def test_plain_password_unchanged(self):
        from research_platform.config.secrets import SecretsManager
        cfg = {"database": {"password": "plain-pass"}}
        result = SecretsManager.resolve_secrets(cfg)
        assert result["database"]["password"] == "plain-pass"

    def test_base64_password_decoded(self):
        import base64
        from research_platform.config.secrets import SecretsManager
        encoded = "base64:" + base64.b64encode(b"decoded-secret").decode()
        cfg = {"database": {"password": encoded}}
        result = SecretsManager.resolve_secrets(cfg)
        assert result["database"]["password"] == "decoded-secret"

    def test_exchange_api_key_decoded(self):
        import base64
        from research_platform.config.secrets import SecretsManager
        encoded = "base64:" + base64.b64encode(b"mykey").decode()
        cfg = {"exchange": {"api_key": encoded}}
        result = SecretsManager.resolve_secrets(cfg)
        assert result["exchange"]["api_key"] == "mykey"

    def test_invalid_base64_does_not_crash(self):
        from research_platform.config.secrets import SecretsManager
        cfg = {"database": {"password": "base64:!!!notvalid!!!"}}
        result = SecretsManager.resolve_secrets(cfg)
        # Should not raise
        assert "password" in result["database"]


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------

class TestConfigValidator:
    def test_valid_config_passes(self):
        from research_platform.config.config_validator import ConfigValidator
        from research_platform.config.defaults import DEFAULT_PAPER_PROFILE
        errors = ConfigValidator.validate(DEFAULT_PAPER_PROFILE)
        assert errors == []

    def test_invalid_port_fails(self):
        from research_platform.config.config_validator import ConfigValidator
        cfg = {"database": {"port": 99999}}
        errors = ConfigValidator.validate(cfg)
        assert any("port" in e for e in errors)

    def test_invalid_slippage_fails(self):
        from research_platform.config.config_validator import ConfigValidator
        cfg = {"database": {"port": 5432}, "risk": {"max_slippage_pct": 0.9}}
        errors = ConfigValidator.validate(cfg)
        assert any("slippage" in e for e in errors)

    def test_zero_slippage_passes(self):
        from research_platform.config.config_validator import ConfigValidator
        cfg = {"database": {"port": 5432}, "risk": {"max_slippage_pct": 0.0}}
        errors = ConfigValidator.validate(cfg)
        slippage_errors = [e for e in errors if "slippage" in e]
        assert slippage_errors == []


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

class TestConfigLoader:
    def test_load_returns_dict(self):
        from research_platform.config.config_loader import ConfigLoader
        loader = ConfigLoader("PAPER")
        cfg = loader.load_configuration()
        assert isinstance(cfg, dict)
        assert "database" in cfg

    def test_merge_dicts_deep(self):
        from research_platform.config.config_loader import ConfigLoader
        loader = ConfigLoader()
        a = {"database": {"host": "localhost", "port": 5432}, "risk": {"max_order_size": 100}}
        b = {"database": {"host": "remotehost"}, "new_key": "val"}
        merged = loader.merge_dicts(a, b)
        assert merged["database"]["host"] == "remotehost"
        assert merged["database"]["port"] == 5432
        assert merged["new_key"] == "val"

    def test_override_applied(self):
        from research_platform.config.config_loader import ConfigLoader
        loader = ConfigLoader("PAPER")
        cfg = loader.load_configuration(overrides={"database": {"host": "override-host"}})
        assert cfg["database"]["host"] == "override-host"

    def test_profile_dev_loaded(self):
        from research_platform.config.config_loader import ConfigLoader
        loader = ConfigLoader("DEV")
        cfg = loader.load_configuration()
        assert cfg["runtime"]["mode"] == "DEV"

    def test_missing_yaml_graceful(self):
        from research_platform.config.config_loader import ConfigLoader
        loader = ConfigLoader("PAPER")
        cfg = loader.load_configuration(yaml_path="/nonexistent/config.yaml")
        assert isinstance(cfg, dict)


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

class TestSchema:
    def test_schema_is_dict(self):
        from research_platform.config.schema import ConfigSchemaGenerator
        schema = ConfigSchemaGenerator.get_json_schema()
        assert isinstance(schema, dict)
        assert "properties" in schema or "$defs" in schema or "title" in schema

    def test_schema_contains_database(self):
        from research_platform.config.schema import ConfigSchemaGenerator
        schema = ConfigSchemaGenerator.get_json_schema()
        schema_str = str(schema)
        assert "database" in schema_str.lower() or "Database" in schema_str


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

class TestConfigEvents:
    def test_config_loaded_event(self):
        from research_platform.config.events import ConfigLoaded
        import uuid
        ev = ConfigLoaded(event_id=str(uuid.uuid4()), profile="PAPER", version=1)
        assert ev.profile == "PAPER"
        assert ev.version == 1

    def test_config_overridden_event(self):
        from research_platform.config.events import ConfigOverridden
        import uuid
        ev = ConfigOverridden(event_id=str(uuid.uuid4()), overridden_keys=["database", "risk"])
        assert "database" in ev.overridden_keys

    def test_config_hot_reloaded_event(self):
        from research_platform.config.events import ConfigHotReloaded
        from datetime import datetime, timezone
        import uuid
        ev = ConfigHotReloaded(event_id=str(uuid.uuid4()), updated_at=datetime.now(timezone.utc))
        assert ev.updated_at is not None


# ---------------------------------------------------------------------------
# HotReloader
# ---------------------------------------------------------------------------

class TestHotReloader:
    def test_start_and_stop(self, tmp_path):
        from research_platform.config.hot_reload import ConfigHotReloader
        f = tmp_path / "config.yaml"
        f.write_text("version: 1")
        called = []
        reloader = ConfigHotReloader(str(f), callback=lambda: called.append(1), interval_sec=0.05)
        reloader.start()
        import time
        # Modify file to trigger reload
        time.sleep(0.1)
        f.write_text("version: 2")
        time.sleep(0.2)
        reloader.stop()
        # callback should have been invoked at least once
        assert len(called) >= 1

    def test_stop_without_start(self, tmp_path):
        from research_platform.config.hot_reload import ConfigHotReloader
        f = tmp_path / "c.yaml"
        f.write_text("")
        reloader = ConfigHotReloader(str(f), callback=lambda: None)
        reloader.stop()  # should not raise


# ---------------------------------------------------------------------------
# ConfigManager
# ---------------------------------------------------------------------------

class TestConfigManager:
    def test_get_config_returns_central_config(self):
        from research_platform.config.config_manager import ConfigManager
        from research_platform.config.models import CentralConfig
        mgr = ConfigManager()
        cfg = mgr.get_config()
        assert isinstance(cfg, CentralConfig)

    def test_apply_valid_overrides(self):
        from research_platform.config.config_manager import ConfigManager
        mgr = ConfigManager()
        mgr.apply_overrides({"database": {"host": "newhost"}})
        assert mgr.get_config().database.host == "newhost"

    def test_apply_invalid_overrides_raises(self):
        from research_platform.config.config_manager import ConfigManager
        mgr = ConfigManager()
        with pytest.raises((ValueError, Exception)):
            mgr.apply_overrides({"database": {"port": 999999}})

    def test_reload_does_not_crash(self):
        from research_platform.config.config_manager import ConfigManager
        mgr = ConfigManager()
        mgr.reload()  # Should not raise

    def test_shutdown_stops_reloader(self):
        from research_platform.config.config_manager import ConfigManager
        mgr = ConfigManager()
        mgr.shutdown()  # Should not raise

    def test_thread_safe_concurrent_access(self):
        import threading
        from research_platform.config.config_manager import ConfigManager
        mgr = ConfigManager()
        errors = []

        def read():
            try:
                _ = mgr.get_config()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=read) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []
