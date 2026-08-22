"""Deployment engine allocating canary routes and managing environment triggers.
"""

from __future__ import annotations

import uuid
from research_platform.deployment.models import StrategyDeployment


class DeploymentEngine:
    """Handles Blue/Green active switches and canary weights allocations."""

    def initiate_deployment(
        self,
        strategy_id: str,
        environment: str,
        version_id: str,
        canary_weight: float
    ) -> StrategyDeployment:
        if not strategy_id or not version_id:
            raise ValueError("Strategy ID and Version ID must not be blank.")
        if environment not in ["PAPER", "STAGING", "PRODUCTION"]:
            raise ValueError("Invalid Deployment Environment: Profile must be PAPER, STAGING, or PRODUCTION.")
        if not (0.0 <= canary_weight <= 100.0):
            raise ValueError("Invalid Canary Weight: Weight must be between 0% and 100%.")

        return StrategyDeployment(
            deployment_id=f"dep-{uuid.uuid4().hex[:8]}",
            strategy_id=strategy_id,
            environment=environment,
            status="ACTIVE",
            version_id=version_id,
            active_weight=canary_weight
        )
