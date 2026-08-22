"""Unit and integration tests for the TOJI Institutional Experiment Management Platform.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone

from toji_platform.core.dependency_injection import Container
from toji_platform.core.event_bus import InMemoryEventBus

from research_platform.experiment_management.models import (
    ExperimentComparison,
    ExperimentRecord,
    ReproducibilityCheck,
)
from research_platform.experiment_management.orchestrator import ExperimentManagementOrchestrator
from research_platform.experiment_management.replay import ExperimentReplayer
from research_platform.experiment_management.comparison import ExperimentComparer

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

    return c


@pytest.fixture
def orchestrator(event_bus, container):
    return ExperimentManagementOrchestrator(event_bus, container=container)


def test_experiment_reproducibility_validation():
    """Verify that replayer detects deviations in outputs or code hashes."""
    replayer = ExperimentReplayer()

    orig = ExperimentRecord(
        experiment_id="exp-1",
        description="original test",
        dataset_hash="hash-123",
        parameters={"lookback": 20},
        metrics={"sharpe": 1.5, "drawdown": 0.08},
        code_hash="code-abc"
    )

    # 1. Exact match
    check_ok = replayer.replay_experiment(orig, {"sharpe": 1.5, "drawdown": 0.08}, "code-abc")
    assert check_ok.matched is True

    # 2. Code hash deviation
    check_code_fail = replayer.replay_experiment(orig, {"sharpe": 1.5, "drawdown": 0.08}, "code-xyz")
    assert check_code_fail.matched is False

    # 3. Metric value deviation
    check_metric_fail = replayer.replay_experiment(orig, {"sharpe": 1.2, "drawdown": 0.08}, "code-abc")
    assert check_metric_fail.matched is False


def test_experiment_diff_comparison():
    """Verify comparing parameters and compiling difference logs."""
    comparer = ExperimentComparer()

    rec1 = ExperimentRecord(
        experiment_id="exp-1",
        description="run 1",
        dataset_hash="hash-123",
        parameters={"lookback": 20, "learning_rate": 0.01},
        metrics={"sharpe": 1.5},
        code_hash="code-abc"
    )

    rec2 = ExperimentRecord(
        experiment_id="exp-2",
        description="run 2",
        dataset_hash="hash-123",
        parameters={"lookback": 30, "learning_rate": 0.01},
        metrics={"sharpe": 1.8},
        code_hash="code-abc"
    )

    comp = comparer.compare_experiments([rec1, rec2])
    assert comp.compared_ids == ["exp-1", "exp-2"]
    
    # lookback differs, learning_rate is identical
    assert "lookback" in comp.parameter_diffs
    assert "learning_rate" not in comp.parameter_diffs
    assert comp.parameter_diffs["lookback"]["exp-1"] == 20
    assert comp.parameter_diffs["lookback"]["exp-2"] == 30


def test_orchestrator_logging_and_replays(orchestrator, container):
    """Verify orchestrator registers, logs to Memory and updates Knowledge Graph links."""
    # 1. Log experiment
    record = orchestrator.log_experiment(
        experiment_id="exp-alpha",
        description="momentum model tests",
        dataset_hash="dataset-h1",
        parameters={"lookback": 20},
        feature_versions={"close": "v1"},
        metrics={"sharpe": 1.4},
        artifacts=["file:///path/to/chart.png"],
        code_hash="git-h1"
    )
    assert record.status == "LOGGED"

    # 2. Verify Memory logging
    mem_orch = container.resolve("research_platform.institutional_memory.orchestrator.InstitutionalMemoryOrchestrator")
    mems = mem_orch.repository.list_memories_by_category("experiment_records")
    assert len(mems) == 1
    assert mems[0].experiment_id == "exp-alpha"

    # 3. Verify Knowledge Graph
    kg_orch = container.resolve("research_platform.knowledge_graph.orchestrator.KnowledgeGraphOrchestrator")
    nodes = kg_orch.repository.list_nodes()
    node_ids = [n.node_id for n in nodes]
    assert "exp-alpha" in node_ids

    # 4. Verify Replay
    check = orchestrator.verify_reproducibility("exp-alpha", {"sharpe": 1.4}, "git-h1")
    assert check.matched is True
    
    # Check node links updated
    nodes_updated = kg_orch.repository.list_nodes()
    updated_ids = [n.node_id for n in nodes_updated]
    assert f"check-{check.check_id}" in updated_ids
    
    edges = kg_orch.repository.list_edges()
    edge_types = [e.relationship_type for e in edges]
    assert "references" in edge_types
