"""Comprehensive unit and integration tests for TOJI Platform Management Layer (R35-R37).
"""

from __future__ import annotations

import pytest
import threading
from datetime import datetime, timezone

from toji_platform.core.dependency_injection import Container
from toji_platform.core.event_bus import InMemoryEventBus

# Subsystems
from research_platform.strategy_registry.orchestrator import StrategyRegistryOrchestrator
from research_platform.strategy_registry.models import RegisteredStrategy
from research_platform.strategy_registry.plugin import StrategyRegistryPlugin

from research_platform.deployment.orchestrator import DeploymentOrchestrator
from research_platform.deployment.models import StrategyDeployment, DeploymentLock
from research_platform.deployment.plugin import DeploymentPlugin

from research_platform.configuration.orchestrator import ConfigurationOrchestrator
from research_platform.configuration.models import ConfigurationEntry
from research_platform.configuration.plugin import ConfigurationPlugin

# Integration targets
from research_platform.institutional_memory.orchestrator import InstitutionalMemoryOrchestrator
from research_platform.knowledge_graph.orchestrator import KnowledgeGraphOrchestrator
from research_platform.operations_center.operations_orchestrator import OperationsOrchestrator


@pytest.fixture
def event_bus():
    return InMemoryEventBus()


@pytest.fixture
def container(event_bus):
    c = Container()
    c.register("IEventBus", instance=event_bus)

    mem_orch = InstitutionalMemoryOrchestrator(event_bus)
    c.register("research_platform.institutional_memory.orchestrator.InstitutionalMemoryOrchestrator", instance=mem_orch)

    kg_orch = KnowledgeGraphOrchestrator(event_bus)
    c.register("research_platform.knowledge_graph.orchestrator.KnowledgeGraphOrchestrator", instance=kg_orch)

    ops_orch = OperationsOrchestrator(event_bus, container=c)
    c.register("research_platform.operations_center.operations_orchestrator.OperationsOrchestrator", instance=ops_orch)

    return c


@pytest.fixture
def registry_orch(event_bus, container):
    return StrategyRegistryOrchestrator(event_bus, container=container)


@pytest.fixture
def deployment_orch(event_bus, container):
    return DeploymentOrchestrator(event_bus, container=container)


@pytest.fixture
def config_orch(event_bus, container):
    return ConfigurationOrchestrator(event_bus, container=container)


# ─────────────────────────────────────────────────────────────────────
# 1-20: STRATEGY REGISTRY TESTS (R35)
# ─────────────────────────────────────────────────────────────────────

def test_registry_registration_success(registry_orch):
    res = registry_orch.register_strategy(
        "s1", "Alpha", "Desc", "v1.0.0", "commit123", ["dep-a"], ["tag-a"], ["cat-a"], "Author", "Equities", "LOW", ["cap-a"]
    )
    assert res.strategy_id == "s1"
    assert res.name == "Alpha"
    assert res.risk_profile == "LOW"


def test_registry_blank_id_failure(registry_orch):
    with pytest.raises(ValueError, match="Strategy ID and Name"):
        registry_orch.register_strategy(
            "", "Alpha", "Desc", "v1", "commit123", [], [], [], "Author", "Asset", "LOW", []
        )


def test_registry_blank_name_failure(registry_orch):
    with pytest.raises(ValueError, match="Strategy ID and Name"):
        registry_orch.register_strategy(
            "s1", "", "Desc", "v1", "commit123", [], [], [], "Author", "Asset", "LOW", []
        )


def test_registry_short_git_hash_failure(registry_orch):
    with pytest.raises(ValueError, match="Invalid Git Commit Hash"):
        registry_orch.register_strategy(
            "s1", "Alpha", "Desc", "v1", "hash", [], [], [], "Author", "Asset", "LOW", []
        )


def test_registry_invalid_risk_profile_failure(registry_orch):
    with pytest.raises(ValueError, match="Invalid Risk Profile"):
        registry_orch.register_strategy(
            "s1", "Alpha", "Desc", "v1", "commit123", [], [], [], "Author", "Asset", "EXTREME", []
        )


