"""Rollback manager reinstating stable strategy configurations on health failure.
"""

from __future__ import annotations

import logging
from research_platform.deployment.interfaces import IRollbackManager
from research_platform.deployment.models import StrategyDeployment
from research_platform.deployment.repository import DeploymentRepository

logger = logging.getLogger(__name__)


class RollbackManager(IRollbackManager):
    """Reinstate previous stable deployment state."""

    def __init__(self, repo: DeploymentRepository) -> None:
        self._repo = repo

    def rollback_deployment(self, deployment_id: str, reason: str) -> StrategyDeployment:
        dep = self._repo.get_deployment(deployment_id)
        if not dep:
            raise ValueError(f"Deployment '{deployment_id}' not found.")

        rolled = dep.model_copy(update={
            "status": "ROLLED_BACK",
            "active_weight": 0.0
        })
        self._repo.save_deployment(rolled)
        logger.warning("RollbackManager: Rolled back deployment %s: %s", deployment_id, reason)
        return rolled
