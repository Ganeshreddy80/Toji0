"""Event Bus — central publish/subscribe system for Toji.

Public API:
    - ``IEvent``, ``IEventHandler``, ``IEventBus`` — interfaces
    - ``BaseEvent`` — frozen dataclass base for all events
    - ``InMemoryEventBus`` — default synchronous implementation
    - System events (``AssetSelected``, ``MarketDataUpdated``, etc.)
"""

from toji_platform.core.event_bus.bus import InMemoryEventBus
from toji_platform.core.event_bus.events import (
    AssetSelected,
    BacktestCompleted,
    BaseEvent,
    DecisionGenerated,
    LearningCompleted,
    MarketDataUpdated,
    MemoryUpdated,
    ResearchCompleted,
    RiskCalculated,
    StrategyCreated,
    TradeRecorded,
    MarketTickReceived,
    OrderBookUpdated,
    TradeExecuted,
    AccountUpdated,
    BalanceUpdated,
    PositionUpdated,
    ConnectionLost,
    ConnectionRecovered,
    LatencyMeasured,
    HeartbeatUpdated,
)
from toji_platform.core.event_bus.interfaces import IEvent, IEventBus, IEventHandler

__all__ = [
    "AssetSelected",
    "BacktestCompleted",
    "BaseEvent",
    "DecisionGenerated",
    "IEvent",
    "IEventBus",
    "IEventHandler",
    "InMemoryEventBus",
    "LearningCompleted",
    "MarketDataUpdated",
    "MemoryUpdated",
    "ResearchCompleted",
    "RiskCalculated",
    "StrategyCreated",
    "TradeRecorded",
    "MarketTickReceived",
    "OrderBookUpdated",
    "TradeExecuted",
    "AccountUpdated",
    "BalanceUpdated",
    "PositionUpdated",
    "ConnectionLost",
    "ConnectionRecovered",
    "LatencyMeasured",
    "HeartbeatUpdated",
]
