"""System events for the Position Sizing Engine subsystem.

All events are frozen dataclasses inheriting from BaseEvent.
"""

from __future__ import annotations

from dataclasses import dataclass
from toji_platform.core.event_bus.events import BaseEvent


@dataclass(frozen=True)
class PositionSizingInitialized(BaseEvent):
    """Fired when the Position Sizing Engine plugin starts successfully."""


@dataclass(frozen=True)
class PositionSizingShutdown(BaseEvent):
    """Fired when the Position Sizing Engine plugin shuts down."""


@dataclass(frozen=True)
class PositionSizeUpdated(BaseEvent):
    """Fired when a position sizing state is updated.

    Payload should contain:
        symbol: str
        timeframe: str
        state: dict representing the serialized PositionSizingState.
    """


@dataclass(frozen=True)
class PositionSizeCalculated(BaseEvent):
    """Fired when a position size is successfully computed.

    Payload should contain:
        symbol: str
        timeframe: str
        state: dict representing the serialized PositionSizingState.
    """


@dataclass(frozen=True)
class PositionSizeRejected(BaseEvent):
    """Fired when a position sizing request is rejected.

    Payload should contain:
        symbol: str
        timeframe: str
        state: dict representing the serialized PositionSizingState.
        reason: str detailing the primary validation rejection.
    """


@dataclass(frozen=True)
class PositionSizeChanged(BaseEvent):
    """Fired when the calculated position size changes significantly.

    Payload should contain:
        symbol: str
        timeframe: str
        previous_size: float
        new_size: float
    """
