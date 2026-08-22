"""Abstract contracts for the Strategy Lifecycle Manager.
"""

from __future__ import annotations

import abc
from typing import Any, List, Optional
from research_platform.strategy_lifecycle.models import (
    StrategyStatus,
    StrategyVersion,
    StrategyApproval,
    StrategyPromotion,
    StrategyRollback,
    StrategyAudit,
)


class IStrategyRepository(abc.ABC):
    """Abstract contract for persisting strategy lifecycle state databases."""

    @abc.abstractmethod
    def save_status(self, status: StrategyStatus) -> None:
        """Persist current strategy status states."""

    @abc.abstractmethod
    def get_status(self, strategy_id: str) -> Optional[StrategyStatus]:
        """Retrieve strategy details by ID."""

    @abc.abstractmethod
    def list_strategies(self, status_filter: Optional[str] = None) -> List[StrategyStatus]:
        """List strategies filtering by active state."""

    @abc.abstractmethod
    def save_audit(self, audit: StrategyAudit) -> None:
        """Persist state transition audit record."""

    @abc.abstractmethod
    def get_audit_history(self, strategy_id: str) -> List[StrategyAudit]:
        """List transition histories matching filter ID."""

    @abc.abstractmethod
    def save_approval(self, approval: StrategyApproval) -> None:
        """Persist gate review outcome."""

    @abc.abstractmethod
    def list_approvals(self, strategy_id: str) -> List[StrategyApproval]:
        """List approvals outcomes logs."""


class IStrategyLifecycle(abc.ABC):
    """Abstract contract for central lifecycle orchestrator."""

    @abc.abstractmethod
    def create_strategy(
        self,
        strategy_id: str,
        name: str,
        description: str,
        author: str,
        asset_class: str
    ) -> StrategyStatus:
        """Initialize draft strategy entry."""


class ILifecycleEngine(abc.ABC):
    """Abstract contract for state migrations engine."""

    @abc.abstractmethod
    def transition_state(self, strategy: StrategyStatus, target_state: str, actor: str, reason: str) -> StrategyStatus:
        """Evaluate migrations matrix rules and execute state changes."""


class IApprovalEngine(abc.ABC):
    """Abstract contract for gates validations engine."""

    @abc.abstractmethod
    def approve_gate(self, strategy_id: str, gate_name: str, approved: bool, reviewer: str, reason: str) -> StrategyApproval:
        """Enforces compliance review gate confirmations."""


class IPromotionEngine(abc.ABC):
    """Abstract contract for thresholds rules validations."""

    @abc.abstractmethod
    def evaluate_promotion(self, strategy: StrategyStatus) -> bool:
        """Validates returns statistics and Sharpe threshold gates before promoting upward."""


class IRollbackEngine(abc.ABC):
    """Abstract contract for deployment rollback actions."""

    @abc.abstractmethod
    def execute_rollback(self, strategy_id: str, target_version: str, reason: str) -> StrategyRollback:
        """Dismantle active production deployment and reinstate previous states."""


class IAuditEngine(abc.ABC):
    """Abstract contract for tracking transaction audit logs."""

    @abc.abstractmethod
    def log_action(self, action: str, strategy_id: str, prev_state: str, new_state: str, actor: str, reason: str) -> StrategyAudit:
        """Create and write audit logs."""
