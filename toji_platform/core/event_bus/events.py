"""Concrete system events for the Toji kernel.

Every event is a **frozen dataclass** inheriting from ``BaseEvent``.
Fields ``event_id`` and ``timestamp`` are generated automatically.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from toji_platform.core.event_bus.interfaces import IEvent
from toji_platform.core.types import EventId, Payload


@dataclass(frozen=True)
class BaseEvent(IEvent):
    """Immutable base event with auto-generated id and timestamp.

    Subclasses should set ``source`` and extend ``payload`` as needed.
    """

    source: str = ""
    payload: Payload = field(default_factory=dict)
    event_id: EventId = field(
        default_factory=lambda: EventId(str(uuid.uuid4()))
    )
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def event_type(self) -> str:
        """Derive event type from the class name.

        ``AssetSelected`` → ``"system.asset_selected"``
        """
        cls_name = type(self).__name__
        # PascalCase → snake_case
        snake = ""
        for i, ch in enumerate(cls_name):
            if ch.isupper() and i > 0:
                snake += "_"
            snake += ch.lower()
        return f"system.{snake}"


# ── System Events ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class AssetSelected(BaseEvent):
    """Fired when an asset is selected for analysis or tracking."""


@dataclass(frozen=True)
class MarketDataUpdated(BaseEvent):
    """Fired when new market data arrives."""


@dataclass(frozen=True)
class ResearchCompleted(BaseEvent):
    """Fired when a research module finishes its analysis."""


@dataclass(frozen=True)
class RiskCalculated(BaseEvent):
    """Fired when a risk assessment is completed."""


@dataclass(frozen=True)
class MemoryUpdated(BaseEvent):
    """Fired when the memory system stores or updates knowledge."""


@dataclass(frozen=True)
class StrategyCreated(BaseEvent):
    """Fired when a new strategy is defined."""


@dataclass(frozen=True)
class BacktestCompleted(BaseEvent):
    """Fired when a backtest run finishes."""


@dataclass(frozen=True)
class DecisionGenerated(BaseEvent):
    """Fired when an agent or module produces a decision."""


@dataclass(frozen=True)
class TradeRecorded(BaseEvent):
    """Fired when a trade execution record is persisted."""


@dataclass(frozen=True)
class LearningCompleted(BaseEvent):
    """Fired when a learning / adaptation cycle finishes."""


@dataclass(frozen=True)
class SubsystemHeartbeat(BaseEvent):
    """Fired periodically to report subsystem operational statistics."""


@dataclass(frozen=True)
class MarketDataReceived(BaseEvent):
    """Fired when market data is received from gateway."""


@dataclass(frozen=True)
class MarketIntelligenceCompleted(BaseEvent):
    """Fired when market intelligence completes analysis."""


@dataclass(frozen=True)
class PriceActionCompleted(BaseEvent):
    """Fired when price action analysis completes."""


@dataclass(frozen=True)
class ConfluenceCompleted(BaseEvent):
    """Fired when confluence analysis completes."""


@dataclass(frozen=True)
class StrategyGenerated(BaseEvent):
    """Fired when strategy generation is complete."""


@dataclass(frozen=True)
class RiskChecked(BaseEvent):
    """Fired when risk engine check is complete."""


@dataclass(frozen=True)
class DashboardUpdated(BaseEvent):
    """Fired when dashboard state updates."""


@dataclass(frozen=True)
class MarketTickReceived(BaseEvent):
    """Fired when a real-time market tick/trade is received from the exchange."""


@dataclass(frozen=True)
class OrderBookUpdated(BaseEvent):
    """Fired when a real-time order book update is received."""


@dataclass(frozen=True)
class TradeExecuted(BaseEvent):
    """Fired when a trade execution message is received."""


@dataclass(frozen=True)
class AccountUpdated(BaseEvent):
    """Fired when user account information is updated."""


@dataclass(frozen=True)
class BalanceUpdated(BaseEvent):
    """Fired when user balance is updated."""


@dataclass(frozen=True)
class PositionUpdated(BaseEvent):
    """Fired when user position is updated."""


@dataclass(frozen=True)
class ConnectionLost(BaseEvent):
    """Fired when a WebSocket connection is lost."""


@dataclass(frozen=True)
class ConnectionRecovered(BaseEvent):
    """Fired when a WebSocket connection is successfully recovered."""


@dataclass(frozen=True)
class LatencyMeasured(BaseEvent):
    """Fired when exchange latency is measured."""


@dataclass(frozen=True)
class HeartbeatUpdated(BaseEvent):
    """Fired when exchange WebSocket heartbeat/ping-pong completes."""


