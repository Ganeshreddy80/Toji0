"""Tests for the Configuration Manager."""

from __future__ import annotations

import os

import pytest

from toji_platform.core.configuration import ConfigurationManager
from toji_platform.core.errors import ConfigurationError, MissingConfigError
from toji_platform.core.types import Profile


class TestConfigurationManager:
    """Tests for ConfigurationManager."""

    def test_get_with_default(self):
        cfg = ConfigurationManager()
        assert cfg.get("nonexistent", "fallback") == "fallback"

    def test_get_returns_none_without_default(self):
        cfg = ConfigurationManager()
        assert cfg.get("nonexistent") is None

    def test_overrides_take_precedence(self):
        cfg = ConfigurationManager(overrides={"app.name": "toji-test"})
        assert cfg.get("app.name") == "toji-test"

    def test_set_and_get(self):
        cfg = ConfigurationManager()
        cfg.set("custom.key", "custom-value")
        assert cfg.get("custom.key") == "custom-value"

    def test_get_required_raises_when_missing(self):
        cfg = ConfigurationManager()
        with pytest.raises(MissingConfigError, match="no.such.key"):
            cfg.get_required("no.such.key")

    def test_get_required_returns_value(self):
        cfg = ConfigurationManager(overrides={"api.key": "secret"})
        assert cfg.get_required("api.key") == "secret"

    def test_get_section(self):
        cfg = ConfigurationManager(
            overrides={
                "database.host": "localhost",
                "database.port": "5432",
                "redis.host": "localhost",
            }
        )
        section = cfg.get_section("database")
        assert "database.host" in section
        assert "database.port" in section
        assert "redis.host" not in section

    def test_validate_passes_with_all_keys_present(self):
        cfg = ConfigurationManager(
            overrides={"a": "1", "b": "2"}
        )
        cfg.validate(["a", "b"])  # should not raise

    def test_validate_raises_with_missing_keys(self):
        cfg = ConfigurationManager(overrides={"a": "1"})
        with pytest.raises(ConfigurationError, match="b"):
            cfg.validate(["a", "b"])

    def test_all_returns_copy(self):
        cfg = ConfigurationManager(overrides={"x": "y"})
        data = cfg.all()
        assert "x" in data

    def test_env_var_loading(self, monkeypatch):
        """TOJI_* env vars are mapped to dot-separated keys."""
        monkeypatch.setenv("TOJI_DATABASE_HOST", "db.example.com")
        monkeypatch.setenv("TOJI_DATABASE_PORT", "5432")
        cfg = ConfigurationManager()
        assert cfg.get("database.host") == "db.example.com"
        assert cfg.get("database.port") == "5432"

    def test_profile_from_env(self, monkeypatch):
        monkeypatch.setenv("TOJI_APP_ENV", "production")
        cfg = ConfigurationManager()
        assert cfg.profile == Profile.PRODUCTION

    def test_profile_defaults_to_development(self):
        cfg = ConfigurationManager()
        # Without TOJI_APP_ENV set, should default to development
        assert cfg.profile in (Profile.DEVELOPMENT, Profile.TESTING, Profile.PRODUCTION)

    def test_invalid_profile_defaults_to_development(self):
        cfg = ConfigurationManager(overrides={"app.env": "staging"})
        assert cfg.profile == Profile.DEVELOPMENT

    def test_testing_profile(self, monkeypatch):
        monkeypatch.setenv("TOJI_APP_ENV", "testing")
        cfg = ConfigurationManager()
        assert cfg.profile == Profile.TESTING
