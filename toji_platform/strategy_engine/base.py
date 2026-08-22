"""Base Strategy interface."""

from __future__ import annotations
from abc import ABC, abstractmethod

from toji_platform.market_scanner.models import MarketScan
from toji_platform.strategy_engine.models import StrategyMetadata, TradeIdea
from toji_platform.strategy_engine.context import StrategyContext
from toji_platform.core.types import HealthStatus

class IStrategy(ABC):
    """Canonical interface that every strategy plugin must implement."""

    @abstractmethod
    def initialize(self, context: StrategyContext) -> None:
        """Called when strategy is loaded into the engine."""
        pass

    @abstractmethod
    def analyze(self, scan: MarketScan) -> list[TradeIdea]:
        """Analyzes a market scan observation snapshot and returns trade ideas."""
        pass

    @abstractmethod
    def shutdown(self) -> None:
        """Called when strategy is unloaded from the engine."""
        pass

    @abstractmethod
    def health_check(self) -> HealthStatus:
        """Returns the internal health status of the strategy."""
        pass

    @abstractmethod
    def metadata(self) -> StrategyMetadata:
        """Returns strategy name, version, and details."""
        pass
