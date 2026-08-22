"""Domain events for the Portfolio Accounting subsystem.

All events follow the existing frozen-dataclass + BaseEvent convention.
Event type strings are auto-derived:  PortfolioUpdated → system.portfolio_updated
"""

from __future__ import annotations

from dataclasses import dataclass
from toji_platform.core.event_bus.events import BaseEvent


@dataclass(frozen=True)
class PortfolioUpdated(BaseEvent):
    """Fired after every portfolio recalculation (on tick or fill)."""


@dataclass(frozen=True)
class PositionValuationUpdated(BaseEvent):
    """Fired when a single position's valuation changes on a market tick."""


@dataclass(frozen=True)
class TradeClosed(BaseEvent):
    """Fired when a position is fully closed and PnL is realized."""


@dataclass(frozen=True)
class PortfolioMetricsUpdated(BaseEvent):
    """Fired after the MetricsEngine recomputes portfolio-level statistics."""


@dataclass(frozen=True)
class PnLUpdated(BaseEvent):
    """Fired when realized or unrealized PnL is updated."""


@dataclass(frozen=True)
class DrawdownUpdated(BaseEvent):
    """Fired when portfolio drawdown or peak equity changes."""


@dataclass(frozen=True)
class PerformanceUpdated(BaseEvent):
    """Fired when portfolio performance statistics (Sharpe, Sortino, etc.) are computed."""


@dataclass(frozen=True)
class PaperOrderFilled(BaseEvent):
    """Fired when a paper order is successfully filled."""


@dataclass(frozen=True)
class OrderFilled(BaseEvent):
    """Fired when a live broker order is successfully filled."""


@dataclass(frozen=True)
class PositionClosed(BaseEvent):
    """Fired when an open position is closed."""


@dataclass(frozen=True)
class PositionUpdated(BaseEvent):
    """Fired when a position's average entry or quantity changes."""
