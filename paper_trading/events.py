"""Immutable domain events for the Paper Trading subsystem (Sprint 9A & 9B)."""

from __future__ import annotations

from datetime import datetime, timezone
import uuid
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field

from paper_trading.models.market_models import (
    FeedStatus,
    MarketCandle,
    MarketTick,
)
from paper_trading.models.paper_models import (
    PaperAccount,
    PaperOrder,
    PaperPosition,
    PaperSession,
    PaperTrade,
)
from toji_platform.core.event_bus.interfaces import IEvent


class PaperBaseEvent(BaseModel):
    """Base class for all immutable paper trading domain events."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Event UUID.")
    event_type: str = Field(..., description="Unique event type string identifier.")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Event creation timestamp.",
    )
    source: str = Field(default="paper_trading", description="Event source component.")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Structured event payload.")

    model_config = ConfigDict(frozen=True)


# Register PaperBaseEvent with IEvent interface to support isinstance checks safely without MRO metaclass conflicts
IEvent.register(PaperBaseEvent)


class PaperOrderSubmitted(PaperBaseEvent):
    """Event emitted when a new paper order is submitted."""

    def __init__(self, order: PaperOrder, **data: Any) -> None:
        payload = {"order": order.model_dump()}
        super().__init__(event_type="PaperOrderSubmitted", payload=payload, **data)


class PaperOrderFilled(PaperBaseEvent):
    """Event emitted when a paper order is partially or fully filled."""

    def __init__(self, order: PaperOrder, trade: PaperTrade, **data: Any) -> None:
        payload = {"order": order.model_dump(), "trade": trade.model_dump()}
        super().__init__(event_type="PaperOrderFilled", payload=payload, **data)


class PaperOrderCancelled(PaperBaseEvent):
    """Event emitted when a paper order is cancelled."""

    def __init__(self, order: PaperOrder, **data: Any) -> None:
        payload = {"order": order.model_dump()}
        super().__init__(event_type="PaperOrderCancelled", payload=payload, **data)


class PaperTradeExecuted(PaperBaseEvent):
    """Event emitted when a paper trade is executed."""

    def __init__(self, trade: PaperTrade, **data: Any) -> None:
        payload = {"trade": trade.model_dump()}
        super().__init__(event_type="PaperTradeExecuted", payload=payload, **data)


class PaperPositionUpdated(PaperBaseEvent):
    """Event emitted when a position is updated or closed."""

    def __init__(self, position: PaperPosition, **data: Any) -> None:
        payload = {"position": position.model_dump()}
        super().__init__(event_type="PaperPositionUpdated", payload=payload, **data)


class PaperAccountUpdated(PaperBaseEvent):
    """Event emitted when account equity or cash ledger updates."""

    def __init__(self, account: PaperAccount, **data: Any) -> None:
        payload = {"account": account.model_dump()}
        super().__init__(event_type="PaperAccountUpdated", payload=payload, **data)


class PaperSessionStarted(PaperBaseEvent):
    """Event emitted when a paper trading session starts."""

    def __init__(self, session: PaperSession, **data: Any) -> None:
        payload = {"session": session.model_dump()}
        super().__init__(event_type="PaperSessionStarted", payload=payload, **data)


class PaperSessionStopped(PaperBaseEvent):
    """Event emitted when a paper trading session stops."""

    def __init__(self, session: PaperSession, **data: Any) -> None:
        payload = {"session": session.model_dump()}
        super().__init__(event_type="PaperSessionStopped", payload=payload, **data)


# --- Sprint 9B Market Data Domain Events ---


class MarketTickReceived(PaperBaseEvent):
    """Event emitted when a new market tick is received and validated."""

    def __init__(self, tick: MarketTick, **data: Any) -> None:
        payload = {"tick": tick.model_dump()}
        super().__init__(event_type="MarketTickReceived", payload=payload, **data)


class CandleClosed(PaperBaseEvent):
    """Event emitted when an OHLCV candle bar closes on interval completion."""

    def __init__(self, candle: MarketCandle, **data: Any) -> None:
        payload = {"candle": candle.model_dump()}
        super().__init__(event_type="CandleClosed", payload=payload, **data)


class FeedConnected(PaperBaseEvent):
    """Event emitted when the market data feed connects successfully."""

    def __init__(self, status: FeedStatus, **data: Any) -> None:
        payload = {"status": status.model_dump()}
        super().__init__(event_type="FeedConnected", payload=payload, **data)


class FeedDisconnected(PaperBaseEvent):
    """Event emitted when the market data feed disconnects."""

    def __init__(self, status: FeedStatus, reason: str = "Disconnected", **data: Any) -> None:
        payload = {"status": status.model_dump(), "reason": reason}
        super().__init__(event_type="FeedDisconnected", payload=payload, **data)


class FeedRecovered(PaperBaseEvent):
    """Event emitted when the market data feed successfully recovers from a disruption."""

    def __init__(self, status: FeedStatus, attempts: int = 1, **data: Any) -> None:
        payload = {"status": status.model_dump(), "attempts": attempts}
        super().__init__(event_type="FeedRecovered", payload=payload, **data)


class MarketOpened(PaperBaseEvent):
    """Event emitted when a market trading session opens."""

    def __init__(self, session_name: str = "RegularTradingHours", **data: Any) -> None:
        payload = {"session_name": session_name}
        super().__init__(event_type="MarketOpened", payload=payload, **data)


class MarketClosed(PaperBaseEvent):
    """Event emitted when a market trading session closes."""

    def __init__(self, session_name: str = "RegularTradingHours", **data: Any) -> None:
        payload = {"session_name": session_name}
        super().__init__(event_type="MarketClosed", payload=payload, **data)
