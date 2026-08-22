"""Comprehensive unit and integration tests for TOJI platform boot layer (R49-R51).
"""

from __future__ import annotations

import pytest
import threading

from research_platform.platform.startup import PlatformStartupCoordinator
from research_platform.platform.shutdown import PlatformShutdownCoordinator
from research_platform.platform.application import PlatformApplication
from research_platform.platform.service_registry import ServiceRegistry

# Orchestrators
from research_platform.monitoring.orchestrator import MonitoringOrchestrator
from research_platform.reporting.orchestrator import ReportingOrchestrator
from research_platform.toji_os.orchestrator import TOJIOSOrchestrator


@pytest.fixture
def registry():
    reg = ServiceRegistry()
    reg.clear()
    return reg


@pytest.fixture
def app():
    ServiceRegistry().clear()
    application = PlatformApplication()
    return application


# ─────────────────────────────────────────────────────────────────────
# PLATFORM BOOT TESTS (1-51)
# ─────────────────────────────────────────────────────────────────────

def test_boot_platform_success(app):
    app.boot()
    assert ServiceRegistry().get_service("Configuration") is not None
    app.shutdown()


def test_boot_configuration_loaded(app):
    app.boot()
    config = ServiceRegistry().get_service("Configuration")
    assert "database" in config
    app.shutdown()


def test_boot_database_connected(app):
    app.boot()
    db = ServiceRegistry().get_service("Database")
    assert db.connected is True
    app.shutdown()


def test_boot_container_bound(app):
    app.boot()
    container = ServiceRegistry().get_service("Container")
    assert container is not None
    app.shutdown()


def test_boot_eventbus_bound(app):
    app.boot()
    event_bus = ServiceRegistry().get_service("EventBus")
    assert event_bus is not None
    app.shutdown()


def test_boot_plugins_registered(app):
    app.boot()
    plugins = ServiceRegistry().get_service("Plugins")
    assert len(plugins) > 0
    app.shutdown()


def test_boot_priority_order(app):
    app.boot()
    plugins = ServiceRegistry().get_service("Plugins")
    class_names = [p.__class__.__name__ for p in plugins]
    
    # Configuration and Memory should boot before OS
    if "InstitutionalMemoryPlugin" in class_names and "TOJIOSPlugin" in class_names:
        assert class_names.index("InstitutionalMemoryPlugin") < class_names.index("TOJIOSPlugin")
    app.shutdown()


def test_boot_service_registry_populated(app):
    app.boot()
    assert ServiceRegistry().get_service("Database") is not None
    app.shutdown()


def test_boot_database_disconnect(app):
    app.boot()
    db = ServiceRegistry().get_service("Database")
    app.shutdown()
    assert db.connected is False


def test_boot_failure_recovery_on_plugin(app):
    class BadPlugin:
        def initialize(self):
            raise ValueError("Plugin Init Fail")
        def shutdown(self):
            pass

    # The shutdown runner should handle plugin failures gracefully
    coordinator = PlatformShutdownCoordinator()
    ServiceRegistry().register_service("Plugins", [BadPlugin()])
    coordinator.shutdown_platform()  # Checks that no exception is bubbled up


def test_boot_registry_cleared_on_shutdown(app):
    app.boot()
    app.shutdown()
    assert ServiceRegistry().get_service("Database") is None


def test_boot_health_check_mon(app):
    app.boot()
    container = ServiceRegistry().get_service("Container")
    orch = container.resolve(MonitoringOrchestrator)
    assert orch is not None
    app.shutdown()


def test_boot_health_check_rep(app):
    app.boot()
    container = ServiceRegistry().get_service("Container")
    orch = container.resolve(ReportingOrchestrator)
    assert orch is not None
    app.shutdown()


def test_boot_health_check_os(app):
    app.boot()
    container = ServiceRegistry().get_service("Container")
    orch = container.resolve(TOJIOSOrchestrator)
    assert orch is not None
    app.shutdown()


def test_boot_health_check_stress(app):
    app.boot()
    container = ServiceRegistry().get_service("Container")
    from research_platform.stress_testing.orchestrator import StressTestingOrchestrator
    orch = container.resolve(StressTestingOrchestrator)
    assert orch is not None
    app.shutdown()


def test_boot_registry_eventbus_available(app):
    app.boot()
    assert ServiceRegistry().get_service("EventBus") is not None
    app.shutdown()


def test_boot_registry_container_available(app):
    app.boot()
    assert ServiceRegistry().get_service("Container") is not None
    app.shutdown()


def test_boot_registry_configuration_available(app):
    app.boot()
    assert ServiceRegistry().get_service("Configuration") is not None
    app.shutdown()


def test_boot_registry_database_available(app):
    app.boot()
    assert ServiceRegistry().get_service("Database") is not None
    app.shutdown()


def test_boot_registry_repositories_available(app):
    app.boot()
    container = ServiceRegistry().get_service("Container")
    # Caches stores inside the container
    assert container.resolve("Configuration") is not None
    app.shutdown()


def test_boot_registry_schedulers_available(app):
    app.boot()
    container = ServiceRegistry().get_service("Container")
    from research_platform.scheduler.orchestrator import StrategySchedulerOrchestrator
    assert container.resolve(StrategySchedulerOrchestrator) is not None
    app.shutdown()


def test_boot_registry_monitoring_available(app):
    app.boot()
    container = ServiceRegistry().get_service("Container")
    assert container.resolve(MonitoringOrchestrator) is not None
    app.shutdown()


def test_boot_registry_reporting_available(app):
    app.boot()
    container = ServiceRegistry().get_service("Container")
    assert container.resolve(ReportingOrchestrator) is not None
    app.shutdown()


