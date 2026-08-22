"""Domain events for the Execution Simulator.
"""

from __future__ import annotations

from dataclasses import dataclass
from toji_platform.core.event_bus.events import BaseEvent


@dataclass(frozen=True)
class OrderSimulationStarted(BaseEvent):
    """Fired when simulator order matching starts."""
    pass


@dataclass(frozen=True)
class OrderSimulationCompleted(BaseEvent):
    """Fired when simulator completes executions matches."""
    pass
