from __future__ import annotations

from dataclasses import dataclass
from toji_platform.core.event_bus.events import BaseEvent


@dataclass(frozen=True)
class PositionOpened(BaseEvent):
    """Fired when a new trading position is opened.

    Payload should contain:
        symbol: str
        timeframe: str
        position: dict representing serialized Position.
    """
    pass


@dataclass(frozen=True)
class PositionUpdated(BaseEvent):
    """Fired when an existing open position is updated (quantity size or price changed).

    Payload should contain:
        symbol: str
        timeframe: str
        position: dict representing serialized Position.
    """
    pass


@dataclass(frozen=True)
class PositionClosed(BaseEvent):
    """Fired when an active position is completely closed.

    Payload should contain:
        symbol: str
        timeframe: str
        position: dict representing serialized ClosedPosition.
    """
    pass


@dataclass(frozen=True)
class PortfolioUpdated(BaseEvent):
    """Fired when the overall portfolio metrics or snapshots are updated.

    Payload should contain:
        symbol: str
        timeframe: str
        portfolio: dict representing serialized PortfolioSnapshot.
    """
    pass


@dataclass(frozen=True)
class PnlUpdated(BaseEvent):
    """Fired when realized or unrealized PnL shifts.

    Payload should contain:
        symbol: str
        timeframe: str
        total_realized_pnl: float
        total_unrealized_pnl: float
    """
    pass


@dataclass(frozen=True)
class ExposureUpdated(BaseEvent):
    """Fired when net or gross portfolio exposures shift.

    Payload should contain:
        symbol: str
        timeframe: str
        gross_exposure: float
        net_exposure: float
    """
    pass
