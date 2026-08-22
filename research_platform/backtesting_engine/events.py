"""Event contracts for the Backtesting Engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from toji_platform.core.event_bus.events import BaseEvent


@dataclass(frozen=True)
class MarketDataArrived(BaseEvent):
    """Fired when next historical tick/OHLCV bar is replayed."""
    pass


@dataclass(frozen=True)
class StrategySignalGenerated(BaseEvent):
    """Fired when strategy triggers signals."""
    pass


@dataclass(frozen=True)
class OrderSubmitted(BaseEvent):
    """Fired when strategy submits orders."""
    pass


@dataclass(frozen=True)
class OrderAccepted(BaseEvent):
    """Fired when matching queue accepts orders."""
    pass


@dataclass(frozen=True)
class OrderRejected(BaseEvent):
    """Fired when orders fail margin or parameters checks."""
    pass


@dataclass(frozen=True)
class OrderFilled(BaseEvent):
    """Fired when transaction matching completes."""
    pass


@dataclass(frozen=True)
class PositionOpened(BaseEvent):
    """Fired when new position exposure starts."""
    pass


@dataclass(frozen=True)
class PositionClosed(BaseEvent):
    """Fired when position units close out."""
    pass


@dataclass(frozen=True)
class PortfolioUpdated(BaseEvent):
    """Fired when equity, margin, or PnL balance shifts."""
    pass


@dataclass(frozen=True)
class BacktestCompleted(BaseEvent):
    """Fired when historical data stream completes."""
    pass