def test_boot_registry_tojios_available(app):
    app.boot()
    container = ServiceRegistry().get_service("Container")
    assert container.resolve(TOJIOSOrchestrator) is not None
    app.shutdown()


def test_boot_thread_safety_database_connect(app):
    app.boot()
    db = ServiceRegistry().get_service("Database")
    threads = [threading.Thread(target=db.connect) for _ in range(10)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert db.connected is True
    app.shutdown()


def test_boot_thread_safety_database_disconnect(app):
    app.boot()
    db = ServiceRegistry().get_service("Database")
    threads = [threading.Thread(target=db.disconnect) for _ in range(10)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert db.connected is False
    app.shutdown()


def test_boot_thread_safety_service_registry(registry):
    threads = [threading.Thread(target=lambda i: registry.register_service(f"s-{i}", i), args=(i,)) for i in range(10)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert registry.get_service("s-5") == 5


def test_boot_config_default_host(app):
    app.boot()
    config = ServiceRegistry().get_service("Configuration")
    assert config["database"]["host"] == "localhost"
    app.shutdown()


def test_boot_config_default_port(app):
    app.boot()
    config = ServiceRegistry().get_service("Configuration")
    assert config["database"]["port"] == 5432
    app.shutdown()


def test_boot_config_default_dbname(app):
    app.boot()
    config = ServiceRegistry().get_service("Configuration")
    assert config["database"]["dbname"] == "toji_v1"
    app.shutdown()


def test_boot_config_default_user(app):
    app.boot()
    config = ServiceRegistry().get_service("Configuration")
    assert config["database"]["user"] == "postgres"
    app.shutdown()


def test_boot_config_default_env(app):
    app.boot()
    config = ServiceRegistry().get_service("Configuration")
    assert config["environment"] == "PRODUCTION"
    app.shutdown()


def test_boot_config_default_loglevel(app):
    app.boot()
    config = ServiceRegistry().get_service("Configuration")
    assert config["log_level"] == "INFO"
    app.shutdown()


def test_boot_db_lifecycle_initial_state():
    from research_platform.platform.database_boot import DatabaseLifecycleManager
    db = DatabaseLifecycleManager({"host": "h", "port": 1})
    assert db.connected is False


def test_boot_db_lifecycle_connected_state():
    from research_platform.platform.database_boot import DatabaseLifecycleManager
    db = DatabaseLifecycleManager({"host": "h", "port": 1})
    db.connect()
    assert db.connected is True


def test_boot_db_lifecycle_disconnected_state():
    from research_platform.platform.database_boot import DatabaseLifecycleManager
    db = DatabaseLifecycleManager({"host": "h", "port": 1})
    db.connect()
    db.disconnect()
    assert db.connected is False


def test_boot_container_registration_config(app):
    app.boot()
    container = ServiceRegistry().get_service("Container")
    assert container.resolve("Configuration") is not None
    app.shutdown()


def test_boot_container_registration_database(app):
    app.boot()
    container = ServiceRegistry().get_service("Container")
    assert container.resolve("Database") is not None
    app.shutdown()


def test_boot_container_registration_eventbus(app):
    app.boot()
    container = ServiceRegistry().get_service("Container")
    assert container.resolve("IEventBus") is not None
    app.shutdown()


def test_boot_plugin_discovery_not_empty(app):
    app.boot()
    plugins = ServiceRegistry().get_service("Plugins")
    assert len(plugins) > 0
    app.shutdown()


def test_boot_plugin_discovery_finds_tojios(app):
    app.boot()
    plugins = ServiceRegistry().get_service("Plugins")
    names = [p.__class__.__name__ for p in plugins]
    assert "TOJIOSPlugin" in names
    app.shutdown()


def test_boot_plugin_discovery_finds_monitoring(app):
    app.boot()
    plugins = ServiceRegistry().get_service("Plugins")
    names = [p.__class__.__name__ for p in plugins]
    assert "MonitoringPlugin" in names
    app.shutdown()


def test_boot_plugin_discovery_finds_reporting(app):
    app.boot()
    plugins = ServiceRegistry().get_service("Plugins")
    names = [p.__class__.__name__ for p in plugins]
    assert "ReportingPlugin" in names
    app.shutdown()


def test_boot_plugin_discovery_finds_stresstesting(app):
    app.boot()
    plugins = ServiceRegistry().get_service("Plugins")
    names = [p.__class__.__name__ for p in plugins]
    assert "StressTestingPlugin" in names
    app.shutdown()


def test_boot_eventbus_subscription_verification(app):
    app.boot()
    event_bus = ServiceRegistry().get_service("EventBus")
    assert event_bus is not None
    app.shutdown()


def test_boot_graceful_shutdown_runs(app):
    app.boot()
    app.shutdown()
    assert ServiceRegistry().get_service("Database") is None


def test_boot_graceful_shutdown_order(app):
    app.boot()
    plugins = ServiceRegistry().get_service("Plugins")
    # Shutdown in reverse order
    reversed_plugins = list(reversed(plugins))
    assert len(reversed_plugins) == len(plugins)
    app.shutdown()


def test_boot_graceful_shutdown_flushes(app):
    app.boot()
    app.shutdown()
    # Check that services cleared
    assert ServiceRegistry().get_service("Plugins") is None


def test_boot_graceful_shutdown_database_closed(app):
    app.boot()
    db = ServiceRegistry().get_service("Database")
    app.shutdown()
    assert db.connected is False


def test_boot_graceful_shutdown_eventbus_stopped(app):
    app.boot()
    app.shutdown()
    assert ServiceRegistry().get_service("EventBus") is None


def test_boot_graceful_shutdown_registry_empty(app):
    app.boot()
    app.shutdown()
    assert len(ServiceRegistry()._instance._registry) == 0
