"""Alert Severity, Comparison Operators, and Immutable Alert Rule Model (Sprint 12C)."""

from __future__ import annotations

import logging
import uuid
from enum import Enum
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class AlertSeverity(str, Enum):
    """Operational alert severity levels."""

    INFO = "INFO"
    WARNING = "WARNING"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ComparisonOperator(str, Enum):
    """Comparison operators for threshold alert rule evaluation."""

    GT = "GT"    # >
    GTE = "GTE"  # >=
    LT = "LT"    # <
    LTE = "LTE"  # <=
    EQ = "EQ"    # ==
    NEQ = "NEQ"  # !=


class AlertRule(BaseModel):
    """Immutable operational threshold alert rule specification."""

    rule_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    rule_name: str = Field(..., description="Name of the alert rule.")
    metric_name: str = Field(..., description="Target metric to monitor.")
    comparison_operator: ComparisonOperator = Field(default=ComparisonOperator.GT)
    threshold_value: float = Field(..., description="Threshold numeric value.")
    severity: AlertSeverity = Field(default=AlertSeverity.WARNING)
    enabled: bool = Field(default=True, description="Rule active flag.")
    description: str = Field(default="", description="Rule description.")
    is_advisory_only: bool = Field(default=True)

    model_config = ConfigDict(frozen=True)

    def evaluate_value(self, current_value: float) -> bool:
        """Evaluate if current_value triggers the alert rule condition."""
        if not self.enabled:
            return False

        op = self.comparison_operator
        val = current_value
        thresh = self.threshold_value

        if op == ComparisonOperator.GT:
            return val > thresh
        elif op == ComparisonOperator.GTE:
            return val >= thresh
        elif op == ComparisonOperator.LT:
            return val < thresh
        elif op == ComparisonOperator.LTE:
            return val <= thresh
        elif op == ComparisonOperator.EQ:
            return val == thresh
        elif op == ComparisonOperator.NEQ:
            return val != thresh
        return False
