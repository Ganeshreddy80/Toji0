"""Rollback engine supporting version, timestamp and deployment target restorations.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from research_platform.strategy_lifecycle.interfaces import IStrategyRepository
from research_platform.strategy_lifecycle.models import LifecycleStage, RollbackRequest, Strategy

logger = logging.getLogger(__name__)


class StrategyRollbackEngine:
    """Coordinates rollback procedures and updates active lifecycle states."""

    def __init__(self, repository: IStrategyRepository) -> None:
        self._repo = repository

    def rollback_to_version(
        self,
        strategy_id: str,
        target_version_id: str,
        requested_by: str,
        reason: str
    ) -> RollbackRequest:
        """Roll back strategy parameters to a specific historical version."""
        strategy = self._repo.get_strategy(strategy_id)
        if not strategy:
            raise ValueError(f"Strategy '{strategy_id}' not found.")

        target_version = self._repo.get_version(target_version_id)
        if not target_version:
            raise ValueError(f"Target version '{target_version_id}' not found.")

        if target_version.strategy_id != strategy_id:
            raise ValueError(f"Target version belongs to strategy '{target_version.strategy_id}', not '{strategy_id}'.")

        # Record rollback audit request
        rollback = RollbackRequest(
            rollback_id=f"rb-{uuid.uuid4().hex[:8]}",
            strategy_id=strategy_id,
            current_version_id=strategy.version_ids[-1] if strategy.version_ids else "unknown",
            target_version_id=target_version_id,
            requested_by=requested_by,
            reason=reason
        )
        self._repo.save_rollback_request(rollback)

        # Update strategy state to ROLLBACK
        updated = strategy.model_copy(update={"current_stage": LifecycleStage.ROLLBACK})
        self._repo.save_strategy(updated)

        logger.info("Rolled back strategy '%s' to version '%s'. Reason: %s", strategy_id, target_version_id, reason)
        return rollback

    def rollback_to_timestamp(
        self,
        strategy_id: str,
        ts: datetime,
        requested_by: str,
        reason: str
    ) -> RollbackRequest:
        """Find the active version at the target timestamp and roll back to it."""
        versions = self._repo.list_versions(strategy_id)
        if not versions:
            raise ValueError(f"No versions found for strategy '{strategy_id}'.")

        # Find latest version created at or before ts
        target_version = None
        for v in sorted(versions, key=lambda x: x.created_at):
            if v.created_at <= ts:
                target_version = v

        if not target_version:
            raise ValueError(f"No active version found at timestamp '{ts}' for strategy '{strategy_id}'.")

        return self.rollback_to_version(strategy_id, target_version.version_id, requested_by, reason)

    def rollback_to_deployment(
        self,
        strategy_id: str,
        deployment_id: str,
        requested_by: str,
        reason: str
    ) -> RollbackRequest:
        """Roll back strategy to the version deployed in deployment_id."""
        deployment = self._repo.get_deployment_record(deployment_id)
        if not deployment:
            raise ValueError(f"Deployment record '{deployment_id}' not found.")

        if deployment.strategy_id != strategy_id:
            raise ValueError(f"Deployment record belongs to strategy '{deployment.strategy_id}', not '{strategy_id}'.")

        return self.rollback_to_version(strategy_id, deployment.version_id, requested_by, reason)
