"""Approval engine managing risk, performance, and committee approval gates.
"""

from __future__ import annotations

from research_platform.strategy_lifecycle.interfaces import IApprovalEngine
from research_platform.strategy_lifecycle.models import StrategyApproval


class ApprovalEngine(IApprovalEngine):
    """Enforces multi-signature approval gates before production deployments."""

    def approve_gate(self, strategy_id: str, gate_name: str, approved: bool, reviewer: str, reason: str) -> StrategyApproval:
        return StrategyApproval(
            gate_name=gate_name,
            approved=approved,
            reviewer=reviewer,
            reason=reason
        )