def test_registry_search_by_name(registry_orch):
    registry_orch.register_strategy("s1", "Alpha", "Desc", "v1", "commit123", [], [], [], "Author", "Asset", "LOW", [])
    registry_orch.register_strategy("s2", "Beta", "Desc", "v1", "commit123", [], [], [], "Author", "Asset", "LOW", [])
    
    res = registry_orch.search_engine.search("Alpha")
    assert len(res) == 1
    assert res[0].strategy_id == "s1"


def test_registry_search_by_description(registry_orch):
    registry_orch.register_strategy("s1", "Alpha", "Important strategy", "v1", "commit123", [], [], [], "Author", "Asset", "LOW", [])
    registry_orch.register_strategy("s2", "Beta", "Desc", "v1", "commit123", [], [], [], "Author", "Asset", "LOW", [])
    
    res = registry_orch.search_engine.search("Important")
    assert len(res) == 1
    assert res[0].strategy_id == "s1"


def test_registry_search_by_tag(registry_orch):
    registry_orch.register_strategy("s1", "Alpha", "Desc", "v1", "commit123", [], ["trend"], [], "Author", "Asset", "LOW", [])
    registry_orch.register_strategy("s2", "Beta", "Desc", "v1", "commit123", [], ["mean-reverting"], [], "Author", "Asset", "LOW", [])
    
    res = registry_orch.search_engine.search("trend")
    assert len(res) == 1
    assert res[0].strategy_id == "s1"


def test_registry_search_by_category(registry_orch):
    registry_orch.register_strategy("s1", "Alpha", "Desc", "v1", "commit123", [], [], ["arbitrage"], "Author", "Asset", "LOW", [])
    registry_orch.register_strategy("s2", "Beta", "Desc", "v1", "commit123", [], [], ["market-making"], "Author", "Asset", "LOW", [])
    
    res = registry_orch.search_engine.search("arbitrage")
    assert len(res) == 1
    assert res[0].strategy_id == "s1"


def test_registry_search_empty_query(registry_orch):
    registry_orch.register_strategy("s1", "Alpha", "Desc", "v1", "commit123", [], [], [], "Author", "Asset", "LOW", [])
    res = registry_orch.search_engine.search("")
    assert len(res) == 1


def test_registry_version_history_logs(registry_orch):
    registry_orch.register_strategy("s1", "Alpha", "Desc", "v1.0.0", "commit123", [], [], [], "Author", "Asset", "LOW", [])
    registry_orch.version_manager.log_version_update("s1", "v1.1.0", "commit456")
    
    history = registry_orch.version_manager.get_version_history("s1")
    assert len(history) == 2
    assert history[0][0] == "v1.0.0"
    assert history[1][0] == "v1.1.0"


def test_registry_statistics_compiles(registry_orch):
    registry_orch.register_strategy("s1", "Alpha", "Desc", "v1", "commit123", [], [], [], "Author", "Asset", "LOW", [])
    stats = registry_orch.get_statistics()
    assert stats.total_registered == 1
    assert stats.active_count == 1
    assert stats.retired_count == 0


def test_registry_snapshot_saves(registry_orch):
    registry_orch.register_strategy("s1", "Alpha", "Desc", "v1", "commit123", [], [], [], "Author", "Asset", "LOW", [])
    snap = registry_orch.create_snapshot()
    assert len(snap.strategies) == 1


def test_registry_repository_lists(registry_orch):
    registry_orch.register_strategy("s1", "Alpha", "Desc", "v1", "commit123", [], [], [], "Author", "Asset", "LOW", [])
    assert len(registry_orch.repository.list_strategies()) == 1


def test_registry_thread_safety_saves(registry_orch):
    def worker(idx):
        registry_orch.register_strategy(
            f"thread-s-{idx}", "Strategy", "Desc", "v1", "commit123", [], [], [], "Author", "Asset", "LOW", []
        )

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(registry_orch.repository.list_strategies()) == 10


