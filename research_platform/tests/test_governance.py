"""Unit and integration tests for the TOJI Institutional Governance & Audit Platform.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone

from toji_platform.core.dependency_injection import Container
from toji_platform.core.event_bus import InMemoryEventBus

from research_platform.governance.models import (
    AccessRole,
    ComplianceRule,
    DeploymentApproval,
    DigitalSignature,
    GovernanceAuditRecord,
)
from research_platform.governance.orchestrator import GovernanceOrchestrator
from research_platform.governance.evaluator import PolicyEvaluator
from research_platform.governance.signature import SignatureVerifier

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
    return GovernanceOrchestrator(event_bus, container=container)


def test_compliance_policy_evaluation():
    """Verify standard compliance rules evaluation against metrics."""
    evaluator = PolicyEvaluator()

    rules = [
        ComplianceRule(rule_id="r1", name="Sharpe Limit", description="desc", criterion_key="sharpe", operator=">=", threshold=1.0),
        ComplianceRule(rule_id="r2", name="Drawdown Limit", description="desc", criterion_key="drawdown", operator="<=", threshold=0.15),
    ]

    # 1. Rules pass
    metrics_pass = {"sharpe": 1.5, "drawdown": 0.08}
    res_pass = evaluator.evaluate_policies(rules, metrics_pass)
    assert len(res_pass) == 2
    assert all(r.passed for r in res_pass)

    # 2. Rule breaches
    metrics_fail = {"sharpe": 0.8, "drawdown": 0.20}
    res_fail = evaluator.evaluate_policies(rules, metrics_fail)
    assert len(res_fail) == 2
    assert all(not r.passed for r in res_fail)


def test_signature_verification():
    """Verify cryptographic signature verification conditions."""
    verifier = SignatureVerifier()

    sig = DigitalSignature(author="risk_officer", public_key_hash="hash-1", signature="sig-authorized-token")
    assert verifier.verify_signature(sig, "deploy-123") is True

    sig_invalid = DigitalSignature(author="researcher", public_key_hash="hash-2", signature="invalid")
    assert verifier.verify_signature(sig_invalid, "deploy-123") is False


def test_block_linked_audit_trail_chain(orchestrator):
    """Verify that governance audit record entries form a hash-linked block chain."""
    r1 = orchestrator.audit_action("a1", "RULE_REGISTERED", AccessRole.COMPLIANCE_OFFICER)
    assert r1.previous_block_hash == "genesis"

    # Second block points back to first block hash
    r2 = orchestrator.audit_action("a2", "POLICY_EVALUATED", AccessRole.RISK_MANAGER)
    assert r2.previous_block_hash == r1.block_hash

    # Verification: chain integrity is linked
    history = orchestrator.repository.list_audit_history()
    assert len(history) == 2
    assert history[0].block_hash == history[1].previous_block_hash


def test_orchestrator_governance_integrations(orchestrator, container):
    """Verify orchestrator triggers Event Bus, memory registries, and Knowledge Graph node links."""
    # 1. Register compliance rule
    orchestrator.register_rule(
        rule_id="rule-sharpe",
        name="Sharpe limit",
        description="Min Sharpe is 1.0",
        criterion_key="sharpe",
        operator=">=",
        threshold=1.0
    )

    # 2. Create deployment approval
    app = orchestrator.create_deployment_approval("app-123", "deploy-123", {"sharpe": 1.5})
    assert app.status == "APPROVED"

    # 3. Verify Memory logging
    mem_orch = container.resolve("research_platform.institutional_memory.orchestrator.InstitutionalMemoryOrchestrator")
    mems = mem_orch.repository.list_memories_by_category("deployment_approvals")
    assert len(mems) == 1
    assert mems[0].approval_id == "app-123"

    # 4. Verify Knowledge Graph
    kg_orch = container.resolve("research_platform.knowledge_graph.orchestrator.KnowledgeGraphOrchestrator")
    nodes = kg_orch.repository.list_nodes()
    node_ids = [n.node_id for n in nodes]
    assert "app-123" in node_ids
