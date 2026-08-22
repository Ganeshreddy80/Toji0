"""Abstract contracts for the Strategy Lab.
"""

from __future__ import annotations

import abc
from typing import List, Optional

from research_platform.strategy_lab.models import StrategyDefinition


class IStrategyRepository(abc.ABC):
    """Abstract database repository contract for strategy persistence."""

    @abc.abstractmethod
    def save(self, strategy: StrategyDefinition) -> None:
        """Persist a StrategyDefinition."""

    @abc.abstractmethod
    def get(self, strategy_id: str) -> Optional[StrategyDefinition]:
        """Fetch StrategyDefinition by ID."""

    @abc.abstractmethod
    def list_all(self) -> List[StrategyDefinition]:
        """List all strategies."""


class IStrategyLabOrchestrator(abc.ABC):
    """Abstract contract for the Strategy Lab Orchestrator."""

    @abc.abstractmethod
    def compose_strategy(self, definition: StrategyDefinition) -> StrategyDefinition:
        """Process and validate strategy composition before registration."""