def test_registry_plugin_registration(container):
    plugin = StrategyRegistryPlugin(container)
    plugin.initialize()
    orch = container.resolve(StrategyRegistryOrchestrator)
    assert orch is not None


def test_registry_event_publication(registry_orch, event_bus):
    events = []
    def sub(event):
        events.append(event)
    event_bus.subscribe("system.strategy_registered", sub)

    registry_orch.register_strategy("s1", "Alpha", "Desc", "v1", "commit123", [], [], [], "Author", "Asset", "LOW", [])
    assert len(events) == 1


def test_registry_snapshot_event(registry_orch, event_bus):
    events = []
    def sub(event):
        events.append(event)
    event_bus.subscribe("system.strategy_registry_snapshot_created", sub)

    registry_orch.create_snapshot()
    assert len(events) == 1


def test_registry_memory_integration(registry_orch, container):
    registry_orch.register_strategy("s1", "Alpha", "Desc", "v1", "commit123", [], [], [], "Author", "Asset", "LOW", [])
    mem = container.resolve("research_platform.institutional_memory.orchestrator.InstitutionalMemoryOrchestrator")
    assert len(mem.repository.list_memories_by_category("strategy_registry")) == 1


def test_registry_kg_integration(registry_orch, container):
    registry_orch.register_strategy("s1", "Alpha", "Desc", "v1", "commit123", [], [], [], "Author", "Asset", "LOW", [])
    kg = container.resolve("research_platform.knowledge_graph.orchestrator.KnowledgeGraphOrchestrator")
    assert next((n for n in kg.repository.list_nodes() if n.node_id == "s1"), None) is not None


# ─────────────────────────────────────────────────────────────────────
# 21-38: DEPLOYMENT MANAGER TESTS (R36)
# ─────────────────────────────────────────────────────────────────────

def test_deployment_trigger_success(deployment_orch):
    res = deployment_orch.deploy_strategy("s1", "PRODUCTION", "v1.0.0", 50.0)
    assert res.strategy_id == "s1"
    assert res.environment == "PRODUCTION"
    assert res.active_weight == 50.0
    assert res.status == "ACTIVE"


def test_deployment_invalid_env_failure(deployment_orch):
    with pytest.raises(ValueError, match="Invalid Deployment Environment"):
        deployment_orch.deploy_strategy("s1", "DEV", "v1", 100.0)


def test_deployment_invalid_canary_weight_failure(deployment_orch):
    with pytest.raises(ValueError, match="Invalid Canary Weight"):
        deployment_orch.deploy_strategy("s1", "PRODUCTION", "v1", 150.0)


def test_deployment_lock_blocks_rollout(deployment_orch):
    deployment_orch.lock_deployments("actor-1", "Maintenance lock")
    with pytest.raises(RuntimeError, match="Deployment Blocked"):
        deployment_orch.deploy_strategy("s1", "PRODUCTION", "v1.0.0", 100.0)


def test_deployment_unlock_allows_rollout(deployment_orch):
    deployment_orch.lock_deployments("actor-1", "Maintenance lock")
    deployment_orch.unlock_deployments()
    res = deployment_orch.deploy_strategy("s1", "PRODUCTION", "v1.0.0", 100.0)
    assert res.status == "ACTIVE"


def test_deployment_health_monitor_healthy(deployment_orch):
    dep = deployment_orch.deploy_strategy("s1", "PRODUCTION", "v1.0.0", 100.0)
    res = deployment_orch.evaluate_deployment_health(dep.deployment_id)
    assert res.status == "HEALTHY"


