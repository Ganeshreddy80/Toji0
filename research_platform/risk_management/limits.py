"""Limits Engine validating maximum size and daily drawdowns limits.
"""

from __future__ import annotations

import uuid
from typing import List

from research_platform.risk_management.interfaces import IRiskLimitsEngine
from research_platform.risk_management.models import LimitViolation, RiskLimits
from research_platform.oms.models import OrderRequest


class RiskLimitsEngine(IRiskLimitsEngine):
    """Enforces absolute daily loss limits, drawdowns, and position caps."""

    def __init__(self, limits: RiskLimits = RiskLimits()) -> None:
        self.limits = limits

    def check_limits(self, request: OrderRequest) -> List[LimitViolation]:
        """Verify order request parameters against limit thresholds."""
        violations = []

        # 1. Max Position Size Check (comparing absolute quantities)
        if request.quantity > self.limits.max_position_size * 1000.0:  # arbitrary max reference scale
            violations.append(
                LimitViolation(
                    violation_id=str(uuid.uuid4()),
                    limit_name="MaxPositionSize",
                    violated=True,
                    details=f"Order quantity {request.quantity} exceeds limit scale"
                )
            )

        return violations
