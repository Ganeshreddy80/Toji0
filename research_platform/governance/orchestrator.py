"""Governance and audit orchestrator coordinating compliance policies, digital signatures, and block-linked audit chains.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from toji_platform.core.event_bus import IEventBus

from research_platform.governance.interfaces import IGovernanceOrchestrator
from research_platform.governance.models import (
    AccessRole,
    ComplianceRule,
    DeploymentApproval,
    DigitalSignature,
    GovernanceAuditRecord,
    PolicyEvaluationResult,
)
from research_platform.governance.repository import GovernanceRepository
from research_platform.governance.evaluator import PolicyEvaluator
from research_platform.governance.signature import SignatureVerifier
from research_platform.governance.events import (
    AuditLogged,
    DeploymentApproved,
    PolicyEvaluated,
    SignatureRegistered,
)

logger = logging.getLogger(__name__)


class GovernanceOrchestrator(IGovernanceOrchestrator):
    """Central orchestrator managing compliance policies, deployment checks and blockchain audits."""

    def __init__(self, event_bus: IEventBus, container: Optional[Any] = None) -> None:
        self._event_bus = event_bus
        self._container = container
        self._repo = GovernanceRepository()

        # Engines
        self._evaluator = PolicyEvaluator()
        self._verifier = SignatureVerifier()

    @property
    def repository(self) -> GovernanceRepository:
        return self._repo

    # ── Downstream Integration Helpers ───────────────────────────────

    def _get_memory_orchestrator(self) -> Optional[Any]:
        if self._container and self._container.has("research_platform.institutional_memory.orchestrator.InstitutionalMemoryOrchestrator"):
            return self._container.resolve("research_platform.institutional_memory.orchestrator.InstitutionalMemoryOrchestrator")
        return None

    def _get_kg_orchestrator(self) -> Optional[Any]:
        if self._container and self._container.has("research_platform.knowledge_graph.orchestrator.KnowledgeGraphOrchestrator"):
            return self._container.resolve("research_platform.knowledge_graph.orchestrator.KnowledgeGraphOrchestrator")
        return None

    def _publish_memory_record(self, category: str, record: Any) -> None:
        mem_orch = self._get_memory_orchestrator()
        if not mem_orch:
            return
        try:
            mem_orch.publish_memory(category, record)
        except Exception as e:
            logger.error("Failed to publish to institutional memory: %s", e)

    def _update_knowledge_graph(self, record: Any, approval: Optional[DeploymentApproval] = None) -> None:
        kg_orch = self._get_kg_orchestrator()
        if not kg_orch:
            return
        try:
            if isinstance(record, GovernanceAuditRecord):
                # Register Audit Block Node
                kg_orch.register_node(
                    node_id=record.record_id,
                    node_type="AUDIT_RECORD",
                    subsystem="governance",
                    event="AuditLogged",
                    author="system",
                    properties={"block_hash": record.block_hash, "action": record.action_type}
                )

                if record.previous_block_hash != "genesis":
                    kg_orch.link_nodes(
                        source_id=record.record_id,
                        target_id=record.previous_block_hash,
                        relationship_type="references",
                        subsystem="governance"
                    )
            elif approval:
                # Register Approval Node
                kg_orch.register_node(
                    node_id=approval.approval_id,
                    node_type="DEPLOYMENT_APPROVAL",
                    subsystem="governance",
                    event="DeploymentApproved",
                    author="system",
                    properties={"status": approval.status}
                )
        except Exception as e:
            logger.error("Failed to update knowledge graph: %s", e)

    # ── Orchestrator Actions ──────────────────────────────────────────

    def register_rule(
        self,
        rule_id: str,
        name: str,
        description: str,
        criterion_key: str,
        operator: str,
        threshold: float
    ) -> ComplianceRule:
        """Register a new compliance policy rule."""
        rule = ComplianceRule(
            rule_id=rule_id,
            name=name,
            description=description,
            criterion_key=criterion_key,
            operator=operator,
            threshold=threshold
        )
        self._repo.save_rule(rule)
        return rule

    def create_deployment_approval(
        self,
        approval_id: str,
        deployment_id: str,
        metrics: Dict[str, float]
    ) -> DeploymentApproval:
        """Evaluate policies and initialize a deployment approval record."""
        rules = self._repo.list_rules()
        results = self._evaluator.evaluate_policies(rules, metrics)
        self._event_bus.publish(PolicyEvaluated(payload={"deployment_id": deployment_id}))

        all_passed = all(r.passed for r in results)
        status = "APPROVED" if all_passed else "REJECTED"

        approval = DeploymentApproval(
            approval_id=approval_id,
            deployment_id=deployment_id,
            policy_results=results,
            status=status
        )
        self._repo.save_approval(approval)
        self._event_bus.publish(DeploymentApproved(payload={"approval_id": approval_id, "status": status}))

        # Downstream
        self._publish_memory_record("deployment_approvals", approval)
        self._update_knowledge_graph(record=None, approval=approval)

        return approval

    def sign_approval(self, approval_id: str, signature: DigitalSignature) -> DeploymentApproval:
        """Verify signature and append authorization signature to approval."""
        approval = self._repo.get_approval(approval_id)
        if not approval:
            raise ValueError(f"Approval record '{approval_id}' not found.")

        # Cryptographic validation check
        verified = self._verifier.verify_signature(signature, data_hash=approval.deployment_id)
        if not verified:
            raise ValueError("Cryptographic verification check failed for signature.")

        signatures = list(approval.signatures)
        signatures.append(signature)

        updated = approval.model_copy(update={"signatures": signatures})
        self._repo.save_approval(updated)

        self._event_bus.publish(SignatureRegistered(payload={
            "approval_id": approval_id,
            "author": signature.author
        }))

        # Downstream
        self._publish_memory_record("deployment_approvals", updated)

        return updated

    def audit_action(
        self,
        record_id: str,
        action_type: str,
        user_role: AccessRole,
        signature: Optional[DigitalSignature] = None,
        policy_results: List[PolicyEvaluationResult] = None
    ) -> GovernanceAuditRecord:
        """Create a block-linked audit record containing signed hashes of quantitative operations."""
        prev = self._repo.get_latest_audit_record()
        prev_hash = prev.block_hash if prev else "genesis"

        # Calculate block hash: SHA256 of parameters and previous hash
        now = datetime.now(timezone.utc)
        payload = f"{prev_hash}|{action_type}|{user_role.value}|{now.isoformat()}"
        block_hash = hashlib.sha256(payload.encode()).hexdigest()

        record = GovernanceAuditRecord(
            record_id=record_id,
            action_type=action_type,
            user_role=user_role,
            timestamp=now,
            signature=signature,
            policy_results=policy_results or [],
            block_hash=block_hash,
            previous_block_hash=prev_hash
        )
        self._repo.save_audit_record(record)
        self._event_bus.publish(AuditLogged(payload={"record_id": record_id, "block_hash": block_hash}))

        # Downstream
        self._publish_memory_record("governance_audit", record)
        self._update_knowledge_graph(record=record)

        return record
