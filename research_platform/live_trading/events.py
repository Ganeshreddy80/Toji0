"""Event contracts for the Live Trading Engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from toji_platform.core.event_bus.events import BaseEvent


@dataclass(frozen=True)
class TradingStarted(BaseEvent):
    """Fired when live trading session transitions to ACTIVE status."""
    pass


@dataclass(frozen=True)
class TradingStopped(BaseEvent):
    """Fired when live trading session transitions to TERMINATED status."""
    pass


@dataclass(frozen=True)
class MarketOpened(BaseEvent):
    """Fired when calendar indicates exchange open times."""
    pass


@dataclass(frozen=True)
class MarketClosed(BaseEvent):
    """Fired when calendar indicates exchange maintenance times."""
    pass


@dataclass(frozen=True)
class SignalReceived(BaseEvent):
    """Fired when strategy processors ingest a validated alpha signal."""
    pass


@dataclass(frozen=True)
class OrderGenerated(BaseEvent):
    """Fired when portfolio sizing generates OMS order requests."""
    pass


@dataclass(frozen=True)
class OrderExecuted(BaseEvent):
    """Fired when EMS executes order fills."""
    pass


@dataclass(frozen=True)
class PositionOpened(BaseEvent):
    """Fired when new position record opens."""
    pass


@dataclass(frozen=True)
class PositionClosed(BaseEvent):
    """Fired when open position reduces to zero quantity."""
    pass


@dataclass(frozen=True)
class PortfolioUpdated(BaseEvent):
    """Fired when position values or cash balances change."""
    pass


@dataclass(frozen=True)
class HeartbeatTimeout(BaseEvent):
    """Fired when keep-alive response latencies exceed limits."""
    pass


@dataclass(frozen=True)
class RecoveryStarted(BaseEvent):
    """Fired when restart recovery process triggers."""
    pass


@dataclass(frozen=True)
class RecoveryCompleted(BaseEvent):
    """Fired when pending orders re-hydration completes."""
    pass
