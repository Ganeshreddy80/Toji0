"""Domain events for the Stress Testing Engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from toji_platform.core.event_bus.events import BaseEvent


@dataclass(frozen=True)
class StressScenarioRun(BaseEvent):
    """Fired when stress scenario completes."""
    pass
