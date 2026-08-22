"""Sizing and allocation domain events.
"""

from __future__ import annotations

from dataclasses import dataclass
from toji_platform.core.event_bus.events import BaseEvent


@dataclass(frozen=True)
class PositionSizeCalculated(BaseEvent):
    """Fired when position size calculations are completed."""
    pass


@dataclass(frozen=True)
class PositionSizingInitialized(BaseEvent):
    """Fired when position sizing plugin is initialized."""
    pass
