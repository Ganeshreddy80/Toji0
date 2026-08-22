"""Domain events for the Market Regime Intelligence Engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from toji_platform.core.event_bus.events import BaseEvent


@dataclass(frozen=True)
class RegimeDetected(BaseEvent):
    """Fired when a new MarketRegime is detected."""
    pass


@dataclass(frozen=True)
class RegimeTransitioned(BaseEvent):
    """Fired when a shift in trend, volatility, or liquidity is detected."""
    pass


@dataclass(frozen=True)
class VolatilityRegimeChanged(BaseEvent):
    """Fired when the volatility regime changes."""
    pass


@dataclass(frozen=True)
class LiquidityRegimeChanged(BaseEvent):
    """Fired when the liquidity regime changes."""
    pass


@dataclass(frozen=True)
class TrendRegimeChanged(BaseEvent):
    """Fired when the trend regime changes."""
    pass


@dataclass(frozen=True)
class MarketStructureAnalyzed(BaseEvent):
    """Fired when support/resistance and order blocks analysis completes."""
    pass
