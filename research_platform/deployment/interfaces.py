"""Abstract contracts for the Deployment Manager.
"""

from __future__ import annotations

import abc
from typing import List, Optional
from research_platform.deployment.models import (
    StrategyDeployment,
    DeploymentLock,
    DeploymentHealthCard,
)


class IDeploymentRepository(abc.ABC):
    """Abstract contract for persisting strategy deployment states."""

    @abc.abstractmethod
    def save_deployment(self, deployment: StrategyDeployment) -> None:
        """Persist deployment details."""

    @abc.abstractmethod
    def get_deployment(self, deployment_id: str) -> Optional[StrategyDeployment]:
        """Retrieve deployment details by ID."""

    @abc.abstractmethod
    def list_deployments(self) -> List[StrategyDeployment]:
        """List active deployments."""

    @abc.abstractmethod
    def save_lock(self, lock: DeploymentLock) -> None:
        """Persist deployment lock states."""

    @abc.abstractmethod
    def get_lock(self) -> DeploymentLock:
        """Retrieve current lock status."""


class IDeploymentEngine(abc.ABC):
    """Abstract contract for deployment engines (Canary, Blue/Green rollout)."""

    @abc.abstractmethod
    def deploy_strategy(
        self,
        strategy_id: str,
        environment: str,
        version_id: str,
        canary_weight: float
    ) -> StrategyDeployment:
        """Deploy strategy to target environment using canary routes weights."""


class IHealthMonitor(abc.ABC):
    """Abstract contract for active diagnostic health reviews."""

    @abc.abstractmethod
    def evaluate_health(self, deployment_id: str) -> DeploymentHealthCard:
        """Run active error checks and check latency parameters."""


class IRollbackManager(abc.ABC):
    """Abstract contract for triggering rollback sequences."""

    @abc.abstractmethod
    def rollback_deployment(self, deployment_id: str, reason: str) -> StrategyDeployment:
        """Reinstate previous stable deployments states."""
