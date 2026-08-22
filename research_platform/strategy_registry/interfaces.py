"""Abstract contracts for the Strategy Registry.
"""

from __future__ import annotations

import abc
from typing import List, Optional
from research_platform.strategy_registry.models import (
    RegisteredStrategy,
    StrategyRegistryStatistics,
    StrategyRegistrySnapshot,
)


class IStrategyRegistryRepository(abc.ABC):
    """Abstract contract for persisting registered strategies."""

    @abc.abstractmethod
    def save_strategy(self, strategy: RegisteredStrategy) -> None:
        """Persist registered strategy details."""

    @abc.abstractmethod
    def get_strategy(self, strategy_id: str) -> Optional[RegisteredStrategy]:
        """Retrieve strategy details by ID."""

    @abc.abstractmethod
    def list_strategies(self) -> List[RegisteredStrategy]:
        """List all registered strategies."""


class IStrategyRegistry(abc.ABC):
    """Abstract contract for core Strategy Registry orchestrators."""

    @abc.abstractmethod
    def register_strategy(
        self,
        strategy_id: str,
        name: str,
        description: str,
        version: str,
        git_hash: str,
        dependencies: List[str],
        tags: List[str],
        categories: List[str],
        author: str,
        asset_class: str,
        risk_profile: str,
        capabilities: List[str]
    ) -> RegisteredStrategy:
        """Register a strategy, validating inputs and persisting details."""


class ISearchEngine(abc.ABC):
    """Abstract contract for searching strategy metadata."""

    @abc.abstractmethod
    def search(self, query: str) -> List[RegisteredStrategy]:
        """Search strategies matching queries keywords."""


class IVersionManager(abc.ABC):
    """Abstract contract for managing codes versions."""

    @abc.abstractmethod
    def log_version_update(self, strategy_id: str, version: str, git_hash: str) -> None:
        """Log code changes and version shifts."""
