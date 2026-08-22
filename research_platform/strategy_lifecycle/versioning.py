"""Lineage tracking and immutable append-only version operations.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional
from research_platform.strategy_lifecycle.interfaces import IStrategyRepository
from research_platform.strategy_lifecycle.models import StrategyVersion

logger = logging.getLogger(__name__)


class StrategyVersioning:
    """Manages append-only creation of strategy versions with parent-child relationship tracking."""

    def __init__(self, repository: IStrategyRepository) -> None:
        self._repo = repository

    def create_version(
        self,
        strategy_id: str,
        parameters: Dict[str, Any],
        parent_version_id: Optional[str] = None,
        indicators: Optional[List[Dict[str, Any]]] = None,
        features: Optional[List[str]] = None,
        datasets: Optional[List[str]] = None,
        training_config: Optional[Dict[str, Any]] = None,
        optimizer_settings: Optional[Dict[str, Any]] = None,
        risk_profile: Optional[Dict[str, Any]] = None,
        market_assumptions: Optional[Dict[str, Any]] = None,
        deployment_metadata: Optional[Dict[str, Any]] = None
    ) -> StrategyVersion:
        """Create a new version for a strategy. Never overwrites."""
        strategy = self._repo.get_strategy(strategy_id)
        if not strategy:
            raise ValueError(f"Strategy '{strategy_id}' not found.")

        # Determine version number and check parent version
        version_number = 1
        if parent_version_id:
            parent = self._repo.get_version(parent_version_id)
            if not parent:
                raise ValueError(f"Parent version '{parent_version_id}' not found.")
            if parent.strategy_id != strategy_id:
                raise ValueError(f"Parent version belongs to strategy '{parent.strategy_id}', not '{strategy_id}'.")
            version_number = parent.version_number + 1
        else:
            existing = self._repo.list_versions(strategy_id)
            if existing:
                version_number = max(v.version_number for v in existing) + 1

        version_id = f"{strategy_id}-v{version_number}-{uuid.uuid4().hex[:6]}"

        version = StrategyVersion(
            version_id=version_id,
            strategy_id=strategy_id,
            version_number=version_number,
            parent_version_id=parent_version_id,
            parameters=parameters,
            indicators=indicators or [],
            features=features or [],
            datasets=datasets or [],
            training_config=training_config or {},
            optimizer_settings=optimizer_settings or {},
            risk_profile=risk_profile or {},
            market_assumptions=market_assumptions or {},
            deployment_metadata=deployment_metadata or {}
        )

        self._repo.save_version(version)

        # Update Strategy's version_ids
        updated_version_ids = list(strategy.version_ids) + [version_id]
        updated_strategy = strategy.model_copy(update={"version_ids": updated_version_ids})
        self._repo.save_strategy(updated_strategy)

        logger.info("Created version %d (%s) for strategy '%s'", version_number, version_id, strategy_id)
        return version

    def get_lineage(self, version_id: str) -> List[StrategyVersion]:
        """Trace parents lineage back to root version."""
        lineage = []
        current = self._repo.get_version(version_id)
        while current:
            lineage.append(current)
            if current.parent_version_id:
                current = self._repo.get_version(current.parent_version_id)
            else:
                break
        # Reverse to get chronological order from root to current
        return list(reversed(lineage))