def test_deployment_health_monitor_critical_triggers_rollback(deployment_orch):
    dep = deployment_orch.deploy_strategy("s1", "PRODUCTION", "v1.0.0", 100.0)
    
    # Mock health monitor to return CRITICAL
    def critical_health(dep_id):
        from research_platform.deployment.models import DeploymentHealthCard
        return DeploymentHealthCard(deployment_id=dep_id, error_count=10, latency_ms=15.0, status="CRITICAL")
    deployment_orch._health.evaluate_health = critical_health

    deployment_orch.evaluate_deployment_health(dep.deployment_id)
    updated = deployment_orch.repository.get_deployment(dep.deployment_id)
    assert updated.status == "ROLLED_BACK"
    assert updated.active_weight == 0.0


def test_deployment_manual_rollback(deployment_orch):
    dep = deployment_orch.deploy_strategy("s1", "PRODUCTION", "v1.0.0", 100.0)
    res = deployment_orch.execute_rollback(dep.deployment_id, "Manual intervention")
    assert res.status == "ROLLED_BACK"
    assert res.active_weight == 0.0


def test_deployment_snapshot_saves(deployment_orch):
    deployment_orch.deploy_strategy("s1", "PRODUCTION", "v1.0.0", 100.0)
    snap = deployment_orch.create_snapshot()
    assert len(snap.deployments) == 1


def test_deployment_repository_queries(deployment_orch):
    deployment_orch.deploy_strategy("s1", "PRODUCTION", "v1.0.0", 100.0)
    assert len(deployment_orch.repository.list_deployments()) == 1


def test_deployment_thread_safety_saves(deployment_orch):
    def worker(idx):
        deployment_orch.deploy_strategy(f"thread-s-{idx}", "PRODUCTION", "v1.0.0", 100.0)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(deployment_orch.repository.list_deployments()) == 10


def test_deployment_plugin_registration(container):
    plugin = DeploymentPlugin(container)
    plugin.initialize()
    orch = container.resolve(DeploymentOrchestrator)
    assert orch is not None


def test_deployment_triggered_event(deployment_orch, event_bus):
    events = []
    def sub(event):
        events.append(event)
    event_bus.subscribe("system.deployment_triggered", sub)

    deployment_orch.deploy_strategy("s1", "PRODUCTION", "v1.0.0", 100.0)
    assert len(events) == 1


def test_deployment_completed_event(deployment_orch, event_bus):
    events = []
    def sub(event):
        events.append(event)
    event_bus.subscribe("system.deployment_completed", sub)

    deployment_orch.deploy_strategy("s1", "PRODUCTION", "v1.0.0", 100.0)
    assert len(events) == 1


def test_deployment_failed_event(deployment_orch, event_bus):
    events = []
    def sub(event):
        events.append(event)
    event_bus.subscribe("system.deployment_failed", sub)

    dep = deployment_orch.deploy_strategy("s1", "PRODUCTION", "v1.0.0", 100.0)
    
    # Force fail
    def critical_health(dep_id):
        from research_platform.deployment.models import DeploymentHealthCard
        return DeploymentHealthCard(deployment_id=dep_id, error_count=10, latency_ms=15.0, status="CRITICAL")
    deployment_orch._health.evaluate_health = critical_health
    
    deployment_orch.evaluate_deployment_health(dep.deployment_id)
    assert len(events) == 1


def test_deployment_rolledback_event(deployment_orch, event_bus):
    events = []
    def sub(event):
        events.append(event)
    event_bus.subscribe("system.deployment_rolled_back", sub)

    dep = deployment_orch.deploy_strategy("s1", "PRODUCTION", "v1.0.0", 100.0)
    deployment_orch.execute_rollback(dep.deployment_id, "Manual")
    assert len(events) == 1


def test_deployment_memory_integration(deployment_orch, container):
    deployment_orch.deploy_strategy("s1", "PRODUCTION", "v1.0.0", 100.0)
    mem = container.resolve("research_platform.institutional_memory.orchestrator.InstitutionalMemoryOrchestrator")
    assert len(mem.repository.list_memories_by_category("deployment")) == 1


