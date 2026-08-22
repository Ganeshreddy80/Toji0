"""Abstract contracts for the Risk Management System.
"""

from __future__ import annotations

import abc
from typing import List, Optional

from research_platform.risk_management.models import (
    ComplianceReport,
    LimitViolation,
    RiskAlert,
    RiskEvaluation
)
from research_platform.oms.models import OrderRequest


class IRiskLimitsEngine(abc.ABC):
    """Abstract contract for checking limit violations."""

    @abc.abstractmethod
    def check_limits(self, request: OrderRequest) -> List[LimitViolation]:
        """Verify order request parameter thresholds."""


class IRiskComplianceEngine(abc.ABC):
    """Abstract contract for compliance gates."""

    @abc.abstractmethod
    def evaluate_compliance(self, request: OrderRequest) -> ComplianceReport:
        """Enforce risk limits checks, returning compliance reports."""


class IRiskRepository(abc.ABC):
    """Abstract database repository contract for risk metrics."""

    @abc.abstractmethod
    def save_evaluation(self, evaluation: RiskEvaluation) -> None:
        """Persist a RiskEvaluation."""

    @abc.abstractmethod
    def save_alert(self, alert: RiskAlert) -> None:
        """Persist a RiskAlert."""
class IRiskOrchestrator(abc.ABC):
    """Abstract contract for risk orchestrator."""
    pass
