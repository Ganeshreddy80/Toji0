"""Unit and integration tests for the TOJI Institutional Workflow Orchestration Engine.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone

from toji_platform.core.dependency_injection import Container
from toji_platform.core.event_bus import InMemoryEventBus

from research_platform.workflow_orchestration.models import (
    WorkflowInstance,
    WorkflowStatus,
    WorkflowStepName
)
from research_platform.workflow_orchestration.orchestrator import WorkflowOrchestrator
from research_platform.workflow_orchestration.engine import WorkflowEngine

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
    return WorkflowOrchestrator(event_bus, container=container)


def test_sequential_workflow_steps_automatic_execution(orchestrator):
    """Verify workflow runs automatic steps (Research -> Backtest -> Walk Forward -> Paper Trading) sequentially."""
    instance = orchestrator.create_workflow_instance("wf-1", "strat_alpha")
    assert instance.status == WorkflowStatus.PENDING
    assert instance.current_step_index == 0

    # 1. Advance Research
    instance = orchestrator.advance_workflow("wf-1")
    assert instance.steps[0].status == WorkflowStatus.COMPLETED
    assert instance.current_step_index == 1

    # 2. Advance Backtest
    instance = orchestrator.advance_workflow("wf-1")
    assert instance.steps[1].status == WorkflowStatus.COMPLETED
    assert instance.current_step_index == 2

    # 3. Advance Walk Forward
    instance = orchestrator.advance_workflow("wf-1")
    assert instance.steps[2].status == WorkflowStatus.COMPLETED
    assert instance.current_step_index == 3

    # 4. Advance Paper Trading
    instance = orchestrator.advance_workflow("wf-1")
    assert instance.steps[3].status == WorkflowStatus.COMPLETED
    assert instance.current_step_index == 4


def test_governance_pauses_and_resumptions(orchestrator):
    """Verify workflow pauses at Risk Review and resumes only when approval is submitted."""
    instance = orchestrator.create_workflow_instance("wf-gov", "strat_alpha")

    # Advance through automatic steps
    for _ in range(4):
        instance = orchestrator.advance_workflow("wf-gov")

    assert instance.current_step_index == 4
    assert instance.steps[4].name == WorkflowStepName.RISK_REVIEW

    # Risk Review execution should cause PAUSED state
    instance = orchestrator.advance_workflow("wf-gov")
    assert instance.status == WorkflowStatus.PAUSED
    assert instance.steps[4].status == WorkflowStatus.PAUSED

    # Submit approval to resume
    instance = orchestrator.approve_step("wf-gov", approver="RISK_SYSTEM", signature="sig-123", approved=True)
    
    # Verify paused step completed and workflow resumed to next step index 5
    assert instance.steps[4].status == WorkflowStatus.COMPLETED
    assert instance.current_step_index == 5
    # The submit_approval auto-executes the next step.
    # Step 5 is AI_REVIEW (another governance step) which will immediately pause again.
    assert instance.status == WorkflowStatus.PAUSED
    assert instance.steps[5].status == WorkflowStatus.PAUSED


def test_step_failure_and_max_retries(orchestrator):
    """Verify that automated steps retry on failure and fail permanently when max retries are hit."""
    # Set strategy_id to fail at backtest
    instance = orchestrator.create_workflow_instance("wf-fail", "strat_fail_at_backtest")
    
    # 1. Research succeeds
    instance = orchestrator.advance_workflow("wf-fail")
    assert instance.current_step_index == 1

    # 2. Backtest is index 1. Execute backtest.
    # First attempt: fails, sets status to PENDING, retry count = 1
    instance = orchestrator.advance_workflow("wf-fail")
    assert instance.steps[1].status == WorkflowStatus.PENDING
    assert instance.steps[1].retries == 1

    # Second attempt: fails, retry count = 2
    instance = orchestrator.advance_workflow("wf-fail")
    assert instance.steps[1].status == WorkflowStatus.PENDING
    assert instance.steps[1].retries == 2

    # Third attempt: fails, hit max_retries (3), workflow and step status becomes FAILED
    instance = orchestrator.advance_workflow("wf-fail")
    assert instance.steps[1].status == WorkflowStatus.FAILED
    assert instance.status == WorkflowStatus.FAILED


def test_workflow_rollback_resets_subsequent_steps(orchestrator):
    """Verify rolling back to a previous completed step resets all steps after it to PENDING."""
    instance = orchestrator.create_workflow_instance("wf-roll", "strat_alpha")

    # Advance through Research (0) and Backtest (1)
    instance = orchestrator.advance_workflow("wf-roll")
    instance = orchestrator.advance_workflow("wf-roll")
    assert instance.current_step_index == 2
    assert instance.steps[0].status == WorkflowStatus.COMPLETED
    assert instance.steps[1].status == WorkflowStatus.COMPLETED

    # Rollback to Research (index 0)
    instance = orchestrator.rollback_workflow("wf-roll", WorkflowStepName.RESEARCH)
    assert instance.current_step_index == 0
    assert instance.steps[0].status == WorkflowStatus.PENDING
    assert instance.steps[1].status == WorkflowStatus.PENDING


def test_workflow_visualizer_mermaid_diagram(orchestrator):
    """Verify Mermaid string render formats."""
    instance = orchestrator.create_workflow_instance("wf-vis", "strat_alpha")
    
    # Run a step
    instance = orchestrator.advance_workflow("wf-vis")
    
    mermaid_str = orchestrator.visualize_workflow("wf-vis")
    assert "graph LR" in mermaid_str
    assert "RESEARCH --> BACKTEST" in mermaid_str
    # Completed step has green color fill
    assert "style RESEARCH fill:#85e3b2" in mermaid_str


def test_orchestrator_workflow_integration(orchestrator, container):
    """Verify orchestrator updates Event Bus, Memory, and Knowledge Graph."""
    instance = orchestrator.create_workflow_instance("wf-int", "strat_alpha")

    # 1. Verify Memory Ingestion
    mem_orch = container.resolve("research_platform.institutional_memory.orchestrator.InstitutionalMemoryOrchestrator")
    mems = mem_orch.repository.list_memories_by_category("workflow_instances")
    assert len(mems) == 1
    assert mems[0].instance_id == "wf-int"

    # 2. Verify Knowledge Graph nodes and links
    kg_orch = container.resolve("research_platform.knowledge_graph.orchestrator.KnowledgeGraphOrchestrator")
    nodes = kg_orch.repository.list_nodes()
    node_ids = [n.node_id for n in nodes]
    assert "wf-int" in node_ids
    assert "strat_alpha" in node_ids

    # uses link exists
    edges = kg_orch.repository.list_edges()
    edge_types = [e.relationship_type for e in edges]
    assert "references" in edge_types