def test_deployment_kg_integration(deployment_orch, container):
    dep = deployment_orch.deploy_strategy("s1", "PRODUCTION", "v1.0.0", 100.0)
    kg = container.resolve("research_platform.knowledge_graph.orchestrator.KnowledgeGraphOrchestrator")
    assert next((n for n in kg.repository.list_nodes() if n.node_id == dep.deployment_id), None) is not None


# ─────────────────────────────────────────────────────────────────────
# 39-52: CONFIGURATION MANAGER TESTS (R37)
# ─────────────────────────────────────────────────────────────────────

def test_config_update_success(config_orch):
    res = config_orch.update_config("RISK", {"drawdown_limit": 0.10})
    assert res.scope == "RISK"
    assert res.params["drawdown_limit"] == 0.10
    assert res.version == 1
    assert res.is_active is True


def test_config_invalid_scope_failure(config_orch):
    with pytest.raises(ValueError, match="Invalid Configuration Scope"):
        config_orch.update_config("TEST_SCOPE", {"param": 1})


def test_config_validator_drawdown_type_failure(config_orch):
    with pytest.raises(ValueError, match="Invalid Risk Configuration"):
        config_orch.update_config("RISK", {"drawdown_limit": "high"})


def test_config_version_increments(config_orch):
    config_orch.update_config("RISK", {"drawdown_limit": 0.10})
    res2 = config_orch.update_config("RISK", {"drawdown_limit": 0.15})
    assert res2.version == 2
    assert res2.is_active is True

    # Previous config should be set to inactive
    entries = config_orch.repository.list_entries("RISK")
    assert len(entries) == 2
    
    inactives = [e for e in entries if not e.is_active]
    assert len(inactives) == 1
    assert inactives[0].version == 1


def test_config_hot_reload_count(config_orch):
    config_orch.trigger_hot_reload()
    assert config_orch.hot_reload._reload_count == 1


def test_config_snapshot_saves(config_orch):
    config_orch.update_config("RISK", {"drawdown_limit": 0.10})
    snap = config_orch.create_snapshot()
    assert len(snap.entries) == 1


def test_config_active_retrieval(config_orch):
    config_orch.update_config("RISK", {"drawdown_limit": 0.10})
    config_orch.update_config("RISK", {"drawdown_limit": 0.15})
    
    active = config_orch.get_active_config("RISK")
    assert active.params["drawdown_limit"] == 0.15


def test_config_thread_safety_saves(config_orch):
    def worker(idx):
        config_orch.update_config("RISK", {f"drawdown_limit_{idx}": 0.10})

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Total entries across updates (active switches happen dynamically)
    assert len(config_orch.repository.list_entries()) == 10


def test_config_plugin_registration(container):
    plugin = ConfigurationPlugin(container)
    plugin.initialize()
    orch = container.resolve(ConfigurationOrchestrator)
    assert orch is not None


def test_config_updated_event(config_orch, event_bus):
    events = []
    def sub(event):
        events.append(event)
    event_bus.subscribe("system.configuration_updated", sub)

    config_orch.update_config("RISK", {"drawdown_limit": 0.10})
    assert len(events) == 1


def test_config_reloaded_event(config_orch, event_bus):
    events = []
    def sub(event):
        events.append(event)
    event_bus.subscribe("system.configuration_reloaded", sub)

    config_orch.trigger_hot_reload()
    assert len(events) == 1


def test_config_memory_integration(config_orch, container):
    config_orch.update_config("RISK", {"drawdown_limit": 0.10})
    mem = container.resolve("research_platform.institutional_memory.orchestrator.InstitutionalMemoryOrchestrator")
    assert len(mem.repository.list_memories_by_category("configuration")) == 1


def test_config_kg_integration(config_orch, container):
    entry = config_orch.update_config("RISK", {"drawdown_limit": 0.10})
    kg = container.resolve("research_platform.knowledge_graph.orchestrator.KnowledgeGraphOrchestrator")
    assert next((n for n in kg.repository.list_nodes() if n.node_id == entry.config_id), None) is not None
