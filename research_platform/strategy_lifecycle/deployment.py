"""Deployment coordination, readiness verification and canary execution tracking.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from research_platform.strategy_lifecycle.interfaces import IDeploymentValidator, IStrategyRepository
from research_platform.strategy_lifecycle.models import CanaryResult, DeploymentRecord, LifecycleStage, Strategy, StrategyVersion

logger = logging.getLogger(__name__)


class StrategyDeploymentValidator(IDeploymentValidator):
    """Enforces checks for risk boundaries, observability hooks, and configuration metrics."""

    def validate_readiness(self, strategy: Strategy, version: StrategyVersion) -> bool:
        """Check all deployment readiness parameters."""
        # Rule 1: Must have risk limits configured
        if not version.risk_profile or "max_drawdown" not in version.risk_profile:
            logger.warning("Deployment check failed: Missing 'max_drawdown' in risk profile.")
            return False

        # Rule 2: Must have parameter metrics defined
        if not version.parameters:
            logger.warning("Deployment check failed: Empty strategy parameters.")
            return False

        # Rule 3: Must have training/backtest assumptions documented
        if not version.market_assumptions:
            logger.warning("Deployment check failed: Missing market assumptions.")
            return False

        return True


class StrategyDeploymentCoordinator:
    """Orchestrates deployment execution status updates and canary results logging."""

    def __init__(self, repository: IStrategyRepository, validator: IDeploymentValidator) -> None:
        self._repo = repository
        self._validator = validator

    def start_deployment(self, strategy_id: str, version_id: str, stage: LifecycleStage) -> DeploymentRecord:
        """Initialize deployment and verify readiness before starting."""
        strategy = self._repo.get_strategy(strategy_id)
        version = self._repo.get_version(version_id)
        if not strategy or not version:
            raise ValueError(f"Strategy or version not found for ID: {strategy_id}, {version_id}")

        if not self._validator.validate_readiness(strategy, version):
            raise ValueError("Strategy is not ready for deployment. Readiness checks failed.")

        deployment = DeploymentRecord(
            deployment_id=f"dep-{uuid.uuid4().hex[:8]}",
            strategy_id=strategy_id,
            version_id=version_id,
            stage=stage,
            started_at=datetime.now(timezone.utc),
            status="PENDING"
        )
        self._repo.save_deployment_record(deployment)
        return deployment

    def complete_deployment(
        self,
        deployment_id: str,
        status: str,
        error_message: Optional[str] = None
    ) -> DeploymentRecord:
        """Mark deployment complete with status and timestamps."""
        deployment = self._repo.get_deployment_record(deployment_id)
        if not deployment:
            raise ValueError(f"Deployment record '{deployment_id}' not found.")

        updated = deployment.model_copy(update={
            "completed_at": datetime.now(timezone.utc),
            "status": status,
            "error_message": error_message
        })
        self._repo.save_deployment_record(updated)

        # Update strategy active stage in repository if deployment succeeded
        if status == "SUCCEEDED":
            strategy = self._repo.get_strategy(deployment.strategy_id)
            if strategy:
                # Target stage is CANARY or LIVE based on the deployment stage
                updated_strategy = strategy.model_copy(update={"current_stage": deployment.stage})
                self._repo.save_strategy(updated_strategy)

        return updated

    def log_canary_result(self, deployment_id: str, passed: bool, metrics: Dict[str, Any]) -> CanaryResult:
        """Persist a canary run outcome."""
        deployment = self._repo.get_deployment_record(deployment_id)
        if not deployment:
            raise ValueError(f"Deployment record '{deployment_id}' not found.")

        result = CanaryResult(
            canary_id=f"can-{uuid.uuid4().hex[:8]}",
            deployment_id=deployment_id,
            passed=passed,
            metrics=metrics,
            checked_at=datetime.now(timezone.utc)
        )
        self._repo.save_canary_result(result)
        return result
