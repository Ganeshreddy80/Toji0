"""Thread-safe, append-only repository for storing compliance rules and block-linked audit records.
"""

from __future__ import annotations

import threading
from typing import Dict, List, Optional
from research_platform.governance.interfaces import IGovernanceRepository
from research_platform.governance.models import (
    ComplianceRule,
    DeploymentApproval,
    GovernanceAuditRecord,
)


class GovernanceRepository(IGovernanceRepository):
    """Memory-backed, thread-safe repository implementation."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._rules: Dict[str, ComplianceRule] = {}
        self._approvals: Dict[str, DeploymentApproval] = {}
        self._audits: List[GovernanceAuditRecord] = []

    def save_rule(self, rule: ComplianceRule) -> None:
        with self._lock:
            self._rules[rule.rule_id] = rule

    def list_rules(self) -> List[ComplianceRule]:
        with self._lock:
            return list(self._rules.values())

    def save_approval(self, approval: DeploymentApproval) -> None:
        with self._lock:
            self._approvals[approval.approval_id] = approval

    def get_approval(self, approval_id: str) -> Optional[DeploymentApproval]:
        with self._lock:
            return self._approvals.get(approval_id)

    def save_audit_record(self, record: GovernanceAuditRecord) -> None:
        with self._lock:
            self._audits.append(record)

    def get_latest_audit_record(self) -> Optional[GovernanceAuditRecord]:
        with self._lock:
            if not self._audits:
                return None
            return self._audits[-1]

    def list_audit_history(self) -> List[GovernanceAuditRecord]:
        with self._lock:
            return list(self._audits)
