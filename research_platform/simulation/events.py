"""Domain events for the Digital Twin & Simulation Engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from toji_platform.core.event_bus.events import BaseEvent


@dataclass(frozen=True)
class SimulationStarted(BaseEvent):
    """Fired when a simulation session initialized."""
    pass


@dataclass(frozen=True)
class SimTickReplayed(BaseEvent):
    """Fired when a tick replayed to simulation components."""
    pass


@dataclass(frozen=True)
class SimOrderExecuted(BaseEvent):
    """Fired when a simulator order execution matched."""
    pass


@dataclass(frozen=True)
class FailureInjected(BaseEvent):
    """Fired when hardware/connection failures are injected."""
    pass


@dataclass(frozen=True)
class SimulationCompleted(BaseEvent):
    """Fired when simulation execution session completes."""
    pass
