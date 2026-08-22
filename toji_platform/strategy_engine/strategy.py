"""Base implementation of Strategy class."""

from __future__ import annotations

from toji_platform.strategy_engine.base import IStrategy
from toji_platform.strategy_engine.models import StrategyMetadata, TradeIdea
from toji_platform.strategy_engine.context import StrategyContext
from toji_platform.market_scanner.models import MarketScan
from toji_platform.core.types import HealthStatus

class BaseStrategy(IStrategy):
    """Reference adapter class providing default implementations for strategy plugins."""

    def __init__(self, name: str, version: str = "1.0.0", description: str = "", author: str = "") -> None:
        self._name = name
        self._version = version
        self._description = description
        self._author = author
        self.context: StrategyContext | None = None
        self._health = HealthStatus.HEALTHY

    def initialize(self, context: StrategyContext) -> None:
        self.context = context

    def analyze(self, scan: MarketScan) -> list[TradeIdea]:
        return []

    def shutdown(self) -> None:
        pass

    def health_check(self) -> HealthStatus:
        return self._health

    def metadata(self) -> StrategyMetadata:
        return StrategyMetadata(
            name=self._name,
            version=self._version,
            description=self._description,
            author=self._author
        )
