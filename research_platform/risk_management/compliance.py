"""Compliance Engine auditing orders before forwarding to OMS.
"""

from __future__ import annotations

from typing import List

from research_platform.risk_management.interfaces import IRiskComplianceEngine, IRiskLimitsEngine
from research_platform.risk_management.kill_switch import KillSwitch
from research_platform.risk_management.models import ComplianceReport
from research_platform.oms.models import OrderRequest


class ComplianceEngine(IRiskComplianceEngine):
    """Enforces kill switch blocks, buying power checks, and margin limits."""

    def __init__(
        self,
        limits_engine: IRiskLimitsEngine,
        kill_switch: KillSwitch
    ) -> None:
        self.limits_engine = limits_engine
        self.kill_switch = kill_switch

    def evaluate_compliance(self, request: OrderRequest) -> ComplianceReport:
        """Enforce risk limits checks, returning compliance reports."""
        reasons = []

        # 1. Kill Switch Check
        if self.kill_switch.is_activated:
            reasons.append(f"Kill Switch active: {self.kill_switch.get_status().reason}")

        # 2. Limits checks
        violations = self.limits_engine.check_limits(request)
        for v in violations:
            reasons.append(f"Limit violated: {v.details}")

        compliant = len(reasons) == 0

        return ComplianceReport(
            compliant=compliant,
            rejection_reasons=reasons
        )
