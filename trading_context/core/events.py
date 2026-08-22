"""System events for the Trading Context subsystem.

All events are frozen dataclasses inheriting from BaseEvent.
"""

from __future__ import annotations

from dataclasses import dataclass
from toji_platform.core.event_bus.events import BaseEvent


@dataclass(frozen=True)
class TradingContextInitialized(BaseEvent):
    """Fired when the Trading Context plugin starts successfully."""


@dataclass(frozen=True)
class TradingContextShutdown(BaseEvent):
    """Fired when the Trading Context plugin shuts down."""


@dataclass(frozen=True)
class TradingContextCreated(BaseEvent):
    """Fired when a new Trading Context is constructed.

    Payload should contain:
        symbol: str
        timeframe: str
        context: dict representing the serialized TradingContext.
    """


@dataclass(frozen=True)
class TradingContextUpdated(BaseEvent):
    """Fired when an existing Trading Context is updated.

    Payload should contain:
        symbol: str
        timeframe: str
        context: dict representing the serialized TradingContext.
    """


@dataclass(frozen=True)
class TradingContextInvalid(BaseEvent):
    """Fired when context validation check fails.

    Payload should contain:
        symbol: str
        timeframe: str
        reason: str
    """
