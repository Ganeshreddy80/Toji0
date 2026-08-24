from __future__ import annotations

import inspect
import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from research_platform.config.aws_database import AWSDatabaseSecretProvider
from research_platform.config.config_loader import ConfigLoader
from research_platform.config.plugin import ConfigPlugin
from research_platform.config.repository import ConfigRepository
from research_platform.platform.configuration_boot import ConfigurationBootloader
from research_platform.platform.service_registry import ServiceRegistry


class FakeSecretsManagerClient:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def get_secret_value(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.response


def secret_provider(payload: dict, *, name: str = "toji/database/paper"):
    client = FakeSecretsManagerClient({"SecretString": json.dumps(payload)})
    return AWSDatabaseSecretProvider(secret_name=name, region_name="us-east-1", client=client), client


def test_secret_provider_normalizes_rds_json_without_logging_values():
    provider, client = secret_provider(
        {"engine": "postgres", "host": "rds.example", "port": "5432", "dbname": "toji", "username": "toji", "password": "unit-secret"}
    )

    result = provider.load_database_config()

    assert result == {
        "host": "rds.example",
        "port": 5432,
        "database": "toji",
        "username": "toji",
        "password": "unit-secret",
    }
    assert client.calls == [{"SecretId": "toji/database/paper"}]


def test_secret_provider_does_not_leak_secret_value(caplog):
    secret_value = "must-not-appear-in-error-or-log"
    client = FakeSecretsManagerClient(error=RuntimeError(f"provider payload {secret_value}"))
    provider = AWSDatabaseSecretProvider(secret_name="toji/database/paper", client=client)

    with pytest.raises(RuntimeError, match="Unable to retrieve database configuration") as exc_info:
        provider.load_database_config()

    assert secret_value not in str(exc_info.value)
    assert secret_value not in caplog.text


def test_no_database_credentials_embedded_in_scoped_configuration():
    root = Path(__file__).parents[2]
    source_files = [
        root / "research_platform/config/defaults.py",
        root / "research_platform/config/models.py",
        root / "docker-compose.yml",
    ]
    for path in source_files:
        content = path.read_text(encoding="utf-8")
        assert not re.search(r"[\\\"']password[\\\"']\\s*:\\s*[\\\"'][^\\\"']+[\\\"']", content)
    assert "POSTGRES_PASSWORD: password" not in (root / "docker-compose.yml").read_text(encoding="utf-8")


def test_paper_configuration_resolves_from_secure_secret(monkeypatch):
    provider, _ = secret_provider(
        {"host": "rds.paper", "port": 5432, "database": "toji", "username": "toji", "password": "paper-secret"}
    )
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("TOJI_PROFILE", "PAPER")

    config = ConfigLoader(
        "PAPER", require_secure_database=True, secret_provider=provider
    ).load_configuration()

    assert config["database"]["host"] == "rds.paper"
    assert config["database"]["database"] == "toji"
    assert config["database"]["password"] == "paper-secret"


def test_database_url_remains_an_explicit_override(monkeypatch):
    provider, _ = secret_provider(
        {"host": "rds.paper", "database": "toji", "username": "toji", "password": "paper-secret"}
    )
    monkeypatch.setenv("DATABASE_URL", "postgresql://env-user:env-pass@env-host:5432/env-db?sslmode=verify-full")

    config = ConfigLoader(
        "PAPER", require_secure_database=True, secret_provider=provider
    ).load_configuration()

    assert config["database"]["host"] == "env-host"
    assert config["database"]["database"] == "env-db"
    assert config["database"]["raw_url"].endswith("sslmode=verify-full")


def test_paper_requires_secure_source_when_no_secret_or_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("TOJI_DATABASE_SECRET_NAME", raising=False)
    monkeypatch.delenv("AWS_DATABASE_SECRET_NAME", raising=False)

    with pytest.raises(RuntimeError, match="Secure database configuration is required"):
        ConfigLoader("PAPER", require_secure_database=True).load_configuration()


def test_paper_database_failure_is_fail_closed_without_sqlite(monkeypatch):
    from research_platform.persistence.postgres.connection import DatabaseConnection

    monkeypatch.delenv("TOJI_MODE", raising=False)
    monkeypatch.setenv("FORCE_DB_FALLBACK_CHECK", "true")
    connection = DatabaseConnection(
        {
            "host": "127.0.0.1",
            "port": 1,
            "dbname": "toji",
            "user": "toji",
            "password": "not-used",
            "_runtime_mode": "PAPER",
        }
    )

    with pytest.raises(RuntimeError, match="Fallback SQLite is disabled"):
        connection.initialize()

    assert connection.is_fallback is False


def test_dev_configuration_remains_local_without_aws(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("TOJI_DATABASE_SECRET_NAME", raising=False)
    monkeypatch.delenv("AWS_DATABASE_SECRET_NAME", raising=False)
    monkeypatch.setenv("TOJI_PROFILE", "DEV")

    config = ConfigLoader("DEV", require_secure_database=True).load_configuration()

    assert config["runtime"]["mode"] == "DEV"
    assert config["database"]["host"] == "localhost"


def test_configuration_bootloader_does_not_persist_before_database(monkeypatch):
    monkeypatch.setenv("TOJI_PROFILE", "DEV")
    persisted = []

    def fail_if_persisted(self, config):
        persisted.append(config)
        raise AssertionError("configuration persisted before Database registration")

    monkeypatch.setattr(ConfigRepository, "save_central_config", fail_if_persisted)
    config = ConfigurationBootloader().load_configuration()

    assert config["runtime"]["mode"] == "DEV"
    assert persisted == []


def test_platform_source_registers_database_before_plugin_discovery():
    from research_platform.platform import startup

    source = inspect.getsource(startup.PlatformStartupCoordinator.boot_platform)
    assert source.index("db_manager.connect()") < source.index('register_service("Database"')
    assert source.index('register_service("Database"') < source.index("discover_plugins")


def test_config_plugin_persists_after_database_registration(monkeypatch):
    registry = ServiceRegistry()
    registry.clear()
    registry.register_service("Database", SimpleNamespace(connection=object()))
    observed = []

    class FakeRepository:
        def save_parameter(self, key, value):
            observed.append((key, value))

    def get_repo(self):
        observed.append(("database_registered", registry.get_service("Database") is not None))
        return FakeRepository()

    monkeypatch.setattr(ConfigRepository, "_get_pg_repo", get_repo)
    monkeypatch.setenv("TOJI_PROFILE", "DEV")

    container = SimpleNamespace(
        register=lambda *args, **kwargs: None,
    )
    ConfigPlugin(container).initialize()

    assert observed
    assert observed[0] == ("database_registered", True)
    assert any(item[0] == "central_config" for item in observed if isinstance(item, tuple))
    registry.clear()
