"""Abstract contracts for the Governance & Audit Platform.
"""

from __future__ import annotations

import abc
from typing import Any, Dict, List, Optional
from research_platform.governance.models import (
    ComplianceRule,
    DeploymentApproval,
    DigitalSignature,
    GovernanceAuditRecord,
    PolicyEvaluationResult,
)


class IGovernanceRepository(abc.ABC):
    """Abstract contract for persisting rules, signatures, and block-linked audit histories."""

    @abc.abstractmethod
    def save_rule(self, rule: ComplianceRule) -> None:
        """Persist a compliance constraint rule."""

    @abc.abstractmethod
    def list_rules(self) -> List[ComplianceRule]:
        """List all active compliance rules."""

    @abc.abstractmethod
    def save_approval(self, approval: DeploymentApproval) -> None:
        """Persist a deployment approval record."""

    @abc.abstractmethod
    def get_approval(self, approval_id: str) -> Optional[DeploymentApproval]:
        """Retrieve an approval record by ID."""

    @abc.abstractmethod
    def save_audit_record(self, record: GovernanceAuditRecord) -> None:
        """Persist a block-linked audit record."""

    @abc.abstractmethod
    def get_latest_audit_record(self) -> Optional[GovernanceAuditRecord]:
        """Retrieve the latest block-linked audit record."""

    @abc.abstractmethod
    def list_audit_history(self) -> List[GovernanceAuditRecord]:
        """List the entire audit trail log."""


class IPolicyEvaluator(abc.ABC):
    """Abstract contract for evaluating policy rules."""

    @abc.abstractmethod
    def evaluate_policies(self, rules: List[ComplianceRule], metrics: Dict[str, float]) -> List[PolicyEvaluationResult]:
        """Evaluate compliance rules against runtime metrics."""


class ISignatureVerifier(abc.ABC):
    """Abstract contract for cryptographic signature verifications."""

    @abc.abstractmethod
    def verify_signature(self, signature: DigitalSignature, data_hash: str) -> bool:
        """Verify signature hash credentials."""


class IGovernanceOrchestrator(abc.ABC):
    """Abstract contract for the governance orchestrator."""
    pass
