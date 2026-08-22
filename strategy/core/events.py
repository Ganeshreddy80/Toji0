"""System events for the Strategy Engine.

All events are frozen dataclasses inheriting from BaseEvent.
"""

from __future__ import annotations

from dataclasses import dataclass
from toji_platform.core.event_bus.events import BaseEvent


@dataclass(frozen=True)
class StrategyInitialized(BaseEvent):
    """Fired when the Strategy Engine plugin starts successfully."""


@dataclass(frozen=True)
class StrategyShutdown(BaseEvent):
    """Fired when the Strategy Engine plugin shuts down."""


@dataclass(frozen=True)
class StrategyUpdated(BaseEvent):
    """Fired when a strategy state is evaluated or updated.

    Payload should contain:
        symbol: str
        timeframe: str
        state: dict representing the serialized StrategyState.
    """


@dataclass(frozen=True)
class StrategySignalEvent(BaseEvent):
    """Fired when a trade setup strategy signal (BUY/SELL) triggers.

    Payload should contain:
        symbol: str
        timeframe: str
        signal: dict representing the serialized StrategySignal.
    """

    @property
    def event_type(self) -> str:
        """Override to match system.strategy_signal exactly."""
        return "system.strategy_signal"


@dataclass(frozen=True)
class StrategyChanged(BaseEvent):
    """Fired when the active strategy type transitions (e.g. Trend Following -> Reversal).

    Payload should contain:
        symbol: str
        timeframe: str
        old_strategy: str | None
        new_strategy: str | None
        state: dict representing the serialized StrategyState.
    """


@dataclass(frozen=True)
class StrategyRejected(BaseEvent):
    """Fired when an active strategy drops back to WAIT.

    Payload should contain:
        symbol: str
        timeframe: str
        state: dict representing the serialized StrategyState.
    """
