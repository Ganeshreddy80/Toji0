"""Unit and integration tests for the TOJI Institutional End-to-End System Validation Framework.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone

from toji_platform.core.dependency_injection import Container
from toji_platform.core.event_bus import InMemoryEventBus

from research_platform.system_validation.models import ValidationSeverity
from research_platform.system_validation.validation_orchestrator import ValidationOrchestrator
from research_platform.system_validation.dependency_validator import DependencyValidator
from research_platform.system_validation.repository_validator import RepositoryValidator
from research_platform.system_validation.event_bus_validator import EventBusValidator
from research_platform.system_validation.performance_snapshot import PerformanceSnapshot
from research_platform.system_validation.certification import CertificationEngine

# Integration components
from research_platform.institutional_memory.orchestrator import InstitutionalMemoryOrchestrator
from research_platform.knowledge_graph.orchestrator import KnowledgeGraphOrchestrator


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

    # Dummy mappings to satisfy remaining validators checks
    class DummyService:
        pass

    c.register("research_platform.market_regime.plugin.MarketRegimePlugin", instance=DummyService())
    c.register("research_platform.portfolio_optimizer.plugin.PortfolioOptimizerPlugin", instance=DummyService())
    c.register("research_platform.research_intelligence.plugin.ResearchIntelligencePlugin", instance=DummyService())
    c.register("research_platform.workflow_orchestration.plugin.WorkflowOrchestratorPlugin", instance=DummyService())
    c.register("research_platform.experiment_management.plugin.ExperimentManagementPlugin", instance=DummyService())
    c.register("research_platform.multi_agent.plugin.MultiAgentPlugin", instance=DummyService())
    c.register("research_platform.governance.plugin.GovernancePlugin", instance=DummyService())
    c.register("research_platform.simulation.plugin.SimulationPlugin", instance=DummyService())

    c.register("WorkflowOrchestrator", instance=DummyService())
    c.register("AIIntelligenceOrchestrator", instance=DummyService())
    c.register("RiskManagementOrchestrator", instance=DummyService())
    c.register("ExecutionEngineOrchestrator", instance=DummyService())
    c.register("SimulationOrchestrator", instance=DummyService())
    c.register("ObservabilityOrchestrator", instance=DummyService())
    c.register("MarketRegimeOrchestrator", instance=DummyService())
    c.register("StrategyLifecycleOrchestrator", instance=DummyService())

    return c


@pytest.fixture
def orchestrator(event_bus, container):
    return ValidationOrchestrator(event_bus, container=container)


def test_dependency_validator_checks(container):
    """Verify DependencyValidator correctly audits registrations in container."""
    val = DependencyValidator()
    health = val.validate(container)
    assert health.name == "Dependency Injection"
    # Verification: DI contains all targeted engines registrations
    assert len(health.checks) == 3
    assert all(c.passed for c in health.checks)
    assert health.score == 100.0


def test_repository_validator_locks(container):
    """Verify RepositoryValidator checks locking primitives on resolved orchestrators."""
    val = RepositoryValidator()
    health = val.validate(container)
    assert health.name == "Repositories"
    # Both Institutional Memory and Knowledge Graph orchestrators have locking repositories
    assert all(c.passed for c in health.checks)
    assert health.score == 100.0


def test_event_bus_validator_contracts(container):
    """Verify EventBusValidator checks publish and subscribe contracts."""
    val = EventBusValidator()
    health = val.validate(container)
    assert health.name == "Event Bus"
    assert health.checks[0].passed is True
    assert health.score == 100.0


def test_performance_snapshot_measurement():
    """Verify snapshot accurately captures time elapsed and memory allocations."""
    import time
    start = time.perf_counter()
    time.sleep(0.01)
    metrics = PerformanceSnapshot.capture(start)
    assert metrics.validation_duration >= 0.01
    assert metrics.memory_usage_mb > 0.0


def test_certification_card_score_compilation(container):
    """Verify CertificationEngine scores calculations and signs SHA256 hashes."""
    engine = CertificationEngine()
    
    val_dep = DependencyValidator()
    val_repo = RepositoryValidator()
    
    h1 = val_dep.validate(container)
    h2 = val_repo.validate(container)
    
    cert = engine.certify([h1, h2])
    assert cert.overall_score == 100.0
    assert cert.status == "PASSED"
    assert len(cert.block_hash) == 64


def test_orchestrator_complete_system_certification(orchestrator, container):
    """Verify orchestrator runs all 15 validators, logs results, and registers memory/graphs."""
    cert = orchestrator.execute_validation_suite()
    assert cert.status == "PASSED"
    assert cert.overall_score == 100.0

    # 1. Verify health cards saved in repository
    cards = orchestrator.repository.list_health_cards()
    assert len(cards) == 15  # All 15 validators executed

    # 2. Verify Memory Ingestion
    mem_orch = container.resolve("research_platform.institutional_memory.orchestrator.InstitutionalMemoryOrchestrator")
    mems = mem_orch.repository.list_memories_by_category("system_certifications")
    assert len(mems) == 1
    assert mems[0].block_hash == cert.block_hash
