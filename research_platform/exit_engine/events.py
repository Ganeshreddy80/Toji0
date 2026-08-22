"""Domain events for the Exit Engine subsystem.
"""

from __future__ import annotations

from dataclasses import dataclass
from toji_platform.core.event_bus.events import BaseEvent


@dataclass(frozen=True)
class PositionExitRequested(BaseEvent):
    """Fired when the Exit Engine requests a position close order."""


@dataclass(frozen=True)
class PositionClosed(BaseEvent):
    """Fired when a position is closed and exit analytics are compiled."""


@dataclass(frozen=True)
class StopLossTriggered(BaseEvent):
    """Fired when a position's stop loss is breached."""


@dataclass(frozen=True)
class TakeProfitTriggered(BaseEvent):
    """Fired when a position's take profit is reached."""


@dataclass(frozen=True)
class TrailingStopUpdated(BaseEvent):
    """Fired when the trailing stop level is adjusted upward (for longs) or downward (for shorts)."""


@dataclass(frozen=True)
class ExitRejected(BaseEvent):
    """Fired when an exit close order is rejected by the trade manager."""
